"""Blueprint runner: executes a blueprint DAG with parallelism and approval gates."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Literal

from codeagent.blueprint.graph import Blueprint, Node, NodeKind
from codeagent.core.types import Message, Usage
from codeagent.llm.base import LLMProvider

NodeStatus = Literal["done", "rejected", "skipped"]


@dataclass
class NodeResult:
    node_id: str
    status: NodeStatus
    output: str = ""
    branches: list[str] = field(default_factory=list)  # chosen downstream ids


@dataclass
class ApprovalResult:
    """Human decision at an approval gate."""

    approved: bool
    reply: str | None = None  # when given, replaces the upstream output


@dataclass
class BlueprintReport:
    task: str
    results: dict[str, NodeResult]
    usage: Usage
    attempts: dict[str, int] = field(default_factory=dict)  # loop iterations etc.

    def outputs(self) -> dict[str, str]:
        return {nid: r.output for nid, r in self.results.items() if r.status == "done"}

    def final_output(self, blueprint: Blueprint) -> str:
        """Joined outputs of leaf nodes (the blueprint's deliverables)."""
        parts = [
            self.results[leaf].output
            for leaf in blueprint.leaves()
            if leaf in self.results and self.results[leaf].status == "done"
        ]
        return "\n\n".join(parts)

    def scorecard(self, blueprint: Blueprint) -> dict[str, Any]:
        """Per-run scorecard: node outcomes, attempts, token usage (HomeRail-style)."""
        done = sum(1 for r in self.results.values() if r.status == "done")
        skipped = sum(1 for r in self.results.values() if r.status == "skipped")
        rejected = sum(1 for r in self.results.values() if r.status == "rejected")
        total = len(self.results)
        return {
            "blueprint": blueprint.name,
            "task": self.task,
            "nodes_total": total,
            "nodes_done": done,
            "nodes_skipped": skipped,
            "nodes_rejected": rejected,
            "success_rate": done / total if total else 0.0,
            "attempts": dict(self.attempts),
            "tokens": {
                "input": self.usage.input_tokens,
                "output": self.usage.output_tokens,
            },
            "nodes": {
                nid: {"status": r.status, "kind": blueprint.nodes[nid].kind.value}
                for nid, r in self.results.items()
            },
        }


# handler(node, upstream_output) -> ApprovalResult (sync or async)
ApprovalHandler = Callable[[Node, str], ApprovalResult | Awaitable[ApprovalResult]]

WHILE_CONTINUE_PROMPT = """\
You are a loop-control node. Based on the latest result, decide whether \
another iteration is needed.

Goal:
{goal}

Latest result (iteration {iteration}):
{last}

Reply with exactly one word: CONTINUE or DONE."""

CONDITION_PROMPT = """\
You are a routing node in a workflow. Read the upstream output and choose \
EXACTLY ONE branch to continue with.

Upstream output:
{inputs}

Available branches:
{branches}

Reply with ONLY the branch name, nothing else."""

MANAGER_PROMPT = """\
You are a manager node in a workflow. Read the upstream output and decide \
which branches to activate (one or more).

Upstream output:
{inputs}

Available branches:
{branches}

Reply with the branch names to activate, one per line, nothing else."""

AGGREGATE_PROMPT = """\
Merge the following parallel results into one coherent summary.

{inputs}"""


def _render(template: str, task: str, inputs: str) -> str:
    """Fill {task}/{inputs} placeholders without str.format brace pitfalls."""
    if not template:
        return f"Task:\n{task}\n\nInput:\n{inputs}" if inputs else task
    return template.replace("{task}", task).replace("{inputs}", inputs)


class BlueprintRunner:
    """Runs a :class:`Blueprint` level by level, parallel within a level.

    Parameters
    ----------
    provider:
        Default LLM backend for agent/manager/condition/aggregate nodes.
    blueprint:
        The validated DAG to execute.
    approval_handler:
        Called at APPROVAL nodes. ``None`` auto-approves (permissive).
    audit:
        Optional audit log with a ``record(kind, **detail)`` method
        (e.g. :class:`codeagent.court.audit.AuditLog`).
    providers:
        Optional per-node provider mapping, keyed by node id with ``"*"``
        as fallback — "smart brain, efficient workers" (HomeRail-style).
    command_allowlist:
        Executables a COMMAND node may run (no shell). Empty = all denied.
    """

    def __init__(
        self,
        provider: LLMProvider,
        blueprint: Blueprint,
        approval_handler: ApprovalHandler | None = None,
        audit: Any = None,
        providers: dict[str, LLMProvider] | None = None,
        command_allowlist: list[str] | None = None,
    ) -> None:
        self.provider = provider
        self.blueprint = blueprint
        self.approval_handler = approval_handler
        self.audit = audit
        self.providers = providers or {}
        self.command_allowlist = set(command_allowlist or [])
        self.usage = Usage()
        self.attempts: dict[str, int] = {}

    def _provider_for(self, node: Node) -> LLMProvider:
        return self.providers.get(node.id) or self.providers.get("*") or self.provider

    def _join_admits(self, node: Node, upstream_results: list[NodeResult]) -> bool:
        """JOIN admission: all / any / n_of_m quorum over upstream outcomes."""
        done = sum(1 for r in upstream_results if r.status == "done")
        mode = node.config.get("mode", "all")
        if mode == "any":
            return done >= 1
        if mode == "n_of_m":
            return done >= int(node.config.get("threshold", len(upstream_results)))
        return done == len(upstream_results)  # all

    async def run(self, task: str) -> BlueprintReport:
        results: dict[str, NodeResult] = {}
        deselected: set[str] = set()
        self._audit("blueprint_start", task=task, blueprint=self.blueprint.name)

        for level in self.blueprint.topo_levels():
            runnable = []
            for node_id in level:
                node = self.blueprint.nodes[node_id]
                upstream = self.blueprint.upstream(node_id)
                upstream_results = [results[u] for u in upstream]
                if node_id in deselected:
                    results[node_id] = NodeResult(node_id, "skipped")
                    self._audit("node_skipped", node=node_id, reason="deselected")
                elif node.kind == NodeKind.JOIN and upstream:
                    if self._join_admits(node, upstream_results):
                        runnable.append(node)
                    else:
                        results[node_id] = NodeResult(node_id, "skipped")
                        self._audit("node_skipped", node=node_id, reason="quorum not met")
                elif upstream and all(r.status != "done" for r in upstream_results):
                    results[node_id] = NodeResult(node_id, "skipped")
                    self._audit("node_skipped", node=node_id, reason="no done upstream")
                else:
                    runnable.append(node)
            if not runnable:
                continue
            level_results = await asyncio.gather(
                *(self._run_node(node, task, results) for node in runnable)
            )
            for result in level_results:
                results[result.node_id] = result
                node = self.blueprint.nodes[result.node_id]
                if node.kind in (NodeKind.CONDITION, NodeKind.MANAGER):
                    chosen = set(result.branches)
                    for edge in self.blueprint.downstream_edges(result.node_id):
                        if edge.target not in chosen:
                            deselected.add(edge.target)

        report = BlueprintReport(
            task=task, results=results, usage=self.usage, attempts=self.attempts
        )
        self._audit(
            "blueprint_done",
            blueprint=self.blueprint.name,
            done=sum(1 for r in results.values() if r.status == "done"),
            skipped=sum(1 for r in results.values() if r.status == "skipped"),
            rejected=sum(1 for r in results.values() if r.status == "rejected"),
        )
        return report

    # ------------------------------------------------------------------
    # node execution
    # ------------------------------------------------------------------

    async def _run_node(
        self, node: Node, task: str, results: dict[str, NodeResult]
    ) -> NodeResult:
        inputs = self._collect_inputs(node, results)
        self._audit("node_start", node=node.id, node_kind=node.kind.value)
        if node.kind in (NodeKind.AGENT, NodeKind.SLOT):
            result = await self._run_agent(node, task, inputs)
        elif node.kind in (NodeKind.AGGREGATE, NodeKind.JOIN):
            result = await self._run_aggregate(node, inputs)
        elif node.kind == NodeKind.CONDITION:
            result = await self._run_router(node, inputs, single=True)
        elif node.kind == NodeKind.MANAGER:
            result = await self._run_router(node, inputs, single=False)
        elif node.kind == NodeKind.APPROVAL:
            result = await self._run_approval(node, inputs)
        elif node.kind == NodeKind.LOOP:
            result = await self._run_loop(node, task, inputs)
        elif node.kind == NodeKind.WHILE:
            result = await self._run_while(node, task, inputs)
        elif node.kind == NodeKind.COMMAND:
            result = await self._run_command(node, inputs)
        else:  # pragma: no cover - exhaustive enum
            raise ValueError(f"unknown node kind: {node.kind}")
        self._audit("node_done", node=node.id, status=result.status)
        return result

    def _collect_inputs(self, node: Node, results: dict[str, NodeResult]) -> str:
        parts = []
        for upstream_id in self.blueprint.upstream(node.id):
            upstream = results.get(upstream_id)
            if upstream and upstream.status == "done" and upstream.output:
                label = self.blueprint.nodes[upstream_id].label or upstream_id
                parts.append(f"[{label}]\n{upstream.output}")
        return "\n\n".join(parts)

    async def _complete(self, prompt: str, system: str, node: Node | None = None) -> str:
        provider = self._provider_for(node) if node is not None else self.provider
        response = await provider.complete(
            messages=[Message.user(prompt)], system=system
        )
        self.usage = self.usage + response.usage
        return response.content.strip()

    async def _run_agent(self, node: Node, task: str, inputs: str) -> NodeResult:
        prompt = _render(node.prompt, task, inputs)
        system = f"You are node '{node.label or node.id}' in a workflow. Do your part well."
        output = await self._complete(prompt, system, node)
        return NodeResult(node.id, "done", output)

    async def _run_aggregate(self, node: Node, inputs: str) -> NodeResult:
        if not node.prompt:
            return NodeResult(node.id, "done", inputs)
        output = await self._complete(
            node.prompt.replace("{inputs}", inputs) or AGGREGATE_PROMPT.format(inputs=inputs),
            "You merge parallel results.",
            node,
        )
        return NodeResult(node.id, "done", output)

    async def _run_loop(self, node: Node, task: str, inputs: str) -> NodeResult:
        """Finite loop: repeat own task, collecting every iteration's result."""
        max_iterations = int(node.config.get("max_iterations", 3))
        results: list[str] = []
        last = inputs
        for i in range(1, max_iterations + 1):
            prompt = _render(node.prompt, task, last)
            prompt += f"\n\n(This is iteration {i}/{max_iterations}.)"
            last = await self._complete(
                prompt, f"You are loop node '{node.label or node.id}'.", node
            )
            results.append(last)
            self.attempts[node.id] = i
        joined = "\n\n".join(
            f"[iteration {i}]\n{r}" for i, r in enumerate(results, start=1)
        )
        return NodeResult(node.id, "done", joined)

    async def _run_while(self, node: Node, task: str, inputs: str) -> NodeResult:
        """Bounded conditional loop: LLM decides CONTINUE/DONE each round."""
        max_iterations = int(node.config.get("max_iterations", 5))
        results: list[str] = []
        last = inputs
        for i in range(1, max_iterations + 1):
            prompt = _render(node.prompt, task, last)
            prompt += f"\n\n(This is iteration {i}/{max_iterations}.)"
            last = await self._complete(
                prompt, f"You are loop node '{node.label or node.id}'.", node
            )
            results.append(last)
            self.attempts[node.id] = i
            verdict = await self._complete(
                WHILE_CONTINUE_PROMPT.format(goal=task, iteration=i, last=last),
                "You control a bounded loop.",
                node,
            )
            if not verdict.upper().startswith("CONTINUE"):
                break
        joined = "\n\n".join(
            f"[iteration {i}]\n{r}" for i, r in enumerate(results, start=1)
        )
        return NodeResult(node.id, "done", joined)

    async def _run_command(self, node: Node, inputs: str) -> NodeResult:
        """Deterministic command: run an allowlisted argv, no shell."""
        argv = node.config.get("argv") or []
        if not argv:
            return NodeResult(node.id, "rejected", "command node has no argv")
        executable = argv[0]
        if executable not in self.command_allowlist:
            return NodeResult(
                node.id,
                "rejected",
                f"command {executable!r} not in allowlist "
                f"({sorted(self.command_allowlist) or 'empty — all denied'})",
            )
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            timeout = float(node.config.get("timeout", 60))
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(inputs.encode() if inputs else None), timeout
            )
        except (OSError, asyncio.TimeoutError) as exc:
            return NodeResult(node.id, "rejected", f"command failed: {exc}")
        output = stdout.decode(errors="replace").strip()
        if proc.returncode != 0:
            err = stderr.decode(errors="replace").strip()
            return NodeResult(
                node.id, "rejected",
                f"exit {proc.returncode}: {err or output}",
            )
        return NodeResult(node.id, "done", output or f"(exit 0, no output)")

    async def _run_router(self, node: Node, inputs: str, single: bool) -> NodeResult:
        edges = self.blueprint.downstream_edges(node.id)
        if not edges:
            return NodeResult(node.id, "done", inputs)
        branch_lines = []
        for edge in edges:
            name = edge.label or self.blueprint.nodes[edge.target].label or edge.target
            branch_lines.append(f"- {name} (id: {edge.target})")
        template = CONDITION_PROMPT if single else MANAGER_PROMPT
        prompt = template.format(inputs=inputs, branches="\n".join(branch_lines))
        reply = await self._complete(prompt, "You route workflow branches.", node)
        chosen = [
            edge.target
            for edge in edges
            if (edge.label and edge.label in reply) or edge.target in reply
        ]
        if not chosen:  # LLM answered garbage: keep the flow alive
            chosen = [edges[0].target]
        if single:
            chosen = chosen[:1]
        return NodeResult(node.id, "done", inputs, branches=chosen)

    async def _run_approval(self, node: Node, inputs: str) -> NodeResult:
        if self.approval_handler is None:
            return NodeResult(node.id, "done", inputs)
        decision = self.approval_handler(node, inputs)
        if hasattr(decision, "__await__"):
            decision = await decision
        if not decision.approved:
            return NodeResult(node.id, "rejected", inputs)
        return NodeResult(node.id, "done", decision.reply or inputs)

    def _audit(self, kind: str, **detail: Any) -> None:
        if self.audit is not None:
            self.audit.record(kind, **detail)
