"""Command-line interface for codeagent."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt

from codeagent.core.agent import DEFAULT_SYSTEM_PROMPT, Agent, AgentEvent, MaxIterationsError
from codeagent.core.budget import Budget, BudgetExceededError
from codeagent.llm.registry import list_providers
from codeagent.llm.aggregate import parse_provider_spec
from codeagent.mcp import MCPManager, load_mcp_config
from codeagent.security.policy import (
    ApprovalDecision,
    PermissionPolicy,
    RiskLevel,
)
from codeagent.harness import discover_harnesses
from codeagent.leader import Leader, ProgressBoard, RunArchive, WorkerConfig, load_workers_yaml
from codeagent.log import get_logger, setup_logging, tail_log
from codeagent.releases import RELEASES, changelog_text, latest
from codeagent.settings import Settings

cli_log = get_logger("cli")
from codeagent.skills import SkillEvolver, SkillLibrary
from codeagent.tools import ToolRegistry, default_tools, web_tools
from codeagent.tools.ocr import ocr_tools
from codeagent.voice import (
    EMOTION_PROMPT_SUFFIX,
    EdgeTTSProvider,
    VoiceChatLoop,
    WhisperASRProvider,
    record_until_enter,
)

app = typer.Typer(
    name="codeagent",
    help="A professional code development agent with multi-model support.",
    no_args_is_help=True,
)
console = Console()

_RISK_STYLE = {
    RiskLevel.WRITE: "yellow",
    RiskLevel.EXECUTE: "red",
    RiskLevel.DESTRUCTIVE: "bold red",
}


def _make_event_handler(verbose: bool):
    def handler(event: AgentEvent) -> None:
        if event.type == "tool_call":
            console.print(f"[cyan]→ tool:[/cyan] {event.data.name} [dim]{event.data.arguments}[/dim]")
        elif event.type == "tool_result" and verbose:
            preview = event.data.content[:500]
            style = "red" if event.data.is_error else "green"
            console.print(Panel(preview, title="result", border_style=style))
        elif event.type == "error":
            console.print(f"[red]error:[/red] {event.data}")
        elif event.type == "skill_evolved":
            console.print(f"[magenta]✦ skill evolved:[/magenta] {event.data.name}")

    return handler


def _make_approval_handler():
    def handler(call, risk: RiskLevel) -> ApprovalDecision:
        style = _RISK_STYLE.get(risk, "yellow")
        console.print(f"[{style}]⚠ approval needed:[/{style}] {call.name} [dim](risk: {risk.name})[/dim]")
        preview = json.dumps(call.arguments, ensure_ascii=False)
        console.print(f"[dim]{preview[:300]}[/dim]")
        choice = Prompt.ask(
            "Allow? [bold]y[/bold]=yes, [bold]n[/bold]=no, [bold]a[/bold]=always allow this tool",
            choices=["y", "n", "a"],
            default="n",
        )
        if choice == "y":
            return ApprovalDecision.APPROVE
        if choice == "a":
            return ApprovalDecision.ALWAYS_ALLOW
        return ApprovalDecision.DENY

    return handler


def _build_policy(auto_yes: bool) -> PermissionPolicy:
    if auto_yes:
        return PermissionPolicy.permissive()
    return PermissionPolicy(
        auto_approve_up_to=RiskLevel.READ_ONLY,
        handler=_make_approval_handler(),
    )


def _build_provider(
    provider: str,
    model: str | None,
    api_key: str | None,
    base_url: str | None,
    strategy: str = "fallback",
):
    provider_kwargs = {"api_key": api_key, "base_url": base_url}
    provider_kwargs = {k: v for k, v in provider_kwargs.items() if v is not None}
    if model:
        provider_kwargs["model"] = model
    return parse_provider_spec(provider, strategy=strategy, **provider_kwargs)


def _build_agent(
    provider: str,
    model: str | None,
    api_key: str | None,
    base_url: str | None,
    root: Path,
    max_iterations: int,
    verbose: bool,
    auto_yes: bool,
    budget_tokens: int | None,
    registry: ToolRegistry,
    skills: SkillLibrary | None = None,
    skill_evolver: SkillEvolver | None = None,
    strategy: str = "fallback",
) -> Agent:
    budget = Budget(max_total_tokens=budget_tokens) if budget_tokens else None
    from codeagent.skills.runtime import workspace_skill_hints

    return Agent(
        provider=_build_provider(provider, model, api_key, base_url, strategy),
        tools=registry,
        max_iterations=max_iterations,
        permissions=_build_policy(auto_yes),
        budget=budget,
        skills=skills,
        settings=Settings.load(),  # host-wide personalization, every chat
        skill_evolver=skill_evolver,
        on_event=_make_event_handler(verbose),
        workspace_hints=workspace_skill_hints(root),
    )


_DEFAULT_SKILLS_DIR = Path("~/.codeagent/skills")


def _build_skills(
    skills_dir: Path | None,
    evolve: bool,
    provider: str,
    model: str | None,
    api_key: str | None,
    base_url: str | None,
) -> tuple[SkillLibrary | None, SkillEvolver | None]:
    """Load a skill library (and optional evolver) from --skills/--evolve.

    Falls back to ~/.codeagent/skills when it exists, so evolved skills are
    picked up automatically in later sessions.
    """
    from codeagent.videoops import load_all_skills

    extra = skills_dir or (
        _DEFAULT_SKILLS_DIR if _DEFAULT_SKILLS_DIR.expanduser().is_dir() else None
    )
    library = load_all_skills(*([extra] if extra is not None else []))
    directory = extra or _DEFAULT_SKILLS_DIR
    if not len(library):
        return None, None
    evolver = None
    if evolve:
        evolver = SkillEvolver(
            provider=_build_provider(provider, model, api_key, base_url),
            library=library,
            directory=directory,
        )
    return library, evolver


def _register_workspace_tools(registry: ToolRegistry) -> None:
    from codeagent.knowledge.tools import knowledge_tools
    from codeagent.videoops.tools import video_ops_tools

    for tool in knowledge_tools() + video_ops_tools():
        registry.register(tool)


@app.command()
def run(
    task: str = typer.Argument(..., help="The coding task for the agent to perform."),
    provider: str = typer.Option("anthropic", "--provider", "-p", help=f"LLM provider ({', '.join(list_providers())}); comma-separate for aggregation, e.g. ollama,openrouter."),
    model: str | None = typer.Option(None, "--model", "-m", help="Model name (provider default if omitted)."),
    api_key: str | None = typer.Option(None, "--api-key", envvar="CODEAGENT_API_KEY", help="API key (defaults to provider env var)."),
    base_url: str | None = typer.Option(None, "--base-url", help="Custom API base URL."),
    strategy: str = typer.Option("fallback", "--strategy", help="Aggregation strategy for comma-separated providers: fallback | round-robin."),
    root: Path = typer.Option(Path.cwd(), "--root", "-r", help="Workspace root the agent may touch."),
    max_iterations: int = typer.Option(50, "--max-iterations", help="Safety cap on model/tool round-trips."),
    budget: int | None = typer.Option(None, "--budget", help="Max total tokens (input+output), sub-agents included."),
    mcp_config: Path | None = typer.Option(None, "--mcp-config", help="Path to a Claude-style MCP servers JSON file."),
    web: bool = typer.Option(False, "--web", help="Enable web scraping tools (web_fetch / web_scrape)."),
    ocr: bool = typer.Option(False, "--ocr", help="Enable the OCR tool (image text extraction)."),
    skills_dir: Path | None = typer.Option(None, "--skills", help="Directory of SKILL.md packs to load (default: ~/.codeagent/skills if present)."),
    evolve: bool = typer.Option(False, "--evolve", help="Self-evolution: distill each finished task into a reusable skill."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Auto-approve all tool calls, including destructive ones."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show full tool results."),
) -> None:
    """Run the agent on a single task and print the final answer."""
    setup_logging()
    cli_log.info("command=run provider=%s model=%s root=%s task=%.120r", provider, model, root, task)

    async def _run() -> None:
        registry = default_tools(root)
        _register_workspace_tools(registry)
        if web:
            for tool in web_tools():
                registry.register(tool)
        if ocr:
            for tool in ocr_tools():
                registry.register(tool)
        skills, evolver = _build_skills(skills_dir, evolve, provider, model, api_key, base_url)
        mcp_configs = load_mcp_config(mcp_config) if mcp_config else []
        async with MCPManager(mcp_configs) as mcp:
            for tool in mcp.tools():
                registry.register(tool)
            agent = _build_agent(
                provider, model, api_key, base_url, root,
                max_iterations, verbose, yes, budget, registry,
                skills=skills, skill_evolver=evolver, strategy=strategy,
            )
            try:
                answer = await agent.run(task)
            except (MaxIterationsError, BudgetExceededError) as exc:
                cli_log.error("run aborted: %s", exc)
                console.print(f"[red]{exc}[/red]")
                raise typer.Exit(code=1)
        console.print(Markdown(answer))
        console.print(
            f"[dim]tokens: {agent.usage.input_tokens} in / {agent.usage.output_tokens} out[/dim]"
        )

    asyncio.run(_run())


@app.command()
def chat(
    provider: str = typer.Option("anthropic", "--provider", "-p", help=f"LLM provider ({', '.join(list_providers())}); comma-separate for aggregation, e.g. ollama,openrouter."),
    model: str | None = typer.Option(None, "--model", "-m", help="Model name (provider default if omitted)."),
    api_key: str | None = typer.Option(None, "--api-key", envvar="CODEAGENT_API_KEY", help="API key (defaults to provider env var)."),
    base_url: str | None = typer.Option(None, "--base-url", help="Custom API base URL."),
    strategy: str = typer.Option("fallback", "--strategy", help="Aggregation strategy for comma-separated providers: fallback | round-robin."),
    root: Path = typer.Option(Path.cwd(), "--root", "-r", help="Workspace root the agent may touch."),
    max_iterations: int = typer.Option(50, "--max-iterations", help="Safety cap per turn."),
    budget: int | None = typer.Option(None, "--budget", help="Max total tokens (input+output), sub-agents included."),
    mcp_config: Path | None = typer.Option(None, "--mcp-config", help="Path to a Claude-style MCP servers JSON file."),
    web: bool = typer.Option(False, "--web", help="Enable web scraping tools (web_fetch / web_scrape)."),
    ocr: bool = typer.Option(False, "--ocr", help="Enable the OCR tool (image text extraction)."),
    skills_dir: Path | None = typer.Option(None, "--skills", help="Directory of SKILL.md packs to load (default: ~/.codeagent/skills if present)."),
    evolve: bool = typer.Option(False, "--evolve", help="Self-evolution: distill each finished task into a reusable skill."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Auto-approve all tool calls, including destructive ones."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show full tool results."),
    emotion: bool = typer.Option(False, "--emotion", help="Emotional-companion mode: replies carry an emotion tag."),
    voice: bool = typer.Option(False, "--voice", help="Speak replies aloud with the free edge-tts voice pack (implies --emotion)."),
    voice_name: str | None = typer.Option(None, "--voice-name", help="TTS voice: preset (xiaoxiao/xiaoyi/yunxi/yunjian/xiaochen/hsiaochen/hsiaoyu/yunjhe) or full edge-tts voice ID."),
    mic: bool = typer.Option(False, "--mic", help="Full voice loop: push-to-talk microphone input via local Whisper ASR."),
    mic_model: str = typer.Option("base", "--mic-model", help="Whisper model size: tiny/base/small/medium/large-v3."),
    memory: bool = typer.Option(False, "--memory", help="Persist long-term memory across sessions (~/.codeagent/memory.json)."),
) -> None:
    """Start an interactive multi-turn chat session with the agent."""
    setup_logging()
    cli_log.info("command=chat provider=%s model=%s root=%s", provider, model, root)

    async def _chat() -> None:
        registry = default_tools(root)
        _register_workspace_tools(registry)
        if web:
            for tool in web_tools():
                registry.register(tool)
        if ocr:
            for tool in ocr_tools():
                registry.register(tool)
        skills, evolver = _build_skills(skills_dir, evolve, provider, model, api_key, base_url)
        memory_store = None
        if memory:
            from codeagent.memory import LocalMemoryStore, memory_tools

            memory_store = LocalMemoryStore("~/.codeagent/memory.json")
            for tool in memory_tools(memory_store):
                registry.register(tool)
        mcp_configs = load_mcp_config(mcp_config) if mcp_config else []
        async with MCPManager(mcp_configs) as mcp:
            for tool in mcp.tools():
                registry.register(tool)
            agent = _build_agent(
                provider, model, api_key, base_url, root,
                max_iterations, verbose, yes, budget, registry,
                skills=skills, skill_evolver=evolver, strategy=strategy,
            )
            agent.memory = memory_store
            if emotion or voice:
                agent.system_prompt = DEFAULT_SYSTEM_PROMPT + EMOTION_PROMPT_SUFFIX

            tts = None
            if voice or mic:
                if voice_name:
                    # 用户指定音色后固定使用，情绪只调节语速/音调
                    tts = EdgeTTSProvider(voice=voice_name, emotion_voices=False)
                else:
                    tts = EdgeTTSProvider()
            asr = WhisperASRProvider(model_size=mic_model) if mic else None
            loop = VoiceChatLoop(agent, tts=tts)

            mode = []
            if emotion or voice or mic:
                mode.append("emotion")
            if voice or mic:
                mode.append("voice")
            if mic:
                mode.append("mic")
            if memory:
                mode.append("memory")
            suffix = f" ({', '.join(mode)})" if mode else ""
            console.print(
                f"[bold]codeagent chat{suffix}[/bold] — type 'exit' or Ctrl-C to quit, 'reset' to clear history"
            )
            while True:
                try:
                    if mic:
                        console.print("[dim]按 Enter 开始说话，说完再按 Enter[/dim]")
                        audio = await record_until_enter()
                        user_input = await asr.transcribe(audio)
                        if not user_input.strip():
                            console.print("[dim](没听清，请再说一次)[/dim]")
                            continue
                        console.print(f"[bold blue]you>[/bold blue] {user_input}")
                    else:
                        user_input = console.input("[bold blue]you> [/bold blue]")
                except (EOFError, KeyboardInterrupt):
                    console.print("\nbye")
                    return
                except RuntimeError as exc:
                    console.print(f"[red]{exc}[/red]")
                    return
                if not user_input.strip():
                    continue
                if user_input.strip() == "reset":
                    agent.reset()
                    console.print("[dim]history cleared[/dim]")
                    continue
                try:
                    turn = await loop.turn(user_input)
                except (MaxIterationsError, BudgetExceededError) as exc:
                    console.print(f"[red]{exc}[/red]")
                    continue
                if turn is None:
                    return
                if emotion or voice:
                    console.print(f"[magenta]({turn.emotion.value})[/magenta]")
                console.print(Markdown(turn.reply_text))

    asyncio.run(_chat())


@app.command()
def lead(
    workers_file: Path | None = typer.Option(None, "--workers", "-w", help="Workers YAML roster (name/provider/model/description per worker)."),
    provider: str = typer.Option("anthropic", "--provider", "-p", help=f"Leader LLM provider ({', '.join(list_providers())}); comma-separate for aggregation."),
    model: str | None = typer.Option(None, "--model", "-m", help="Leader model name."),
    api_key: str | None = typer.Option(None, "--api-key", envvar="CODEAGENT_API_KEY", help="API key (defaults to provider env var)."),
    base_url: str | None = typer.Option(None, "--base-url", help="Custom API base URL."),
    strategy: str = typer.Option("fallback", "--strategy", help="Aggregation strategy for comma-separated providers: fallback | round-robin."),
    root: Path = typer.Option(Path.cwd(), "--root", "-r", help="Project root the workers operate on."),
    max_iterations: int = typer.Option(30, "--max-iterations", help="Safety cap per worker task."),
    web: bool = typer.Option(False, "--web", help="Give workers web scraping tools."),
    ocr: bool = typer.Option(False, "--ocr", help="Give workers the OCR tool."),
    skills_dir: Path | None = typer.Option(None, "--skills", help="Skill packs directory (default: ~/.codeagent/skills if present)."),
    voice: bool = typer.Option(False, "--voice", help="Speak the leader's replies aloud (edge-tts)."),
    voice_name: str | None = typer.Option(None, "--voice-name", help="TTS voice preset or full edge-tts voice ID."),
    mic: bool = typer.Option(False, "--mic", help="Voice commands via push-to-talk microphone (local Whisper ASR)."),
    mic_model: str = typer.Option("base", "--mic-model", help="Whisper model size."),
    no_escalate: bool = typer.Option(False, "--no-escalate", help="Disable escalation to external agent platforms on worker failure."),
) -> None:
    """Lead a team of worker models: voice/text commands, live progress."""
    setup_logging()
    cli_log.info("command=lead provider=%s root=%s workers_file=%s", provider, root, workers_file)

    async def _lead() -> None:
        if workers_file:
            roster = load_workers_yaml(workers_file)
        else:
            roster = [WorkerConfig(name="worker", provider=provider, model=model, base_url=base_url, api_key=api_key)]
        skills, _ = _build_skills(skills_dir, False, provider, model, api_key, base_url)

        def registry_factory() -> ToolRegistry:
            registry = default_tools(root)
            _register_workspace_tools(registry)
            if web:
                for tool in web_tools():
                    registry.register(tool)
            if ocr:
                for tool in ocr_tools():
                    registry.register(tool)
            return registry

        board = ProgressBoard(
            on_change=lambda r: console.print(
                f"[dim]· {r.title[:40]} → {r.status}（{r.worker}）[/dim]"
            )
        )
        harnesses = discover_harnesses()
        leader = Leader(
            provider=_build_provider(provider, model, api_key, base_url, strategy),
            workers=roster,
            root=root,
            skills=skills,
            registry_factory=registry_factory,
            board=board,
            max_iterations=max_iterations,
            harnesses=harnesses,
            escalate=not no_escalate,
            archive=RunArchive(),
            settings=Settings.load(),
        )

        tts = None
        if voice or mic:
            tts = EdgeTTSProvider(voice=voice_name, emotion_voices=False) if voice_name else EdgeTTSProvider()
        asr = WhisperASRProvider(model_size=mic_model) if mic else None

        names = ", ".join(f"{w.name}({w.provider})" for w in roster)
        console.print(f"[bold]codeagent lead[/bold] — 工人: {names}")
        if harnesses:
            available = ", ".join(h.name for h in harnesses)
            console.print(f"[dim]外部增援平台: {available}（工人卡住时可呼叫/失败自动升级）[/dim]")
        console.print(f"[dim]运行记录本地存档: ~/.codeagent/runs/[/dim]")
        console.print("[dim]下达命令即可；问“进度”随时查看进展；'exit' 退出[/dim]")
        while True:
            try:
                if mic:
                    console.print("[dim]按 Enter 开始说话，说完再按 Enter[/dim]")
                    audio = await record_until_enter()
                    user_input = await asr.transcribe(audio)
                    if not user_input.strip():
                        console.print("[dim](没听清，请再说一次)[/dim]")
                        continue
                    console.print(f"[bold blue]boss>[/bold blue] {user_input}")
                else:
                    user_input = console.input("[bold blue]boss> [/bold blue]")
            except (EOFError, KeyboardInterrupt):
                console.print("\nbye")
                return
            except RuntimeError as exc:
                console.print(f"[red]{exc}[/red]")
                return
            if not user_input.strip():
                continue
            reply = await leader.command(user_input)
            console.print(Markdown(reply))
            if tts is not None:
                try:
                    audio_path = await tts.synthesize(reply[:600])
                    from codeagent.voice import play_audio

                    await play_audio(audio_path)
                except Exception as exc:
                    console.print(f"[dim](语音播报失败: {exc})[/dim]")

    asyncio.run(_lead())


settings_app = typer.Typer(
    name="settings",
    help="Host-wide personalization applied to every chat on this machine.",
    no_args_is_help=True,
)
app.add_typer(settings_app, name="settings")


@settings_app.command("show")
def settings_show() -> None:
    """Show version info and the current personalization settings."""
    rel = latest()
    console.print(f"[bold]codeagent[/bold] v{rel.version}（{rel.date}）")
    console.print(f"[dim]本次更新：{'；'.join(rel.highlights)}[/dim]")
    console.print(f"[dim]日志：{Path('~/.codeagent/logs/codeagent.log').expanduser()}[/dim]")
    settings = Settings.load()
    if settings.is_empty():
        console.print("[dim]（个性化未设置）用 codeagent settings set 来配置。[/dim]")
        return
    console.print(Panel(settings.prompt_block(), title="个性化设置", border_style="cyan"))
    console.print("[dim]存储于 ~/.codeagent/settings.json[/dim]")


@settings_app.command("set")
def settings_set(
    nickname: str | None = typer.Option(None, "--nickname", "-n", help="怎么称呼你（如：石头）。"),
    language: str | None = typer.Option(None, "--language", "-l", help="首选回复语言（如：中文）。"),
    instructions: str | None = typer.Option(None, "--instructions", "-i", help="额外行为说明（如：回答先给结论，再给细节）。"),
    context: str | None = typer.Option(None, "--context", "-c", help="用户与主机上下文（如：M4 Mac，项目在 ~/code）。"),
) -> None:
    """Set personalization fields (only provided fields are updated)."""
    settings = Settings.load()
    if nickname is not None:
        settings.nickname = nickname
    if language is not None:
        settings.language = language
    if instructions is not None:
        settings.instructions = instructions
    if context is not None:
        settings.context = context
    path = settings.save()
    console.print(f"[green]已保存[/green] → {path}")
    console.print(Panel(settings.prompt_block() or "（空）", title="当前个性化", border_style="cyan"))


@settings_app.command("clear")
def settings_clear() -> None:
    """Remove all personalization settings."""
    if Settings.clear():
        console.print("[green]已清除个性化设置。[/green]")
    else:
        console.print("[dim]本来就没有设置。[/dim]")


@app.command("desktop")
def desktop_cmd(
    root: Path = typer.Option(Path.cwd(), "--root", "-r", help="Workspace root the agent may touch."),
) -> None:
    """Launch the desktop UI (chat window, settings panel, version info)."""
    from codeagent.desktop import run_desktop

    raise typer.Exit(code=run_desktop(root=root))


@app.command("version")
def version_cmd() -> None:
    """Show the current version and what changed in this release."""
    rel = latest()
    console.print(f"[bold]codeagent[/bold] v{rel.version}（{rel.date}）")
    for highlight in rel.highlights:
        console.print(f"  · {highlight}")
    console.print("[dim]完整历史：codeagent changelog[/dim]")


@app.command("changelog")
def changelog_cmd() -> None:
    """Show the full per-release update history."""
    console.print(Markdown(changelog_text()))


@app.command("logs")
def logs_cmd(
    lines: int = typer.Option(50, "--lines", "-n", help="Number of recent log lines to show."),
) -> None:
    """Show recent run logs (~/.codeagent/logs/codeagent.log)."""
    path = setup_logging()
    entries = tail_log(lines)
    if not entries:
        console.print(f"[dim]暂无日志。日志文件：{path}[/dim]")
        return
    console.print(f"[dim]{path}（最近 {len(entries)} 行）[/dim]")
    for line in entries:
        console.print(line, highlight=False)


if __name__ == "__main__":
    app()
