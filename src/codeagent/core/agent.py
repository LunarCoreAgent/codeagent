"""The agent loop: send messages, dispatch tool calls, feed results back."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Literal

from codeagent.core.budget import Budget, BudgetExceededError
from codeagent.core.types import (
    LLMResponse,
    Message,
    ToolCall,
    ToolResult,
    Usage,
)
from codeagent.llm.base import LLMProvider
from codeagent.log import get_logger
from codeagent.security.policy import ApprovalDecision, PermissionPolicy, RiskLevel
from codeagent.tools.base import ToolRegistry

log = get_logger("agent")

if TYPE_CHECKING:
    from codeagent.memory.compact import ConversationCompactor
    from codeagent.memory.store import MemoryStore
    from codeagent.settings import Settings
    from codeagent.skills.evolve import SkillEvolver
    from codeagent.skills.skill import Skill, SkillLibrary

DEFAULT_SYSTEM_PROMPT = """\
You are an expert software engineering agent. You help users with code \
development tasks: reading, writing, and editing files, running shell \
commands, and searching codebases.

Guidelines:
- Think step by step before acting. Prefer small, verifiable changes.
- Explore before editing: read the relevant files and understand context.
- Use tools to act on the real workspace; never invent file contents.
- After making changes, verify them (run tests, linters, or builds) when possible.
- When a website / frontend / landing-page task is finished, start a local \
HTTP preview if needed and call the browser tool (action=navigate) to show \
the product in the built-in browser before your final summary. Never use \
file:// — only http://127.0.0.1 or http://localhost.
- When the task is complete, summarize what you did concisely.
"""

EventType = Literal[
    "text", "thinking", "tool_call", "tool_result", "iteration", "approval",
    "done", "error", "skill_evolved", "skills_activated",
]
EventHandler = Callable[["AgentEvent"], None | Awaitable[None]]


@dataclass
class AgentEvent:
    type: EventType
    data: Any = None


class MaxIterationsError(RuntimeError):
    """Raised when the agent exceeds its iteration budget."""


class Agent:
    """A tool-using coding agent driven by an LLM provider.

    Parameters
    ----------
    provider:
        The LLM backend used for completions.
    tools:
        Registry of tools the agent may call.
    system_prompt:
        Overrides the default coding-agent system prompt.
    max_iterations:
        Safety cap on model/tool round-trips per ``run``.
    permissions:
        Optional :class:`PermissionPolicy` gating tool calls by risk.
        ``None`` means permissive (everything is approved).
    budget:
        Optional token :class:`Budget`; sub-agent usage rolls up into it.
    compactor:
        Optional :class:`ConversationCompactor`; when history grows past
        its threshold, older turns are summarized (short-term memory).
    memory:
        Optional :class:`MemoryStore`; memories relevant to each task are
        injected into the system prompt (long-term memory recall).
    skills:
        Optional :class:`SkillLibrary`; skill catalog is always visible,
        matching skills auto-activate, and ``use_skill`` can load any pack.
    workspace_hints:
        Optional project/file-type text used to recognize work content.
    settings:
        Optional host-wide personalization :class:`Settings`; extra
        instructions and context injected into every conversation.
    skill_evolver:
        Optional :class:`SkillEvolver`; after each successful run it
        reflects on the experience and may write a new skill.
    on_event:
        Optional callback receiving :class:`AgentEvent` objects for
        streaming UIs, logging, or human-in-the-loop approval.
    """

    def __init__(
        self,
        provider: LLMProvider,
        tools: ToolRegistry | None = None,
        system_prompt: str | None = None,
        max_iterations: int = 50,
        soft_iterations: bool = False,
        permissions: PermissionPolicy | None = None,
        budget: Budget | None = None,
        compactor: "ConversationCompactor | None" = None,
        memory: "MemoryStore | None" = None,
        skills: "SkillLibrary | None" = None,
        settings: "Settings | None" = None,
        skill_evolver: "SkillEvolver | None" = None,
        on_event: EventHandler | None = None,
        workspace_hints: str = "",
    ) -> None:
        self.provider = provider
        self.tools = tools or ToolRegistry()
        self.system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
        self.max_iterations = max_iterations
        self.soft_iterations = soft_iterations
        self.permissions = permissions
        self.budget = budget
        self.compactor = compactor
        self.memory = memory
        self.skills = skills
        self.settings = settings
        self.skill_evolver = skill_evolver
        self.on_event = on_event
        self.workspace_hints = workspace_hints
        self.messages: list[Message] = []
        self.own_usage = Usage()
        self._children_usage = Usage()
        self._memory_context = ""
        self._auto_skill_names: list[str] = []
        self._invoked_skill_names: list[str] = []
        self._browser_navigated = False
        self._showcase_nudged = False
        self._bind_skill_runtime()

    @property
    def usage(self) -> Usage:
        """Total token usage, including delegated sub-agents."""
        return self.own_usage + self._children_usage

    @property
    def total_usage(self) -> Usage:
        return self.usage

    def _add_child_usage(self, usage: Usage) -> None:
        """Roll a sub-agent's token usage into this agent's budget."""
        self._children_usage = self._children_usage + usage

    async def _emit(self, event_type: EventType, data: Any = None) -> None:
        if self.on_event is None:
            return
        result = self.on_event(AgentEvent(type=event_type, data=data))
        if result is not None and hasattr(result, "__await__"):
            await result

    def reset(self) -> None:
        """Clear conversation history and token usage."""
        self.messages.clear()
        self.own_usage = Usage()
        self._children_usage = Usage()
        self._auto_skill_names.clear()
        self._invoked_skill_names.clear()
        self._memory_context = ""
        self._browser_navigated = False
        self._showcase_nudged = False

    def _bind_skill_runtime(self) -> None:
        """Expose use_skill so the model can independently load any pack."""
        if self.skills is None or not len(self.skills):
            return
        if self.tools.get("use_skill") is not None:
            return
        from codeagent.skills.runtime import UseSkillTool

        self.tools.register(UseSkillTool(self.skills, self.invoke_skills))

    def invoke_skills(self, names: list[str]) -> list["Skill"]:
        """Mark skills as user-invoked (or model-invoked) for this session."""
        from codeagent.skills.skill import Skill

        loaded: list[Skill] = []
        if self.skills is None:
            return loaded
        for name in names:
            skill = self.skills.get(name)
            if skill is None or skill.name in self._invoked_skill_names:
                if skill is not None:
                    loaded.append(skill)
                continue
            self._invoked_skill_names.append(skill.name)
            loaded.append(skill)
        return loaded

    def _active_skill_names(self) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for name in (*self._auto_skill_names, *self._invoked_skill_names):
            if name in seen:
                continue
            seen.add(name)
            ordered.append(name)
        return ordered

    def _auto_activate_skills(self, task: str) -> list[str]:
        """Recognize work content and enable matching skills without asking."""
        if self.skills is None or not len(self.skills):
            return []
        from codeagent.skills.runtime import match_work_skills

        hits = match_work_skills(
            self.skills, task, hints=self.workspace_hints, limit=8,
        )
        names = [skill.name for skill in hits]
        self._auto_skill_names = names
        return names

    def _budget_exceeded(self) -> bool:
        return self.budget is not None and self.budget.exceeded(self.usage)

    def _raise_budget(self) -> None:
        total = self.usage.input_tokens + self.usage.output_tokens
        cap = self.budget.max_total_tokens if self.budget is not None else None
        raise BudgetExceededError(
            f"Token budget exceeded: {total} tokens used (budget: {cap})"
        )

    def _check_budget(self) -> None:
        if self._budget_exceeded():
            self._raise_budget()

    @staticmethod
    def _split_response(response: LLMResponse) -> tuple[str, str]:
        """Split CoT from the visible answer for UI streaming."""
        from codeagent.core.thinking import split_thinking

        return split_thinking(
            response.content or "",
            getattr(response, "reasoning", "") or "",
        )

    async def _emit_response_parts(self, response: LLMResponse) -> tuple[str, str]:
        """Push thinking + text events; return ``(visible, thinking)``."""
        visible, thinking = self._split_response(response)
        if thinking:
            await self._emit("thinking", thinking)
        if visible:
            await self._emit("text", visible)
        return visible, thinking

    async def _wrap_up_for_budget(self, fallback: str) -> str:
        """Ask for a final answer with no tools when the cap is hit mid-work."""
        hint = (
            "Token budget is exhausted. Give your best complete answer now "
            "based on work so far. Do not call tools."
        )
        try:
            response = await self.provider.complete(
                messages=[*self.messages, Message.user(hint)],
                tools=None,
                system=self._system_prompt(),
            )
            self.own_usage = self.own_usage + response.usage
            visible, thinking = await self._emit_response_parts(response)
            answer = visible or response.content or thinking
            if answer:
                return answer
        except Exception:
            log.exception("budget wrap-up failed")
        return fallback or (
            "Token 预算已用尽，已完成的工作见上文。请开新对话继续未做完的部分。"
        )

    async def _wrap_up_for_iterations(self) -> str:
        """Conclude without more tools when the iteration safety cap is hit."""
        hint = (
            "You have reached the maximum number of tool rounds. "
            "Stop calling tools. Summarize what you learned and give the "
            "best complete answer you can for the user now."
        )
        try:
            response = await self.provider.complete(
                messages=[*self.messages, Message.user(hint)],
                tools=None,
                system=self._system_prompt(),
            )
            self.own_usage = self.own_usage + response.usage
            visible, thinking = await self._emit_response_parts(response)
            answer = visible or response.content or thinking
            if answer:
                return answer
        except Exception:
            log.exception("iteration wrap-up failed")
        # Prefer the last assistant text already shown, if any.
        for msg in reversed(self.messages):
            if msg.role == "assistant" and (msg.content or "").strip():
                return msg.content
        return (
            "本轮工具往返次数已用尽。已完成的部分见上文；"
            "请开新对话继续，或把问题拆小后再发。"
        )

    def _system_prompt(self) -> str:
        """System prompt plus personalization, skills, budget, memories."""
        parts = [self.system_prompt]
        if self.settings is not None:
            block = self.settings.prompt_block()
            if block:
                parts.append(block)
        if self.skills is not None and len(self.skills):
            from codeagent.skills.runtime import STUDIO_SKILL_RULES, expand_work_query

            parts.append(STUDIO_SKILL_RULES)
            query = ""
            for msg in reversed(self.messages):
                if msg.role == "user":
                    query = (msg.content or "")[:800]
                    break
            blob = expand_work_query(" ".join(
                x for x in (query, self.workspace_hints) if x
            ))
            active = self._active_skill_names()
            if active:
                parts.append("[已自动启用 / 已调用技能 — 必须遵守]\n" + "、".join(active))
            block = self.skills.prompt_block(query=blob, active=active)
            if block:
                parts.append(block)
        if self._memory_context:
            parts.append(self._memory_context)
        if self.budget is not None and self.budget.aware:
            status = self.budget.status_message(self.usage)
            if status:
                parts.append(status)
        return "\n\n".join(parts)

    async def _refresh_memory_context(self, task: str) -> None:
        """Recall long-term memories relevant to the incoming task."""
        if self.memory is None:
            return
        memories = await self.memory.search(task, limit=5)
        if memories:
            lines = "\n".join(f"- {m.content}" for m in memories)
            self._memory_context = (
                "[Recalled memories from previous sessions]\n" + lines
            )

    async def run(self, task: str) -> str:
        """Run the agent on a task until the model stops calling tools.

        Returns the final assistant text. Raises :class:`MaxIterationsError`
        if the iteration budget is exhausted, or :class:`BudgetExceededError`
        if the token budget is exceeded mid-work (hard mode only). A finished
        answer is always returned even if it slightly overshoots the cap.
        """
        log.info("run start: provider=%s model=%s task=%.120r",
                 self.provider.name, self.provider.model, task)
        # Per-task accounting: reuse of this Agent (desktop / CLI chat)
        # must not stack every prior turn into one lifetime cap.
        self.own_usage = Usage()
        self._children_usage = Usage()
        self._browser_navigated = False
        self._showcase_nudged = False
        self.messages.append(Message.user(task))
        await self._refresh_memory_context(task)
        activated = self._auto_activate_skills(task)
        if activated:
            await self._emit("skills_activated", activated)
            log.info("auto skills: %s", ", ".join(activated))

        for iteration in range(1, self.max_iterations + 1):
            await self._emit("iteration", iteration)

            if self.compactor is not None:
                self.messages = await self.compactor.maybe_compact(self.messages)

            response = await self.provider.complete(
                messages=self.messages,
                tools=self.tools.schemas() or None,
                system=self._system_prompt(),
            )
            self.own_usage = self.own_usage + response.usage
            self.messages.append(Message.assistant(response.content, response.tool_calls))
            log.debug(
                "iter %d: in=%d out=%d tool_calls=%d",
                iteration, response.usage.input_tokens, response.usage.output_tokens,
                len(response.tool_calls),
            )

            visible, thinking = self._split_response(response)
            if thinking:
                await self._emit("thinking", thinking)
            if visible:
                await self._emit("text", visible)

            if not response.wants_tool_use:
                answer = visible or response.content or thinking
                if self._maybe_nudge_website_showcase(task, answer or ""):
                    continue
                await self._emit("done", response)
                log.info(
                    "run done: iters=%d tokens=%d+%d",
                    iteration,
                    self.usage.input_tokens, self.usage.output_tokens,
                )
                await self._maybe_evolve_skill(task, answer)
                return answer

            if self._budget_exceeded():
                if self.budget is not None and self.budget.soft:
                    answer = await self._wrap_up_for_budget(response.content)
                    await self._emit("done", response)
                    return answer
                self._raise_budget()

            results = await self._execute_tool_calls(response.tool_calls)
            self.messages.append(Message.tool(results))
            if self._budget_exceeded():
                if self.budget is not None and self.budget.soft:
                    answer = await self._wrap_up_for_budget("")
                    await self._emit("done", response)
                    return answer
                self._raise_budget()

        if self.soft_iterations:
            log.info(
                "soft wrap-up after %d iterations (cap=%d)",
                self.max_iterations, self.max_iterations,
            )
            answer = await self._wrap_up_for_iterations()
            await self._emit("done", None)
            return answer

        raise MaxIterationsError(
            f"Agent did not finish within {self.max_iterations} iterations"
        )

    async def _maybe_evolve_skill(self, task: str, answer: str) -> None:
        """Let the skill evolver reflect; never let it break a finished run."""
        if self.skill_evolver is None:
            return
        try:
            skill = await self.skill_evolver.evolve(task, answer)
        except Exception:
            return
        if skill is not None:
            await self._emit("skill_evolved", skill)

    def _maybe_nudge_website_showcase(self, task: str, answer: str) -> bool:
        """Once per run: ask the model to open the built-in browser for web work."""
        if self._showcase_nudged or self._browser_navigated:
            return False
        if self.tools.get("browser") is None:
            return False
        from codeagent.browser.showcase import SHOWCASE_NUDGE, looks_like_website_task

        if not looks_like_website_task(task, answer, self.workspace_hints):
            return False
        self._showcase_nudged = True
        self.messages.append(Message.user(SHOWCASE_NUDGE))
        log.info("website showcase nudge: ask model to call browser")
        return True

    async def _authorize(self, call: ToolCall) -> ApprovalDecision:
        if self.permissions is None:
            return ApprovalDecision.APPROVE
        tool = self.tools.get(call.name)
        if tool is None:
            return ApprovalDecision.APPROVE  # registry reports the unknown tool
        risk = tool.risk_for(call.arguments)
        decision = await self.permissions.authorize(call, risk)
        await self._emit("approval", {"call": call, "risk": risk, "decision": decision})
        return decision

    async def _execute_tool_calls(self, tool_calls: list[ToolCall]) -> list[ToolResult]:
        results: list[ToolResult] = []
        for call in tool_calls:
            await self._emit("tool_call", call)
            if call.name == "browser":
                action = str((call.arguments or {}).get("action") or "").lower()
                url = str((call.arguments or {}).get("url") or "")
                if action == "navigate" and url.strip():
                    self._browser_navigated = True
            decision = await self._authorize(call)
            log.info("tool %s decision=%s", call.name, decision.name)
            if decision == ApprovalDecision.DENY:
                result = ToolResult(
                    tool_call_id=call.id,
                    content=(
                        f"Tool call {call.name!r} was denied by the permission "
                        "policy. Do not retry the same call; ask the user or "
                        "choose a different approach."
                    ),
                    is_error=True,
                )
            else:
                result = await self.tools.execute(call)
                if result.is_error:
                    log.warning("tool %s error: %.200s", call.name, result.content)
            await self._emit("tool_result", result)
            results.append(result)
        return results
