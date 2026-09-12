"""JS bridge for the desktop UI.

A ``DesktopAPI`` instance is exposed to the webview's JavaScript as
``pywebview.api.*``. Python pushes live updates back via
``window.evaluate_js``. No web server involved.

UI preferences persist to ``~/.codeagent/desktop.json``; personalization
reuses the host-wide ``Settings`` store.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from codeagent.core.agent import Agent, AgentEvent
from codeagent.core.budget import Budget, BudgetExceededError
from codeagent.memory.compact import CompactionConfig, ConversationCompactor
from codeagent.desktop.activity import (
    LearningStore,
    learn_now,
    log_activity,
    read_activity,
    record_feedback,
)
from codeagent.desktop.automation import Workflow, WorkflowRunner, WorkflowStep, WorkflowStore
from codeagent.desktop.cron import PRESETS, CronJob, CronScheduler, CronStore, next_run_hint
from codeagent.desktop.evolution import (
    PHASES,
    EvolutionStore,
    run_evolution,
    set_patch,
)
from codeagent.desktop.models import (
    ApiModel,
    Mixture,
    ModelAssets,
    OllamaEndpoint,
    build_active_provider,
    delete_ollama_model,
    delete_secret,
    detect_service,
    load_secret,
    mask_secret,
    normalize_endpoint_base,
    probe_all,
    probe_endpoint_info,
    pull_ollama_model,
    running_models,
    save_secret,
    set_model_loaded,
    test_provider,
)
from codeagent.desktop.permissions import (
    CAPABILITIES,
    LEVELS,
    Confirmer,
    append_audit,
    build_policy,
    load_levels,
    read_audit,
    save_levels,
)
from codeagent.desktop.projects import (
    CATEGORIES,
    DEFAULT_BASE,
    ProjectStore,
    append_message,
    ingest_file,
    list_conversations,
    list_files,
    load_conversation,
    new_conversation_id,
)
from codeagent.desktop.router import (
    FREE_ROUTE_LABEL,
    FREE_ROUTE_REF,
    RouteRule,
    RouterStore,
    is_free_route,
    route_message,
)
from codeagent.llm.aggregate import AggregateProvider, parse_provider_spec
from codeagent.llm.openai import is_transient_serving_error
from codeagent.llm.registry import list_providers
from codeagent.log import get_logger, setup_logging, tail_log
from codeagent.releases import changelog_text, latest
from codeagent.settings import Settings
from codeagent.desktop.privacy import PRIVACY_VERSION, privacy_document
from codeagent.browser.engine import InternalBrowser
from codeagent.browser.webview import WebviewHost
from codeagent.tools import default_tools
from codeagent.tools.browser import BrowserTool

log = get_logger("desktop")

DESKTOP_CONFIG_PATH = Path("~/.codeagent/desktop.json")
DEFAULT_SKILLS_DIR = Path("~/.codeagent/skills")
MEMORY_PATH = Path("~/.codeagent/memory.json")
# Per-task cap for desktop chat. Soft: wrap up instead of crashing the UI.
# 50 万在思考强度=高 + 读大量文件时一轮就会顶满（见 2026-09-10 日志）。
DESKTOP_TOKEN_BUDGET = 2_000_000
DESKTOP_MAX_ITERATIONS_DEFAULT = 80
DESKTOP_MAX_ITERATIONS_MIN = 10
DESKTOP_MAX_ITERATIONS_MAX = 300
# Back-compat alias used by older tests / docs.
DESKTOP_MAX_ITERATIONS = DESKTOP_MAX_ITERATIONS_DEFAULT


def clamp_max_iterations(value: Any, default: int = DESKTOP_MAX_ITERATIONS_DEFAULT) -> int:
    """Keep tool-round trips in [10, 300]."""
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return max(DESKTOP_MAX_ITERATIONS_MIN, min(DESKTOP_MAX_ITERATIONS_MAX, n))
_SEED_MAX_MSGS = 6
_SEED_MAX_CHARS = 1200


def _format_conv_seed(msgs: list[dict[str, Any]]) -> str:
    """Prior turns as compact context — long file dumps must not refill the prompt."""
    parts: list[str] = []
    for m in msgs[-_SEED_MAX_MSGS:]:
        role = "用户" if m.get("role") == "user" else "助手"
        body = (m.get("text") or "").strip()
        if len(body) > _SEED_MAX_CHARS:
            body = body[:_SEED_MAX_CHARS] + "…(已截断)"
        if body:
            parts.append(f"{role}：{body}")
    return "\n".join(parts)


def _macos_pasteboard_write(text: str) -> bool:
    """Write via NSPasteboard (works in signed .app; pbcopy may be off PATH)."""
    try:
        from AppKit import NSPasteboard, NSPasteboardTypeString

        board = NSPasteboard.generalPasteboard()
        board.clearContents()
        return bool(board.setString_forType_(text, NSPasteboardTypeString))
    except Exception:  # noqa: BLE001
        return False


def _macos_pasteboard_read() -> str | None:
    try:
        from AppKit import NSPasteboard, NSPasteboardTypeString

        value = NSPasteboard.generalPasteboard().stringForType_(NSPasteboardTypeString)
        if value is None:
            return None
        return str(value)
    except Exception:  # noqa: BLE001
        return None


def _win_clip_bin() -> str:
    root = os.environ.get("SystemRoot", r"C:\Windows")
    return str(Path(root) / "System32" / "clip.exe")


def _clipboard_copy(text: str) -> bool:
    """Write Unicode text to the OS clipboard."""
    import shutil
    import subprocess
    import sys

    data = text if isinstance(text, str) else str(text)
    try:
        if sys.platform == "darwin":
            if _macos_pasteboard_write(data):
                return True
            subprocess.run(
                ["/usr/bin/pbcopy"], input=data.encode("utf-8"),
                check=True, capture_output=True, timeout=5,
            )
            return True
        if sys.platform == "win32":
            # clip.exe expects UTF-16LE; UTF-8 Chinese becomes garbage.
            try:
                subprocess.run(
                    [_win_clip_bin()], input=data.encode("utf-16le"),
                    check=True, capture_output=True, timeout=5,
                )
                return True
            except (subprocess.SubprocessError, OSError, FileNotFoundError):
                ps = (
                    "[Console]::InputEncoding = New-Object System.Text.UTF8Encoding $false; "
                    "$t = [Console]::In.ReadToEnd(); Set-Clipboard -Value $t"
                )
                subprocess.run(
                    ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                    input=data.encode("utf-8"),
                    check=True, capture_output=True, timeout=8,
                )
                return True
        for cmd in (
            ["wl-copy"],
            ["xclip", "-selection", "clipboard"],
            ["xsel", "--clipboard", "--input"],
        ):
            if shutil.which(cmd[0]) is None:
                continue
            subprocess.run(
                cmd, input=data.encode("utf-8"),
                check=True, capture_output=True, timeout=5,
            )
            return True
        return False
    except (subprocess.SubprocessError, OSError, FileNotFoundError):
        return False


def _clipboard_paste() -> str:
    """Read Unicode text from the OS clipboard."""
    import shutil
    import subprocess
    import sys

    try:
        if sys.platform == "darwin":
            got = _macos_pasteboard_read()
            if got is not None:
                return got
            res = subprocess.run(
                ["/usr/bin/pbpaste"], check=True, capture_output=True, timeout=5,
            )
            return res.stdout.decode("utf-8", errors="replace")
        if sys.platform == "win32":
            ps = (
                "[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false; "
                "Get-Clipboard -Raw"
            )
            res = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                check=True, capture_output=True, timeout=8,
            )
            return res.stdout.decode("utf-8", errors="replace").replace("\r\n", "\n")
        for cmd in (
            ["wl-paste"],
            ["xclip", "-selection", "clipboard", "-o"],
            ["xsel", "--clipboard", "--output"],
        ):
            if shutil.which(cmd[0]) is None:
                continue
            res = subprocess.run(cmd, check=True, capture_output=True, timeout=5)
            return res.stdout.decode("utf-8", errors="replace")
        return ""
    except (subprocess.SubprocessError, OSError, FileNotFoundError):
        return ""


@dataclass
class DesktopConfig:
    """Everything configurable from the UI."""

    provider: str = "ollama"
    model: str = ""
    api_key: str = ""
    base_url: str = ""
    strategy: str = "fallback"
    auto_yes: bool = False
    voice_enabled: bool = False
    voice_name: str = "edge-tw"
    voice_cute_tone: bool = True
    voice_pitch: int = -10
    voice_rate: int = -5
    # 陪伴型 AI（偏好设置页）
    companion_enabled: bool = False
    companion_preset: str = ""  # 预设 id，空=自定义
    companion_name: str = ""  # AI 自称 / 角色名
    companion_nature: str = ""  # 性格与说话方式
    theme: str = "dark"  # dark | light | auto（跟随系统）
    thinking: str = "medium"  # low | medium | high（思考强度）
    # 单次任务模型↔工具往返上限（偏好设置可调，10–300）
    max_iterations: int = DESKTOP_MAX_ITERATIONS_DEFAULT
    # JSON list of {"name","provider","model","description"} for leader mode
    workers_json: str = ""
    # Accepted privacy policy version (empty = never accepted)
    privacy_accepted_version: str = ""
    privacy_accepted_at: str = ""  # ISO timestamp when last accepted

    @classmethod
    def load(cls, path: Path | None = None) -> "DesktopConfig":
        path = Path(path or DESKTOP_CONFIG_PATH).expanduser()
        if not path.is_file():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return cls()
        known = {f for f in cls.__dataclass_fields__}
        cfg = cls(**{k: v for k, v in data.items() if k in known})
        cfg.max_iterations = clamp_max_iterations(cfg.max_iterations)
        return cfg

    def save(self, path: Path | None = None) -> None:
        path = Path(path or DESKTOP_CONFIG_PATH).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2),
                        encoding="utf-8")


class DesktopAPI:
    """Object exposed to JavaScript. All methods are callable from JS."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path.cwd() if root is None else Path(root)
        self.projects = ProjectStore.load()
        self._conv_id: str | None = None
        # 正式启动（未显式传入 root）时保证至少有一个项目，对话不会丢
        if root is None:
            self.projects.ensure_default()
        active_proj = self.projects.get(self.projects.active)
        if root is None and active_proj is not None:
            self.root = Path(active_proj.path)
        self.config = DesktopConfig.load()
        self.settings = Settings.load()
        self.assets = ModelAssets.load()
        self.router = RouterStore.load()
        self.perm_levels = load_levels()
        self.confirmer = Confirmer(lambda kind, data: self._push(kind, **data))
        self.workflows = WorkflowStore.load()
        self.evolution = EvolutionStore.load()
        self.cron_jobs = CronStore.load()
        self.runner = WorkflowRunner(self.workflows, self._run_workflow_step)
        self.scheduler = CronScheduler(
            self.cron_jobs,
            run_action=self._run_cron_action,
            evolution_enabled=lambda: self.evolution.settings.enabled,
            evolution_cron=lambda: self.evolution.settings.cron,
            run_evolution=lambda: self._run_evolution(manual=False),
        )
        self.scheduler.start()
        self._window: Any = None
        # 第二个独立对话窗口（B）：由 open_second_window() 在后台线程创建
        self._window_b: Any = None
        self._agent: Agent | None = None
        self._lock = threading.Lock()
        self._busy = False
        self._cancel = threading.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._attachments: list[dict[str, Any]] = []
        self._conv_seed: list[dict[str, Any]] = []
        # 第二对话进程（B）：独立并发，同一项目文件夹保留记录
        self._conv_id2: str | None = None
        self._agent2: Agent | None = None
        self._lock2 = threading.Lock()
        self._busy2 = False
        self._cancel2 = threading.Event()
        self._loop2: asyncio.AbstractEventLoop | None = None
        self._conv_seed2: list[dict[str, Any]] = []
        self._confirmer2 = Confirmer(lambda kind, data: self._push(kind, chan="B", **data))
        # 模型资产探测缓存：TTL 秒内不重复探测，避免来回切换页面卡死/识别慢
        self._assets_probe_cache: tuple[float, list[dict[str, Any]]] | None = None
        self._browser_host = WebviewHost(push=self._push)
        self._browser = InternalBrowser(host=self._browser_host)
        self._chat_browser_urls: list[str] = []
        self._voice_session = False
        self._native_listen = None
        setup_logging()

    # ------------------------------------------------------------------
    # push channel
    # ------------------------------------------------------------------

    def _push(self, kind: str, chan: str = "A", **data: Any) -> None:
        targets = []
        if self._window is not None:
            targets.append(self._window)
        if chan == "B" and self._window_b is not None:
            targets.append(self._window_b)  # 独立对话窗口也收 B 事件
        if not targets:
            return
        payload = json.dumps({"kind": kind, "chan": chan, **data}, ensure_ascii=False)
        # wrap in try — bad JS must never poison the bridge
        script = f"try{{window._onEvent({payload})}}catch(e){{}}"
        for win in targets:
            self._eval_js_fire_and_forget(win, script)

    def _eval_js_fire_and_forget(self, win: Any, script: str) -> None:
        """Push JS without waiting.

        pywebview's ``evaluate_js`` does ``callAfter`` + ``semaphore.acquire()``.
        Calling that from Speech / audio callbacks deadlocks the main run loop
        the moment recognition produces text — the window freezes until force-quit.
        """
        # FakeWindow / tests: direct, non-blocking stub.
        if not hasattr(win, "uid") or win.__class__.__name__ == "FakeWindow":
            try:
                win.evaluate_js(script)
            except Exception:  # noqa: BLE001
                log.exception("push failed")
            return

        import sys

        if sys.platform == "darwin":
            try:
                from PyObjCTools import AppHelper
                from webview.platforms.cocoa import BrowserView

                uid = win.uid

                def _run(uid: str = uid, script: str = script) -> None:
                    try:
                        inst = BrowserView.instances.get(uid)
                        wv = getattr(inst, "webview", None) if inst is not None else None
                        if wv is not None:
                            wv.evaluateJavaScript_completionHandler_(script, None)
                            return
                    except Exception:  # noqa: BLE001
                        log.exception("async cocoa push failed")

                AppHelper.callAfter(_run)
                return
            except Exception:  # noqa: BLE001
                log.exception("async push setup failed")

        def _fallback() -> None:
            try:
                win.evaluate_js(script)
            except Exception:  # noqa: BLE001
                log.exception("push failed")

        threading.Thread(target=_fallback, daemon=True, name="cca-js-push").start()

    def _on_event_chan(self, chan: str, event: AgentEvent) -> None:
        if event.type == "text":
            self._push("text", chan=chan, text=str(event.data))
        elif event.type == "thinking":
            text = str(event.data or "").strip()
            if text:
                self._push("thinking", chan=chan, text=text)
        elif event.type == "tool_call":
            call = event.data
            name = getattr(call, "name", None) or ""
            # Phase-1: bash 命令过程默认不刷屏；其它工具仍显示芯片
            if name != "bash":
                self._push("tool", chan=chan, name=name)
            if name == "browser":
                args = getattr(call, "arguments", None) or {}
                action = str(args.get("action") or "").lower()
                url = str(args.get("url") or "").strip()
                if action == "navigate" and url:
                    self._chat_browser_urls.append(url)
                    self._push("browser", chan=chan, showcase=True, **self._browser.ui_state())
        elif event.type == "skills_activated":
            names = event.data if isinstance(event.data, list) else []
            if names:
                self._push("status", chan=chan, text="自动启用技能：" + "、".join(str(n) for n in names))

    def _maybe_showcase_website(
        self,
        task: str,
        answer: str,
        agent: Agent | None,
        chan: str,
    ) -> None:
        """Safety net: open internal browser if the model skipped the showcase."""
        from codeagent.browser.showcase import (
            looks_like_website_finished,
            looks_like_website_task,
            pick_preview_url,
            probe_http,
        )

        hints = getattr(agent, "workspace_hints", "") if agent else ""
        navigated = bool(getattr(agent, "_browser_navigated", False) or self._chat_browser_urls)
        if navigated:
            url = (self._chat_browser_urls[-1] if self._chat_browser_urls else "") or (
                self._browser.url or ""
            )
            # Model may have navigated to a dead port → recover to a live preview.
            if url and not probe_http(url):
                recovered = pick_preview_url(
                    answer, url, *(self._chat_browser_urls or []),
                    workspace=self.root,
                )
                if recovered and recovered.rstrip("/") != url.rstrip("/"):
                    log.info("showcase recover dead %s → %s", url, recovered)
                    self.browser_goto(recovered)
                    url = recovered
                else:
                    # Still open via navigate so the window shows the error page, not white.
                    self.browser_goto(url)
            if url:
                self.browser_show_window()
                self._push("browser", chan=chan, showcase=True, url=url, **self._browser.ui_state())
            return
        if not looks_like_website_finished(task, answer, hints) and not looks_like_website_task(
            task, hints,
        ):
            return
        url = pick_preview_url(
            answer, *(self._chat_browser_urls or []),
            workspace=self.root,
        )
        if not url:
            return
        log.info("auto showcase website → %s", url)
        self.browser_goto(url)
        self.browser_show_window()
        self._push(
            "browser",
            chan=chan,
            showcase=True,
            url=url,
            ready_text=f"已自动打开成品预览：{url}",
        )

    def _on_event(self, event: AgentEvent) -> None:
        self._on_event_chan("A", event)

    def _on_event2(self, event: AgentEvent) -> None:
        self._on_event_chan("B", event)

    # ------------------------------------------------------------------
    # state & settings
    # ------------------------------------------------------------------

    def get_state(self) -> dict[str, Any]:
        rel = latest()
        try:
            from codeagent.skills.fusion import ensure_fusion_skills

            ensure_fusion_skills(DEFAULT_SKILLS_DIR)
        except OSError:
            pass
        return {
            "version": rel.version,
            "date": rel.date,
            "highlights": list(rel.highlights),
            "providers": list_providers(),
            "voices": self._voice_presets(),
            "config": asdict(self.config),
            "settings": asdict(self.settings),
            "root": str(self.root),
            "active_label": self._active_label(),
            "project": (self.projects.get(self.projects.active).name
                        if self.projects.get(self.projects.active) else ""),
            "privacy_version": PRIVACY_VERSION,
            "privacy_accepted": (
                self.config.privacy_accepted_version == PRIVACY_VERSION
            ),
        }

    def get_privacy_policy(self) -> dict[str, Any]:
        """Current privacy policy + whether this install has accepted it."""
        doc = privacy_document()
        doc["accepted"] = self.config.privacy_accepted_version == PRIVACY_VERSION
        doc["accepted_version"] = self.config.privacy_accepted_version
        doc["accepted_at"] = self.config.privacy_accepted_at
        return doc

    def accept_privacy(self) -> dict[str, Any]:
        """Record acceptance of the current privacy policy version."""
        from datetime import datetime, timezone

        self.config.privacy_accepted_version = PRIVACY_VERSION
        self.config.privacy_accepted_at = (
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        )
        self.config.save()
        log.info("privacy accepted: version=%s", PRIVACY_VERSION)
        return {
            "ok": True,
            "privacy_version": PRIVACY_VERSION,
            "privacy_accepted": True,
            "accepted_at": self.config.privacy_accepted_at,
        }

    @staticmethod
    def _voice_presets() -> dict[str, str]:
        try:
            from codeagent.voice.tts import VOICE_LABELS, VOICE_PRESETS

            return {k: VOICE_LABELS.get(k, v) for k, v in VOICE_PRESETS.items()}
        except Exception:  # noqa: BLE001
            return {}

    def get_changelog(self) -> str:
        return changelog_text()

    def get_nav_status(self) -> dict[str, Any]:
        """侧栏底部：本地端点/探测模型、API 在线、聚合池启用、当前激活。"""
        local_eps = [e for e in self.assets.endpoints if e.kind not in ("gradio", "comfy")]
        running = 0
        if self._probe_cache is not None:
            chat_ids = {e.id for e in local_eps}
            running = sum(
                len(models)
                for eid, models in self._probe_cache[1].items()
                if eid in chat_ids
            )
        return {
            "running": running,
            "local": len(local_eps),
            "online": sum(1 for m in self.assets.api_models if m.status == "online"),
            "api": len(self.assets.api_models),
            "mixtures": sum(1 for x in self.assets.mixtures if x.enabled),
            "active": self._active_label(),
        }

    def get_overview(self) -> dict[str, Any]:
        """Dashboard stats: counts of skills, memories, runs, harnesses."""
        rel = latest()
        skills = self.get_skills()
        try:
            memories = len(asyncio.run(self._memory_store().list(limit=1000)))
        except Exception:  # noqa: BLE001
            memories = 0
        runs = self.get_runs()
        harnesses = self.get_harnesses()
        return {
            "version": rel.version,
            "date": rel.date,
            "provider": self.config.provider,
            "active_label": self._active_label(),
            "model": self.config.model or "默认",
            "skills": len(skills),
            "memories": memories,
            "runs": len(runs),
            "harnesses": sum(1 for h in harnesses if h["available"]),
            "voice": self.config.voice_name if self.config.voice_enabled else "关",
            "recent_runs": runs[:5],
        }

    def save_config(self, data: dict[str, Any]) -> dict[str, Any]:
        for key in ("provider", "model", "api_key", "base_url", "strategy",
                    "voice_name", "workers_json", "theme", "thinking",
                    "companion_preset", "companion_name", "companion_nature"):
            if key in data:
                setattr(self.config, key, str(data[key]))
        if self.config.theme not in ("dark", "light", "auto"):
            self.config.theme = "dark"
        if self.config.thinking not in ("low", "medium", "high"):
            self.config.thinking = "medium"
        if "max_iterations" in data:
            self.config.max_iterations = clamp_max_iterations(
                data["max_iterations"], self.config.max_iterations,
            )
        else:
            self.config.max_iterations = clamp_max_iterations(self.config.max_iterations)
        for key in ("auto_yes", "voice_enabled", "voice_cute_tone", "companion_enabled"):
            if key in data:
                setattr(self.config, key, bool(data[key]))
        if "voice_pitch" in data:
            try:
                self.config.voice_pitch = max(-50, min(50, int(data["voice_pitch"])))
            except (TypeError, ValueError):
                pass
        if "voice_rate" in data:
            try:
                self.config.voice_rate = max(-20, min(20, int(data["voice_rate"])))
            except (TypeError, ValueError):
                pass
        self.config.save()
        self._agent = None
        log.info("config saved: provider=%s model=%s companion=%s",
                 self.config.provider, self.config.model,
                 self.config.companion_enabled)
        return asdict(self.config)

    def save_settings(self, data: dict[str, Any]) -> dict[str, Any]:
        for key in ("nickname", "language", "instructions", "context"):
            if key in data:
                setattr(self.settings, key, str(data[key]))
        self.settings.save()
        if self._agent is not None:
            self._agent.settings = self.settings
        return asdict(self.settings)

    # ------------------------------------------------------------------
    # model assets (LCA-style: local endpoints + API models, key pointers)
    # ------------------------------------------------------------------

    def get_model_assets(self) -> dict[str, Any]:
        probed = self._probed_assets()
        by_id = {e["id"]: e for e in probed}
        endpoints: list[dict[str, Any]] = []
        for e in self.assets.endpoints:
            rec = {
                **by_id.get(e.id, {"id": e.id, "ok": False, "models": []}),
                "label": e.label, "role": e.role, "base": e.base,
            }
            rec["kind"] = rec.get("kind") or e.kind
            models = list(rec.get("models") or [])
            if rec.get("kind") == "gradio" and not models:
                models = [(e.label or "").strip() or "WAN 文生视频"]
            if rec.get("kind") == "comfy" and not models:
                models = [(e.label or "").strip() or "ComfyUI"]
            rec["models"] = models
            endpoints.append(rec)
        active = self.assets.active
        return {
            "endpoints": endpoints,
            "api_models": [self._api_model_dict(m) for m in self.assets.api_models],
            "mixtures": [self._mixture_dict(x) for x in self.assets.mixtures],
            "active": FREE_ROUTE_REF if is_free_route(active) else active,
            "active_label": self._active_label(),
            "free_route": {"ref": FREE_ROUTE_REF, "label": FREE_ROUTE_LABEL},
        }

    @staticmethod
    def _api_model_dict(m: ApiModel) -> dict[str, Any]:
        from codeagent.videoops.cloud import is_video_api_model, video_backend

        video = is_video_api_model(m.model, m.base_url, m.provider)
        return {
            "id": m.id,
            "label": m.display,
            "provider": m.provider,
            "base_url": m.base_url,
            "model": m.model,
            "status": m.status,
            "latency_ms": m.latency_ms,
            "cost_per_1k": m.cost_per_1k,
            "has_key": bool(load_secret(m.secret_key)),
            "key_masked": mask_secret(load_secret(m.secret_key)),
            "video": video,
            "video_kind": video_backend(m.model, m.base_url, m.provider) if video else "",
        }

    def _mixture_dict(self, x: Mixture) -> dict[str, Any]:
        return {
            "id": x.id,
            "name": x.name,
            "strategy": x.strategy,
            "members": [
                {"ref": ref, "label": self.assets.member_label(ref),
                 "local": ref.startswith("local:")}
                for ref in x.members
            ],
            "fallback": self.assets.member_label(x.fallback) if x.fallback else "",
            "enabled": x.enabled,
            "calls": x.calls,
            "active": self.assets.active == f"mix:{x.id}",
        }

    def _active_video_ep(self) -> OllamaEndpoint | None:
        ref = (self.assets.active or "").strip()
        if not ref.startswith("local:") or "@" not in ref:
            return None
        _, ep_id = ref[6:].rsplit("@", 1)
        ep = next((e for e in self.assets.endpoints if e.id == ep_id), None)
        if ep is None or ep.kind != "gradio":
            return None
        return ep

    def _active_video_job(self) -> dict[str, Any] | None:
        """Active selection that should run text-to-video instead of chat."""
        if self._active_video_ep() is not None:
            return {"backend": "wan"}
        ref = (self.assets.active or "").strip()
        if not ref.startswith("api:"):
            return None
        from codeagent.videoops.cloud import is_video_api_model, video_backend

        am = next((m for m in self.assets.api_models if m.id == ref[4:]), None)
        if am is None or not is_video_api_model(am.model, am.base_url, am.provider):
            return None
        return {
            "backend": video_backend(am.model, am.base_url, am.provider) or "minimax",
            "model": am.model,
        }

    def _active_label(self) -> str:
        if is_free_route(self.assets.active):
            return FREE_ROUTE_LABEL
        job = self._active_video_job()
        if job is not None:
            if job.get("backend") == "wan":
                model = self.assets.active[6:].rsplit("@", 1)[0]
                return f"{model}（文生视频）"
            return f"{job.get('model') or job['backend']}（文生视频）"
        resolved = self.assets.resolve_active()
        if resolved is None:
            return f"{self.config.provider} · {self.config.model or '默认'}"
        kind, kwargs = resolved
        if kind in ("local", "local_openai"):
            return f"{kwargs['model']}（本地）"
        if kind == "mix":
            return f"聚合池 · {kwargs['mixture'].name}"
        am = next((m for m in self.assets.api_models
                   if m.id == self.assets.active[4:]), None)
        return am.display if am else "API 模型"

    def add_endpoint(self, base: str, label: str = "", role: str = "backup") -> dict[str, Any]:
        base = normalize_endpoint_base(base or "")
        if not base:
            return {"ok": False, "error": "地址为空"}
        if not re.match(r"^https?://[\w.-]+:\d{1,5}$", base, re.I):
            return {"ok": False, "error": "地址格式应为 http://IP:端口"}
        if any(e.base == base for e in self.assets.endpoints):
            return {"ok": False, "error": "端点已存在"}
        ep = OllamaEndpoint(
            base=base, label=(label or "").strip(),
            role=role if role in ("primary", "backup") else "backup",
        )
        if base.rstrip("/").endswith(":8188"):
            ep.kind = "comfy"
            self._remember_comfy_base(base)
        self.assets.endpoints.append(ep)
        self.assets.save()
        self._invalidate_probe_cache()
        log.info("endpoint added: %s kind=%s", base, ep.kind or "?")
        return {"ok": True, "kind": ep.kind}

    def remove_endpoint(self, endpoint_id: str) -> bool:
        before = len(self.assets.endpoints)
        self.assets.endpoints = [
            e for e in self.assets.endpoints if e.id != endpoint_id
        ]
        if len(self.assets.endpoints) == before:
            return False
        self.assets.save()
        self._invalidate_probe_cache()
        return True

    def detect_models(self, base_url: str, api_key: str = "") -> dict[str, Any]:
        """Dual-protocol sniff of a Base URL (OpenAI /models → /api/tags)。

        带 API Key 识别：多数提供方的 /models 需要鉴权。
        """
        return asyncio.run(
            detect_service((base_url or "").strip(), (api_key or "").strip()))

    def add_api_model(self, base_url: str, model: str,
                      label: str = "", api_key: str = "",
                      provider: str = "") -> dict[str, Any]:
        base_url = (base_url or "").strip().rstrip("/")
        model = (model or "").strip()
        if not base_url or not model:
            return {"ok": False, "error": "Base URL 和模型名必填"}
        am = ApiModel(base_url=base_url, model=model, label=(label or "").strip(),
                      provider=(provider or "").strip())
        if api_key.strip():
            save_secret(am.secret_key, api_key.strip())  # pointer in store
        self.assets.api_models.append(am)
        self.assets.save()
        log.info("api model added: %s (%s)", am.display, am.id)
        return {"ok": True, "id": am.id}

    def remove_api_model(self, model_id: str) -> bool:
        target = next((m for m in self.assets.api_models if m.id == model_id), None)
        if target is None:
            return False
        delete_secret(target.secret_key)
        self.assets.api_models.remove(target)
        if self.assets.active == f"api:{model_id}":
            self.assets.active = ""
            self._agent = None
        self.assets.save()
        return True

    def set_active_model(self, ref: str) -> dict[str, Any]:
        """ref: 'local:model@endpoint_id' | 'api:{id}' | 'mix:{id}' | 'route:free'.

        Gradio 端点可选为当前「文生视频」模型，但不能作为对话 LLM。
        空字符串与 ``route:free`` 都表示自由路由。
        """
        ref = (ref or "").strip()
        if is_free_route(ref):
            ref = FREE_ROUTE_REF
        self.assets.active = ref
        self.assets.save()
        self._agent = None  # rebuild on next chat
        log.info("active model: %s", self.assets.active)
        return {"ok": True, "active_label": self._active_label()}

    def test_model(self, ref: str) -> dict[str, Any]:
        """Connectivity test through the same provider path as real chat."""
        saved = self.assets.active
        self.assets.active = (ref or "").strip()
        try:
            provider = build_active_provider(self.assets)
        finally:
            self.assets.active = saved
        if provider is None:
            return {"ok": False, "error": "模型资产不存在"}
        result = asyncio.run(test_provider(provider))
        # 记录测试状态与延迟（LCA：status/latencyMs 随测试更新）
        if ref.startswith("api:"):
            am = next((m for m in self.assets.api_models if m.id == ref[4:]), None)
            if am is not None:
                am.status = "online" if result.get("ok") else "error"
                if result.get("ok"):
                    am.latency_ms = int(result.get("latency_ms", 0))
                self.assets.save()
        result["label"] = ref
        return result

    # ------------------------------------------------------------------
    # models page: local model ops + mixtures (LCA Models.tsx)
    # ------------------------------------------------------------------

    def get_models_page(self) -> dict[str, Any]:
        """Local tab data: endpoints with detailed tags + running status."""

        dirty = False

        async def _probe(ep: OllamaEndpoint) -> dict[str, Any]:
            nonlocal dirty
            info = await probe_endpoint_info(ep.base)
            kind = (info or {}).get("kind", "") or ep.kind
            if info is not None and kind and ep.kind != kind:
                ep.kind = kind
                dirty = True
            details = (info or {}).get("models") or []
            running: set[str] = set()
            if info is not None and kind == "ollama":
                running = await running_models(ep.base)
            models = [
                {
                    **d,
                    "running": True if kind in ("openai", "gradio", "comfy") else d["name"] in running,
                    "ref": f"local:{d['name']}@{ep.id}",
                    "active": self.assets.active == f"local:{d['name']}@{ep.id}",
                    "manageable": kind == "ollama",
                }
                for d in details
            ]
            if (kind or ep.kind) == "gradio" and not models:
                name = (ep.label or "").strip() or "WAN 文生视频"
                models = [{
                    "name": name,
                    "params": "Gradio 文生视频",
                    "quant": "文生视频",
                    "size": "-",
                    "running": info is not None,
                    "ref": f"local:{name}@{ep.id}",
                    "active": self.assets.active == f"local:{name}@{ep.id}",
                    "manageable": False,
                }]
            if (kind or ep.kind) == "comfy":
                if info is not None:
                    self._remember_comfy_base(ep.base)
                if not models:
                    name = (ep.label or "").strip() or "ComfyUI"
                    models = [{
                        "name": name,
                        "params": "ComfyUI 节点图",
                        "quant": "节点图",
                        "size": "-",
                        "running": info is not None,
                        "ref": f"local:{name}@{ep.id}",
                        "active": self.assets.active == f"local:{name}@{ep.id}",
                        "manageable": False,
                    }]
            return {
                "id": ep.id, "label": ep.label, "base": ep.base, "role": ep.role,
                "kind": kind or ep.kind, "online": info is not None, "models": models,
            }

        async def _all() -> list[dict[str, Any]]:
            return list(await asyncio.gather(
                *(_probe(e) for e in self.assets.endpoints)))

        endpoints = asyncio.run(_all())
        if dirty:
            self.assets.save()
            self._invalidate_probe_cache()
        active = self.assets.active
        return {
            "endpoints": endpoints,
            "api_models": [self._api_model_dict(m) for m in self.assets.api_models],
            "mixtures": [self._mixture_dict(x) for x in self.assets.mixtures],
            "active": FREE_ROUTE_REF if is_free_route(active) else active,
            "active_label": self._active_label(),
            "free_route": {"ref": FREE_ROUTE_REF, "label": FREE_ROUTE_LABEL},
        }

    def set_local_loaded(self, endpoint_id: str, model: str, load: bool) -> dict[str, Any]:
        ep = next((e for e in self.assets.endpoints if e.id == endpoint_id), None)
        if ep is None:
            return {"ok": False, "error": "端点不存在"}
        if ep.kind in ("openai", "gradio", "comfy"):
            return {"ok": False, "error": "该端点不支持显存启停（Ollama 专用）"}
        try:
            asyncio.run(set_model_loaded(ep.base, model, load))
            return {"ok": True}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)[:200]}

    def delete_local_model(self, endpoint_id: str, model: str) -> dict[str, Any]:
        ep = next((e for e in self.assets.endpoints if e.id == endpoint_id), None)
        if ep is None:
            return {"ok": False, "error": "端点不存在"}
        if ep.kind in ("openai", "gradio", "comfy"):
            return {"ok": False, "error": "该端点不支持删除模型（Ollama 专用）"}
        try:
            asyncio.run(delete_ollama_model(ep.base, model))
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)[:200]}
        if self.assets.active == f"local:{model}@{endpoint_id}":
            self.assets.active = ""
            self._agent = None
        self.assets.save()
        return {"ok": True}

    def pull_model(self, model: str) -> dict[str, Any]:
        """部署新模型：后台线程拉取（主推理端点优先）。"""
        model = (model or "").strip()
        if not model:
            return {"ok": False, "error": "模型标识为空"}
        ep = (next((e for e in self.assets.endpoints if e.role == "primary"), None)
              or (self.assets.endpoints[0] if self.assets.endpoints else None))
        if ep is None:
            return {"ok": False, "error": "请先添加 Ollama 端点"}

        def _pull() -> None:
            try:
                self._push("status", text=f"开始部署 {model}…")
                asyncio.run(pull_ollama_model(ep.base, model))
                self._push("pull_done", model=model, ok=True)
            except Exception as exc:  # noqa: BLE001
                log.exception("pull failed")
                self._push("pull_done", model=model, ok=False,
                           error=str(exc)[:200])

        threading.Thread(target=_pull, daemon=True).start()
        return {"ok": True, "endpoint": ep.label}

    def save_mixture(self, name: str, strategy: str, members: list[str],
                     mix_id: str = "") -> dict[str, Any]:
        name = (name or "").strip()
        members = [m for m in (members or []) if isinstance(m, str) and m]
        if not name:
            return {"ok": False, "error": "请先填写聚合池名称"}
        if len(members) < 2:
            return {"ok": False, "error": f"聚合池至少选择 2 个成员模型（当前已选 {len(members)} 个）"}
        if strategy not in ("weighted", "cascade", "vote", "rule"):
            strategy = "weighted"
        if mix_id:
            mix = next((x for x in self.assets.mixtures if x.id == mix_id), None)
            if mix is None:
                return {"ok": False, "error": "聚合池不存在"}
            mix.name, mix.strategy, mix.members = name, strategy, members
            if mix.fallback not in members:
                mix.fallback = members[0]
        else:
            self.assets.mixtures.append(Mixture(name=name, strategy=strategy,
                                                members=members))
        self.assets.save()
        return {"ok": True}

    def delete_mixture(self, mix_id: str) -> bool:
        before = len(self.assets.mixtures)
        self.assets.mixtures = [x for x in self.assets.mixtures if x.id != mix_id]
        if len(self.assets.mixtures) == before:
            return False
        if self.assets.active == f"mix:{mix_id}":
            self.assets.active = ""
            self._agent = None
        self.assets.save()
        return True

    def toggle_mixture(self, mix_id: str, enabled: bool) -> bool:
        mix = next((x for x in self.assets.mixtures if x.id == mix_id), None)
        if mix is None:
            return False
        mix.enabled = bool(enabled)
        self.assets.save()
        return True

    # ------------------------------------------------------------------
    # router (LCA RouterPage.tsx)
    # ------------------------------------------------------------------

    def _route_targets(self) -> list[dict[str, str]]:
        targets = [
            {"ref": f"mix:{x.id}", "label": f"聚合池 · {x.name}"}
            for x in self.assets.mixtures
        ]
        targets += [
            {"ref": f"api:{m.id}", "label": m.display}
            for m in self.assets.api_models
        ]
        probed = self._probed_local()
        targets += [
            {"ref": f"local:{m}@{ep.id}", "label": f"{m}（本地）"}
            for ep in self.assets.endpoints for m in probed.get(ep.id, [])
        ]
        return targets

    _probe_cache: tuple[float, dict[str, list[str]]] | None = None

    def _invalidate_probe_cache(self) -> None:
        """端点配置或类型变化后清空探测缓存，下次调用重新探测。"""
        self._probe_cache = None
        self._assets_probe_cache = None

    def _probed_local(self, ttl: float = 30.0) -> dict[str, list[str]]:
        """端点 → 模型名列表（30s 缓存；离线端点为空列表）。"""
        import time as _time

        if (self._probe_cache is not None
                and _time.monotonic() - self._probe_cache[0] < ttl):
            return self._probe_cache[1]
        result: dict[str, list[str]] = {e.id: [] for e in self.assets.endpoints}
        try:
            probed = asyncio.run(probe_all(self.assets.endpoints))
            for entry in probed["endpoints"]:
                if entry.get("ok"):
                    result[entry["id"]] = entry.get("models", [])
        except Exception:  # noqa: BLE001 — 探测失败不阻塞路由配置
            log.debug("route-target probe failed")
        self._probe_cache = (_time.monotonic(), result)
        return result

    _assets_probe_cache: tuple[float, list[dict[str, Any]]] | None = None

    def _probed_assets(self, ttl: float = 20.0) -> list[dict[str, Any]]:
        """完整端点探测结果（20s 缓存），供对话页/模型页选择器复用。
        避免每次切换页面都同步全量探测，离线/慢端点不再反复阻塞桥线程。"""
        import time as _time

        if (self._assets_probe_cache is not None
                and _time.monotonic() - self._assets_probe_cache[0] < ttl):
            return self._assets_probe_cache[1]
        try:
            probed = asyncio.run(probe_all(self.assets.endpoints))
            endpoints = probed["endpoints"]
        except Exception:  # noqa: BLE001 — 探测失败也缓存空结果，避免反复重试
            log.debug("assets probe failed")
            endpoints = []
        self._assets_probe_cache = (_time.monotonic(), endpoints)
        return endpoints

    def get_router(self) -> dict[str, Any]:
        return {
            "rules": [
                {**asdict(r), "target_label": self._target_label(r.target)}
                for r in self.router.sorted_rules()
            ],
            "weights": asdict(self.router.weights),
            "targets": self._route_targets(),
        }

    def _target_label(self, ref: str) -> str:
        if ref.startswith("mix:"):
            mix = next((x for x in self.assets.mixtures if x.id == ref[4:]), None)
            return f"聚合池 · {mix.name}" if mix else ref
        return self.assets.member_label(ref) if ref else "（未设置）"

    def add_route_rule(self, task_type: str, keywords: str, target: str) -> dict[str, Any]:
        task_type = (task_type or "").strip()
        if not task_type:
            return {"ok": False, "error": "填写任务类型"}
        target = (target or "").strip()
        if not self._valid_target(target):
            return {"ok": False, "error": "暂无可用模型，请先到「模型管理」接入模型"}
        self.router.rules.append(RouteRule(
            task_type=task_type, keywords=(keywords or "").strip(), target=target,
        ))
        self.router.save()
        return {"ok": True}

    def _valid_target(self, ref: str) -> bool:
        """mix/api 必须存在；local 只需格式合法（端点可能暂时离线）。"""
        if ref.startswith("mix:"):
            return any(x.id == ref[4:] for x in self.assets.mixtures)
        if ref.startswith("api:"):
            return any(m.id == ref[4:] for m in self.assets.api_models)
        if ref.startswith("local:") and "@" in ref:
            ep_id = ref.rsplit("@", 1)[1]
            return any(e.id == ep_id for e in self.assets.endpoints)
        return False

    def delete_route_rule(self, rule_id: str) -> bool:
        before = len(self.router.rules)
        self.router.rules = [r for r in self.router.rules if r.id != rule_id]
        if len(self.router.rules) == before:
            return False
        self.router.save()
        return True

    def toggle_route_rule(self, rule_id: str, enabled: bool) -> bool:
        rule = next((r for r in self.router.rules if r.id == rule_id), None)
        if rule is None:
            return False
        rule.enabled = bool(enabled)
        self.router.save()
        return True

    def move_route_rule(self, rule_id: str, direction: int) -> bool:
        rules = self.router.sorted_rules()
        i = next((n for n, r in enumerate(rules) if r.id == rule_id), None)
        if i is None:
            return False
        j = i + (1 if direction > 0 else -1)
        if j < 0 or j >= len(rules):
            return False
        rules[i].priority, rules[j].priority = rules[j].priority, rules[i].priority
        if rules[i].priority == rules[j].priority:
            # 同级交换无效：给邻居让出优先级，保证顺序真实变化
            rules[j].priority += 1 if direction > 0 else -1
        self.router.save()
        return True

    def save_route_weights(self, cost: int, quality: int, local_first: int) -> dict[str, Any]:
        self.router.weights.cost = max(0, min(100, int(cost)))
        self.router.weights.quality = max(0, min(100, int(quality)))
        self.router.weights.local_first = max(0, min(100, int(local_first)))
        self.router.save()
        return asdict(self.router.weights)

    def route_sandbox(self, text: str) -> dict[str, Any]:
        text = (text or "").strip()
        if not text:
            return {"ok": False, "error": "请输入测试语句"}
        result = route_message(text, self.router, self._target_label)
        result["ok"] = True
        return result

    # ------------------------------------------------------------------
    # permissions (LCA Permissions.tsx)
    # ------------------------------------------------------------------

    def get_permissions(self) -> dict[str, Any]:
        return {
            "capabilities": [
                {k: c[k] for k in ("id", "capability", "desc", "scope")}
                | {"level": self.perm_levels.get(c["id"], "confirm")}
                for c in CAPABILITIES
            ],
            "levels": list(LEVELS),
            "audit": read_audit(12),
        }

    def set_permission_level(self, cap_id: str, level: str) -> dict[str, Any]:
        cap = next((c for c in CAPABILITIES if c["id"] == cap_id), None)
        if cap is None or level not in LEVELS:
            return {"ok": False, "error": "未知能力或级别"}
        self.perm_levels[cap_id] = level
        save_levels(self.perm_levels)
        append_audit("user", f"调整「{cap['capability']}」权限为 {level}", "confirmed")
        self._agent = None  # rebuild with new policy
        return {"ok": True}

    def resolve_confirm(self, cid: str, approved: bool) -> bool:
        return self.confirmer.resolve(cid, bool(approved))

    def resolve_confirm2(self, cid: str, approved: bool) -> bool:
        return self._confirmer2.resolve(cid, bool(approved))

    # ------------------------------------------------------------------
    # versions (LCA Versions.tsx)
    # ------------------------------------------------------------------

    def get_versions(self) -> dict[str, Any]:
        from codeagent.releases import RELEASES

        ordered = list(reversed(RELEASES))
        current, history = ordered[0], ordered[1:]
        return {
            "current": {"version": current.version, "date": current.date,
                        "points": list(current.highlights)},
            "history": [
                {"version": r.version, "date": r.date, "points": list(r.highlights)}
                for r in history
            ],
        }

    # ------------------------------------------------------------------
    # activity stream & self-learning (LCA Learning.tsx)
    # ------------------------------------------------------------------

    def get_activity(self, limit: int = 80) -> list[dict[str, Any]]:
        return read_activity(min(int(limit), 500))

    def send_feedback(self, positive: bool) -> dict[str, Any]:
        """对话页赞/踩 → 活动流 kind=learn 条目。"""
        record_feedback(bool(positive))
        return {"ok": True}

    def get_learning(self) -> dict[str, Any]:
        store = LearningStore.load()
        entries = read_activity(500)
        ups = sum(1 for e in entries
                  if e.get("kind") == "learn" and "正向" in e.get("text", ""))
        downs = sum(1 for e in entries
                    if e.get("kind") == "learn" and "点踩" in e.get("text", ""))
        latest_rec = store.records[-1] if store.records else None
        return {
            "records": [asdict(r) for r in store.records[-30:]],
            "accuracy": latest_rec.accuracy if latest_rec else 0,
            "total_samples": sum(r.samples for r in store.records),
            "today_up": ups,
            "today_down": downs,
        }

    def learn_now(self) -> dict[str, Any]:
        result = learn_now()
        if result.get("ok"):
            # 反馈信号真实回流：正反馈占比低 → 路由更保守（本地优先上调）
            if result["accuracy"] < 60:
                self.router.weights.local_first = min(
                    100, self.router.weights.local_first + 5)
                self.router.save()
        return result

    # ------------------------------------------------------------------
    # automation: workflows (LCA Automation.tsx, real step execution)
    # ------------------------------------------------------------------

    def get_workflows(self) -> list[dict[str, Any]]:
        return [
            {**asdict(w), "steps": [asdict(s) for s in w.steps],
             "step_labels": [self._step_label(s.tool) for s in w.steps]}
            for w in self.workflows.workflows
        ]

    def _step_label(self, tool: str) -> str:
        if not tool:
            return "当前激活模型"
        return self._target_label(tool) if ":" in tool else tool

    def add_workflow(self, name: str, desc: str, trigger: str,
                     steps: list[dict[str, str]]) -> dict[str, Any]:
        name = (name or "").strip()
        steps = [WorkflowStep(name=(s.get("name") or "").strip(),
                              tool=(s.get("tool") or "").strip())
                 for s in (steps or []) if (s.get("name") or "").strip()]
        if not name:
            return {"ok": False, "error": "请填写工作流名称"}
        if not steps:
            return {"ok": False, "error": "至少需要一个步骤"}
        if trigger not in ("manual", "cron", "event", "feishu"):
            trigger = "manual"
        self.workflows.workflows.append(Workflow(
            name=name, desc=(desc or "").strip(), trigger=trigger, steps=steps,
        ))
        self.workflows.save()
        log_activity("workflow", f"新建工作流「{name}」（{len(steps)} 步）")
        return {"ok": True}

    def delete_workflow(self, wf_id: str) -> bool:
        before = len(self.workflows.workflows)
        self.workflows.workflows = [
            w for w in self.workflows.workflows if w.id != wf_id]
        if len(self.workflows.workflows) == before:
            return False
        self.workflows.save()
        return True

    def run_workflow(self, wf_id: str) -> dict[str, Any]:
        if self.runner.start(wf_id):
            return {"ok": True}
        wf = self.workflows.get(wf_id)
        return {"ok": False,
                "error": "工作流不存在" if wf is None else "工作流正在运行中"}

    def pause_workflow(self, wf_id: str) -> bool:
        return self.runner.pause(wf_id)

    def set_workflow_continuous(self, wf_id: str, on: bool) -> bool:
        return self.runner.set_continuous(wf_id, bool(on))

    def _run_workflow_step(self, step: WorkflowStep, context: str) -> str:
        """真实执行：单步 = 一次 agent 调用，上一步产出作为上下文。"""
        prompt = step.name if not context else (
            f"{step.name}\n\n上一步产出：\n{context[:2000]}")
        provider = self._provider_for_ref(step.tool)
        agent = self._build_agent_with(provider)
        return asyncio.run(agent.run(prompt))

    def _provider_for_ref(self, ref: str):
        """按模型引用解析 provider；空引用走当前激活模型。"""
        if ref and ":" in ref and self._valid_target(ref):
            saved = self.assets.active
            self.assets.active = ref
            try:
                provider = build_active_provider(self.assets)
            finally:
                self.assets.active = saved
            if provider is not None:
                return provider
        return self._build_provider()

    # ------------------------------------------------------------------
    # cron jobs (LCA CronPage.tsx, real scheduler)
    # ------------------------------------------------------------------

    def get_cron(self) -> dict[str, Any]:
        return {
            "presets": PRESETS,
            "jobs": [asdict(j) for j in self.cron_jobs.jobs],
            "evolution": {
                "enabled": self.evolution.settings.enabled,
                "cron": self.evolution.settings.cron,
            },
        }

    def add_cron_job(self, name: str, schedule: str, action: str) -> dict[str, Any]:
        name = (name or "").strip()
        action = (action or "").strip()
        schedule = (schedule or "").strip()
        if not name or not action:
            return {"ok": False, "error": "请填写名称与执行动作"}
        if len(schedule.split()) != 5:
            return {"ok": False, "error": "cron 表达式需为五字段（分 时 日 月 周）"}
        self.cron_jobs.jobs.append(CronJob(
            name=name, schedule=schedule, action=action,
            next_run=next_run_hint(schedule),
        ))
        self.cron_jobs.save()
        log_activity("cron", f"新建定时任务「{name}」（{schedule}）")
        return {"ok": True}

    def delete_cron_job(self, job_id: str) -> bool:
        before = len(self.cron_jobs.jobs)
        self.cron_jobs.jobs = [j for j in self.cron_jobs.jobs if j.id != job_id]
        if len(self.cron_jobs.jobs) == before:
            return False
        self.cron_jobs.save()
        return True

    def toggle_cron_job(self, job_id: str, enabled: bool) -> bool:
        job = next((j for j in self.cron_jobs.jobs if j.id == job_id), None)
        if job is None:
            return False
        job.enabled = bool(enabled)
        if enabled:
            job.next_run = next_run_hint(job.schedule)
        self.cron_jobs.save()
        log_activity("cron", f"定时任务「{job.name}」{'启用' if enabled else '停用'}")
        return True

    def _run_cron_action(self, job: CronJob) -> bool:
        """到点执行：动作描述作为提示词跑一次 agent。"""
        agent = self._build_agent_with(self._build_provider())
        asyncio.run(agent.run(job.action))
        return True

    # ------------------------------------------------------------------
    # evolution log (LCA Evolution.tsx)
    # ------------------------------------------------------------------

    def get_evolution(self) -> dict[str, Any]:
        return {
            "patches": [asdict(p) for p in self.evolution.patches],
            "runs": [
                {**asdict(r), "phases": [asdict(p) for p in r.phases],
                 "skill_drafts": [asdict(d) for d in r.skill_drafts]}
                for r in self.evolution.runs
            ],
            "settings": asdict(self.evolution.settings),
            "phases": list(PHASES),
        }

    def _evolution_stats(self) -> dict[str, Any]:
        entries = read_activity(500)
        samples = sum(1 for e in entries if e.get("kind") == "learn")
        try:
            memories = len(asyncio.run(self._memory_store().list(limit=1000)))
        except Exception:  # noqa: BLE001
            memories = 0
        return {"messages": samples, "events": len(entries),
                "samples": samples, "compressed": max(1, memories // 20),
                "merged": max(0, memories // 50)}

    def _run_evolution(self, manual: bool = True) -> dict[str, Any]:
        run = run_evolution(self.evolution, stats=self._evolution_stats(),
                            manual=manual)
        return {"ok": True, "patches": len(run.patch_ids),
                "skills": len(run.skill_drafts)}

    def run_evolution_now(self) -> dict[str, Any]:
        return self._run_evolution(manual=True)

    def set_patch_status(self, patch_id: str, status: str) -> dict[str, Any]:
        verbs = {"active": "已批准启用", "disabled": "已停用",
                 "rolledback": "已回滚"}
        if status not in verbs:
            return {"ok": False, "error": "未知状态"}
        ok = set_patch(self.evolution, patch_id, status, verbs[status])
        if ok:
            self._agent = None  # 补丁注入变化 → 重建 agent
        return {"ok": ok}

    def approve_skill(self, run_id: str, draft_id: str) -> dict[str, Any]:
        """技能草稿转正：实例化为正式工作流（cron 触发）。"""
        run = next((r for r in self.evolution.runs if r.id == run_id), None)
        draft = next((d for d in (run.skill_drafts if run else [])
                      if d.id == draft_id), None)
        if run is None or draft is None or draft.approved:
            return {"ok": False, "error": "草稿不存在或已转正"}
        draft.approved = True
        self.evolution.save()
        self.workflows.workflows.append(Workflow(
            name=draft.name, desc=draft.desc, trigger="cron",
            steps=[WorkflowStep("数据采集"),
                   WorkflowStep("模型汇总"),
                   WorkflowStep("结果推送")],
        ))
        self.workflows.save()
        log_activity("learn", f"技能草稿「{draft.name}」已批准，转为正式工作流")
        append_audit("user", f"批准技能草稿「{draft.name}」", "confirmed")
        return {"ok": True}

    def save_evolution_settings(self, enabled: bool, auto_apply_l01: bool,
                                require_approval_l2: bool,
                                cron: str = "") -> dict[str, Any]:
        s = self.evolution.settings
        s.enabled = bool(enabled)
        s.auto_apply_l01 = bool(auto_apply_l01)
        s.require_approval_l2 = bool(require_approval_l2)
        if cron.strip() and len(cron.strip().split()) == 5:
            s.cron = cron.strip()
        self.evolution.save()
        if not s.enabled:
            log_activity("cron", "系统进化作业暂停")
        return {"ok": True}

    # ------------------------------------------------------------------
    # chat
    # ------------------------------------------------------------------

    def _build_provider(self):
        if not is_free_route(self.assets.active):
            asset_provider = build_active_provider(self.assets)
            if asset_provider is not None:
                return asset_provider
        kwargs: dict[str, Any] = {}
        if self.config.model:
            kwargs["model"] = self.config.model
        if self.config.api_key:
            kwargs["api_key"] = self.config.api_key
        if self.config.base_url:
            kwargs["base_url"] = self.config.base_url
        spec = (self.config.provider or "").strip()
        if not spec:
            if is_free_route(self.assets.active):
                raise ValueError(
                    "自由路由未命中可用模型，且偏好设置里没有默认 Provider。"
                    "请在「自由路由」添加空关键词的兜底规则，或在对话里选一个具体模型。"
                )
            raise ValueError("没有可用的模型——请在对话里选一个模型，或在偏好设置填写 Provider。")
        return parse_provider_spec(spec, strategy=self.config.strategy, **kwargs)

    @staticmethod
    def _diagnose(exc: Exception) -> str:
        """Turn raw exceptions into actionable Chinese diagnoses."""
        text = str(exc)
        low = text.lower()
        if "connect" in low or "connection refused" in low:
            return ("连不上模型服务——本地模型请确认 Ollama 已启动；"
                    "API 模型请检查 Base URL 与网络。")
        if "timed out" in low or "timeout" in low:
            return "模型响应超时——本地大模型首次加载较慢，可再试一次。"
        if "401" in text or "403" in text or "unauthorized" in low:
            return "API Key 无效或权限不足——请在设置页检查密钥。"
        if "404" in text:
            return "模型或接口不存在（404）——请确认模型名与 Base URL。"
        if isinstance(exc, BudgetExceededError) or "token budget exceeded" in low:
            return (
                "这次任务的 token 用量超过了单次上限。"
                "已完成的部分还在，请开一个新对话继续，"
                "或把思考强度调到「中 / 低」、缩小问题范围后再发。"
            )
        from codeagent.core.agent import MaxIterationsError

        if isinstance(exc, MaxIterationsError) or "did not finish within" in low:
            return (
                "这一轮工具往返次数用完了（模型一直在调工具还没收束）。"
                "请开新对话继续，或把问题拆小、思考强度改成「中 / 低」后再发。"
            )
        if "empty provider spec" in low or "自由路由未命中" in text:
            return ("自由路由没有可用模型——请在「自由路由」加一条关键词留空的兜底规则，"
                    "或在对话里改选一个具体模型/聚合池。")
        if is_transient_serving_error(exc) or "internalerror.algo" in low:
            if "providers failed" in low:
                return ("自由路由试过的模型都失败了。云端返回了 500（服务商内部错误），"
                        "请稍后再发，或在对话里改选本地模型 / DeepSeek。")
            return ("云端模型服务暂时失败（500）。这是通义/网关侧故障，不是本地配置写错。"
                    "请再发一次，或换本地模型、DeepSeek、聚合池。")
        return text[:300]

    def _load_skills(self):
        from codeagent.skills.fusion import ensure_fusion_skills
        from codeagent.videoops import load_all_skills

        try:
            ensure_fusion_skills(DEFAULT_SKILLS_DIR)
        except OSError:
            pass
        return load_all_skills(DEFAULT_SKILLS_DIR)

    THINKING_HINTS = {
        "low": "思考强度=低：快速直接作答，跳过冗长分析，结论优先，能一句说清不写两句",
        "medium": (
            "思考强度=中：正常推理深度，先给结论再补关键依据。"
            "若需要写出中间推理，请用 <think>…</think> 包裹；最终答复写在标签外"
        ),
        "high": (
            "思考强度=高：深入逐步推理——先拆解问题、列出假设与方案，逐一验证后再作答；"
            "复杂问题主动自我检查边界情况。"
            "请把逐步推理写在 <think>…</think> 内，最终结论写在标签外"
        ),
    }

    def _settings_with_patches(self) -> Settings:
        """生效中的行为补丁 + 思考强度注入系统提示（注入即生效）。"""
        rules = list(self.evolution.active_patch_rules())
        hint = self.THINKING_HINTS.get(self.config.thinking)
        if hint:
            rules.append(hint)
        if self._voice_session or self.config.voice_enabled:
            from codeagent.voice.emotion import EMOTION_PROMPT_SUFFIX, VOICE_CHAT_HINT

            rules.append(VOICE_CHAT_HINT.strip())
            rules.append(EMOTION_PROMPT_SUFFIX.strip())
        if self.config.companion_enabled:
            rules.append(self._companion_prompt_rule())
            # 陪伴回复带情绪标签，方便回播/麦克风播报调语气
            if not (self._voice_session or self.config.voice_enabled):
                from codeagent.voice.emotion import EMOTION_PROMPT_SUFFIX
                rules.append(EMOTION_PROMPT_SUFFIX.strip())
        if not rules:
            return self.settings
        from dataclasses import replace

        extra = "；".join(rules)
        instructions = (f"{self.settings.instructions}；{extra}"
                        if self.settings.instructions else extra)
        return replace(self.settings, instructions=instructions)

    def _companion_prompt_rule(self) -> str:
        """Build companion-mode system rule from preference settings."""
        name = (self.config.companion_name or "").strip() or "小暖"
        nature = (self.config.companion_nature or "").strip() or (
            "温柔、会倾听，记得用户说过的细节，口语短句，先情绪后建议"
        )
        user = (self.settings.nickname or "").strip() or "你"
        return (
            f"陪伴模式已开启：你是「{name}」，不是冷冰冰的工具助手。"
            f"性格与说话方式：{nature}。"
            f"称呼用户为「{user}」。"
            "保持人设稳定，主动想起对方提过的细节；不假装真人；"
            "危机话题要关心并建议联系现实援助，不给伤害方法。"
            "可叠用语音播报与嗲嗲声；闲聊优先，事务协助先说明再帮忙。"
        )

    def _effective_max_iterations(self) -> int:
        return clamp_max_iterations(self.config.max_iterations)

    def _build_agent(self, chan: str = "A") -> Agent:
        from codeagent.security.policy import PermissionPolicy

        confirmer = self.confirmer if chan == "A" else self._confirmer2
        on_event = self._on_event if chan == "A" else self._on_event2
        policy = (
            PermissionPolicy.permissive()
            if self.config.auto_yes
            else build_policy(self.perm_levels, confirmer)
        )
        provider = self._build_provider()
        return Agent(
            provider=provider,
            tools=self._agent_tools(),
            permissions=policy,
            max_iterations=self._effective_max_iterations(),
            soft_iterations=True,
            budget=Budget(max_total_tokens=DESKTOP_TOKEN_BUDGET, soft=True),
            compactor=ConversationCompactor(
                provider, CompactionConfig(max_messages=24, keep_recent=8),
            ),
            skills=self._load_skills(),
            settings=self._settings_with_patches(),
            on_event=on_event,
            workspace_hints=self._workspace_skill_hints(),
        )

    def _implicit_free_route_targets(self) -> list[str]:
        """No keyword/fallback rule: mixture → API models → local chat models."""
        refs: list[str] = []
        seen: set[str] = set()

        def add(ref: str) -> None:
            if ref and ref not in seen:
                seen.add(ref)
                refs.append(ref)

        for mix in self.assets.mixtures:
            if mix.enabled:
                add(f"mix:{mix.id}")
        for am in self.assets.api_models:
            add(f"api:{am.id}")
        if refs:
            return refs
        probed = self._probed_local()
        for ep in self.assets.endpoints:
            if ep.kind in ("gradio", "comfy"):
                continue
            for name in probed.get(ep.id, []) or []:
                add(f"local:{name}@{ep.id}")
        return refs

    def _implicit_free_route_target(self) -> str:
        """First implicit target, or empty."""
        refs = self._implicit_free_route_targets()
        return refs[0] if refs else ""

    def _try_build_ref(self, ref: str):
        saved = self.assets.active
        self.assets.active = ref
        try:
            return build_active_provider(self.assets)
        finally:
            self.assets.active = saved

    def _provider_for_message(self, text: str):
        """自由路由时按规则分发；钉死具体模型则直连，不改道。"""
        decision = route_message(text, self.router, self._target_label)
        if not is_free_route(self.assets.active):
            decision = {
                **decision,
                "strategy": "默认直连",
                "reason": "已指定模型，跳过自由路由",
                "chosen": self._active_label(),
                "candidates": [],
            }
            return self._build_provider(), decision
        target = (decision.get("target") or "").strip()
        candidates: list[str] = []
        if target:
            candidates.append(target)
        else:
            candidates.extend(self._implicit_free_route_targets())
            if candidates:
                pick = candidates[0]
                label = self._target_label(pick)
                decision = {
                    **decision,
                    "strategy": "兜底分发",
                    "reason": "未命中关键词规则，走默认聚合池或可用模型",
                    "target": pick,
                    "chosen": label,
                    "candidates": [label],
                }
        for cand in candidates:
            provider = self._try_build_ref(cand)
            if provider is None:
                continue
            if not cand.startswith("mix:"):
                provider = self._with_route_backups(provider, cand)
            if cand != target:
                label = self._target_label(cand)
                decision = {
                    **decision,
                    "strategy": "兜底分发",
                    "reason": decision.get("reason") or "未命中关键词规则，走可用模型",
                    "target": cand,
                    "chosen": label,
                    "candidates": [label],
                }
            return provider, decision
        # 无规则/无聚合池/无本地模型时，退回偏好设置里的默认 Provider
        return self._build_provider(), decision

    def _with_route_backups(self, primary, target: str):
        """Keyword-routed single model: keep it first, fail over to the mixture."""
        from codeagent.desktop.models import _build_member

        mix = next((m for m in self.assets.mixtures if m.enabled), None)
        refs: list[str] = []
        if mix is not None:
            refs.extend(mix.members)
            if mix.fallback:
                refs.append(mix.fallback)
        else:
            refs.extend(f"api:{am.id}" for am in self.assets.api_models)
        backups = []
        seen = {f"{primary.name}:{primary.model}"}
        for ref in refs:
            if not ref or ref == target:
                continue
            extra = _build_member(self.assets, ref)
            if extra is None:
                continue
            key = f"{extra.name}:{extra.model}"
            if key in seen:
                continue
            seen.add(key)
            backups.append(extra)
        if not backups:
            return primary
        return AggregateProvider([primary, *backups], strategy="fallback")

    # ------------------------------------------------------------------
    # attachments / clipboard / share (对话页)
    # ------------------------------------------------------------------

    def pick_attachments(self) -> list[dict[str, Any]]:
        """系统文件选择器 → 读取所有选中文件，返回附件描述列表。"""
        if self._window is None:
            return []
        import webview

        paths = self._window.create_file_dialog(
            webview.OPEN_DIALOG, allow_multiple=True)
        if not paths:
            return []
        from codeagent.desktop.attachments import read_attachment

        for p in paths:
            self._ingest_attachment(Path(p))
        return list(self._attachments)

    def _ingest_attachment(self, src: Path) -> dict[str, Any]:
        """读取附件并复制进当前项目 files/（所有文件、内容都落在项目文件夹）。"""
        from codeagent.desktop.attachments import read_attachment

        try:
            info = read_attachment(src)
        except OSError as exc:
            info = {"name": src.name, "size": "-", "ext": "",
                    "kind": "binary", "text": "", "note": f"读取失败：{exc}"}
        proj = self.projects.get(self.projects.active)
        if proj is not None and src.is_file():
            try:
                dest = ingest_file(proj, src)
                info["saved"] = str(dest)
                extra = f"已保存到项目/files/{dest.name}"
                info["note"] = f"{info['note']} · {extra}" if info.get("note") else extra
            except OSError:
                pass
        self._attachments.append(info)
        return info

    def remove_attachment(self, index: int) -> list[dict[str, Any]]:
        if 0 <= int(index) < len(self._attachments):
            self._attachments.pop(int(index))
        return list(self._attachments)

    def copy_text(self, text: str) -> bool:
        """系统剪贴板写入（pbcopy / clip UTF-16 / xclip）。"""
        return _clipboard_copy(text)

    def read_clipboard(self) -> str:
        """系统剪贴板读取（pbpaste / Get-Clipboard / xclip）。"""
        return _clipboard_paste()

    def speak_text(self, text: str) -> bool:
        """回播一段对话正文（不依赖「打字提问也播报」开关）。"""
        if not (text or "").strip():
            return False
        self.stop_speaking()
        self._speak(text, force=True)
        return True

    def export_message(self, text: str) -> dict[str, Any]:
        """分享：把消息导出为 Markdown 文件（系统保存对话框）。"""
        if self._window is None:
            return {"ok": False}
        import webview

        path = self._window.create_file_dialog(
            webview.SAVE_DIALOG, save_filename="codeagent-回复.md",
            file_types=("Markdown (*.md)", "All files (*.*)"))
        if not path:
            return {"ok": False}
        if isinstance(path, (tuple, list)):
            path = path[0]
        try:
            Path(path).write_text(text, encoding="utf-8")
            log_activity("share", f"导出分享：{Path(path).name}")
            return {"ok": True, "path": str(path)}
        except OSError as exc:
            return {"ok": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # projects（项目工作区：文件夹 + 全量对话记录）
    # ------------------------------------------------------------------

    def get_projects(self) -> dict[str, Any]:
        proj = self.projects.get(self.projects.active)
        return {
            "projects": [asdict(p) for p in self.projects.projects],
            "active": self.projects.active,
            "active_path": proj.path if proj else "",
            "default_base": str(DEFAULT_BASE.expanduser()),
            "categories": list(CATEGORIES),
        }

    def create_project(self, name: str, base: str = "",
                       category: str = "其他") -> dict[str, Any]:
        try:
            proj = self.projects.create(name, base, category)
        except (OSError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}
        self._activate_project(proj.id)
        log_activity("project", f"新建项目：{proj.name}（{proj.path}）")
        return {"ok": True, "project": asdict(proj)}

    def get_project_records(self) -> dict[str, Any]:
        """当前项目的全部记录：对话 + 文件夹内文件。"""
        proj = self.projects.get(self.projects.active)
        if proj is None:
            return {"ok": False, "project": None, "conversations": [], "files": []}
        return {
            "ok": True,
            "project": asdict(proj),
            "conversations": list_conversations(proj),
            "files": list_files(proj),
        }

    def open_project_folder(self) -> dict[str, Any]:
        """在系统文件管理器中打开当前项目文件夹。"""
        import subprocess
        import sys

        proj = self.projects.get(self.projects.active)
        if proj is None:
            return {"ok": False, "error": "没有激活的项目"}
        path = Path(proj.path)
        try:
            if sys.platform == "darwin":
                subprocess.run(["open", str(path)], check=True, timeout=5)
            elif sys.platform == "win32":
                subprocess.run(["explorer", str(path)], check=True, timeout=5)
            else:
                subprocess.run(["xdg-open", str(path)], check=True, timeout=5)
            return {"ok": True, "path": str(path)}
        except (subprocess.SubprocessError, OSError) as exc:
            return {"ok": False, "error": str(exc)}

    def switch_project(self, pid: str) -> dict[str, Any]:
        proj = self.projects.get(pid)
        if proj is None:
            return {"ok": False, "error": "项目不存在"}
        self._activate_project(pid)
        log_activity("project", f"切换到项目：{proj.name}")
        return {"ok": True, "project": asdict(proj)}

    def delete_project(self, pid: str) -> bool:
        """仅从索引移除；本地文件夹与对话记录全部保留。"""
        proj = self.projects.get(pid)
        ok = self.projects.remove(pid)
        if ok:
            log_activity("project", f"移除项目：{proj.name}（文件夹保留）")
            if self.projects.active:
                self._activate_project(self.projects.active)
            else:
                self.root = Path.cwd()
                self._agent = None
                self._conv_id = None
                self._agent2 = None
                self._conv_id2 = None
        return ok

    def _activate_project(self, pid: str) -> None:
        self.projects.touch(pid)
        proj = self.projects.get(pid)
        self.root = Path(proj.path)
        self._agent = None       # 重建 agent 以使用新工作目录
        self._conv_id = None     # 新项目开新对话
        self._conv_seed: list[dict[str, Any]] = []
        # 第二对话进程也随项目切换重置
        self._agent2 = None
        self._conv_id2 = None
        self._conv_seed2 = []

    def get_conversations(self) -> dict[str, Any]:
        proj = self.projects.get(self.projects.active)
        if proj is None:
            return {"project": "", "items": [], "current": ""}
        return {"project": proj.name, "items": list_conversations(proj),
                "current": self._conv_id or ""}

    def new_conversation(self) -> dict[str, Any]:
        self._conv_id = None
        self._conv_seed = []
        return {"ok": True}

    def load_conversation(self, conv_id: str) -> dict[str, Any]:
        proj = self.projects.get(self.projects.active)
        if proj is None:
            return {"ok": False, "messages": []}
        msgs = load_conversation(proj, conv_id)
        self._conv_id = conv_id
        self._conv_seed = msgs[-10:]  # 继续对话时作为上下文带入
        return {"ok": True, "messages": msgs}

    def get_second_state(self) -> dict[str, Any]:
        """第二对话进程（B）的状态：是否忙碌、当前对话 id。"""
        return {"busy": self._busy2, "current": self._conv_id2 or ""}

    def open_second_window(self) -> dict[str, Any]:
        """在项目里打开第二个独立对话窗口（B 对话进程）。
        从后台线程创建第二个 webview 窗口；pywebview 在 start() 之后由
        非主线程 create_window 会立即实例化窗口。"""
        if self._window_b is not None:
            return {"ok": True, "opened": False, "already": True}

        def _create() -> None:
            try:
                import webview
            except ImportError:
                self._push(
                    "status", chan="B",
                    text="桌面版需要 pywebview：pip install codeagent[desktop]",
                )
                return
            from codeagent.desktop.ui import CHAT_HTML
            from codeagent.desktop.brand_mark import MARK_URI

            html = CHAT_HTML.replace("__BRAND_MARK_SRC__", MARK_URI)
            theme = self.config.theme
            light = theme == "light" or (theme == "auto" and self._system_light())
            if light:
                html = html.replace("<body>", '<body class="light">', 1)
            win = webview.create_window(
                "CodeCoreAgent · 对话 B",
                html=html,
                js_api=self,
                width=860,
                height=760,
                min_size=(640, 500),
                text_select=True,
            )
            if win is not None:
                self._window_b = win
                try:
                    win.events.closed += lambda: setattr(self, "_window_b", None)
                except Exception:  # noqa: BLE001 — 关闭事件绑定失败不影响窗口
                    log.warning("无法绑定对话 B 窗口关闭事件")

        threading.Thread(target=_create, daemon=True).start()
        return {"ok": True, "opened": True}

    def set_dual_mode(self, on: bool) -> bool:
        """开启「双对话」时主窗口加宽 0.5 倍（1.5×），关闭时还原。
        双面板需要更宽视口容纳 A/B 两列，避免内容拥挤。"""
        w = self._window
        if w is None:
            return False
        base_w = getattr(w, "initial_width", None) or 1440
        base_h = getattr(w, "initial_height", None) or 900
        try:
            if on:
                w.resize(int(base_w * 1.5), base_h)
            else:
                w.resize(int(base_w), base_h)
        except Exception:  # noqa: BLE001 — 缩放失败不阻塞界面
            log.warning("dual mode resize failed")
            return False
        return True

    def _system_light(self) -> bool:
        """macOS 系统外观检测（auto 主题用）：无 AppleInterfaceStyle 键 = 浅色。"""
        import sys

        if sys.platform != "darwin":
            return False
        import subprocess

        try:
            subprocess.run(
                ["defaults", "read", "-g", "AppleInterfaceStyle"],
                capture_output=True, check=True, timeout=2,
            )
            return False  # 键存在 → 深色
        except (subprocess.CalledProcessError, FileNotFoundError,
                subprocess.TimeoutExpired):
            return True

    def new_conversation2(self) -> dict[str, Any]:
        self._conv_id2 = None
        self._conv_seed2 = []
        return {"ok": True}

    def load_conversation2(self, conv_id: str) -> dict[str, Any]:
        proj = self.projects.get(self.projects.active)
        if proj is None:
            return {"ok": False, "messages": []}
        msgs = load_conversation(proj, conv_id)
        self._conv_id2 = conv_id
        self._conv_seed2 = msgs[-10:]  # 继续对话时作为上下文带入
        return {"ok": True, "messages": msgs}

    def send2(
        self,
        text: str,
        resolution: str = "720p",
        num_frames: int = 60,
        num_inference_steps: int = 50,
    ) -> bool:
        """第二对话进程（B）：与主对话并发，记录保留在项目文件夹。"""
        text = (text or "").strip()
        if not text:
            return False
        with self._lock2:
            if self._busy2:
                return False
            self._busy2 = True
            self._cancel2.clear()
        proj = self.projects.get(self.projects.active)
        display = text
        if getattr(self, "_conv_seed2", None):  # 续接历史对话：带上下文
            seed = _format_conv_seed(self._conv_seed2)
            if seed:
                text = f"（本会话之前的对话记录）\n{seed}\n\n（用户新消息）\n{text}"
            self._conv_seed2 = []
        if proj is not None:
            if not self._conv_id2:
                self._conv_id2 = new_conversation_id()
            append_message(proj, self._conv_id2, "user", display)
        job = self._active_video_job()
        if job is not None:
            threading.Thread(
                target=self._run_video_gen2,
                args=(text, resolution, int(num_frames), int(num_inference_steps), job),
                daemon=True,
            ).start()
        else:
            threading.Thread(target=self._run_chat2, args=(text,), daemon=True).start()
        return True

    def stop2(self) -> bool:
        """Interrupt the in-flight second conversation (B)."""
        with self._lock2:
            if not self._busy2:
                return False
            self._cancel2.set()
            loop = self._loop2
        self._confirmer2.cancel_all()
        if loop is not None and loop.is_running():
            def _cancel_all() -> None:
                for task in asyncio.all_tasks(loop):
                    task.cancel()

            try:
                loop.call_soon_threadsafe(_cancel_all)
            except RuntimeError:
                pass
        return True

    def reset2(self) -> bool:
        if self._agent2 is not None:
            self._agent2.reset()
        self._agent2 = None
        return True

    def send(
        self,
        text: str,
        resolution: str = "720p",
        num_frames: int = 60,
        num_inference_steps: int = 50,
    ) -> bool:
        text = (text or "").strip()
        if not text and not self._attachments:
            return False
        with self._lock:
            if self._busy:
                return False
            self._busy = True
            self._cancel.clear()
        proj = self.projects.get(self.projects.active)
        display = text
        if self._attachments:  # 附件内容拼到消息前面，发送后清空
            from codeagent.desktop.attachments import format_attachments

            names = "、".join(a["name"] for a in self._attachments)
            block = format_attachments(self._attachments)
            text = f"{block}\n\n{text}" if text else block
            self._attachments = []
            display = f"{display}\n📎 {names}".strip()
        if getattr(self, "_conv_seed", None):  # 续接历史对话：带上下文
            seed = _format_conv_seed(self._conv_seed)
            if seed:
                text = f"（本会话之前的对话记录）\n{seed}\n\n（用户新消息）\n{text}"
            self._conv_seed = []
        if proj is not None:  # 所有对话保留在项目文件夹
            if not self._conv_id:
                self._conv_id = new_conversation_id()
            append_message(proj, self._conv_id, "user", display)
        job = self._active_video_job()
        if job is not None:
            threading.Thread(
                target=self._run_video_gen,
                args=(text, resolution, int(num_frames), int(num_inference_steps), job),
                daemon=True,
            ).start()
        else:
            threading.Thread(target=self._run_chat, args=(text,), daemon=True).start()
        return True

    def stop(self) -> bool:
        """Interrupt the in-flight chat (or lead) from the UI stop button."""
        with self._lock:
            if not self._busy:
                return False
            self._cancel.set()
            loop = self._loop
        self.confirmer.cancel_all()
        try:
            from codeagent.voice.tts import stop_audio
            stop_audio()
        except Exception:  # noqa: BLE001
            pass
        if loop is not None and loop.is_running():
            def _cancel_all() -> None:
                for task in asyncio.all_tasks(loop):
                    task.cancel()

            try:
                loop.call_soon_threadsafe(_cancel_all)
            except RuntimeError:
                pass
        return True

    def _run_chat(self, text: str) -> None:
        self._run_chat_chan(text, "A")

    def _run_chat2(self, text: str) -> None:
        self._run_chat_chan(text, "B")

    def _run_chat_chan(self, text: str, chan: str) -> None:
        is_a = chan == "A"
        lock = self._lock if is_a else self._lock2
        cancel = self._cancel if is_a else self._cancel2
        busy_attr = "_busy" if is_a else "_busy2"
        agent_attr = "_agent" if is_a else "_agent2"
        loop_attr = "_loop" if is_a else "_loop2"
        conv_id = self._conv_id if is_a else self._conv_id2
        stopped = False
        try:
            if cancel.is_set():
                stopped = True
                return
            provider, decision = self._provider_for_message(text)
            if cancel.is_set():
                stopped = True
                return
            if decision["strategy"] == "默认直连":
                if getattr(self, agent_attr) is None:
                    self._push("status", chan=chan, text="正在连接模型…")
                    setattr(self, agent_attr, self._build_agent(chan=chan))
                agent = getattr(self, agent_attr)
                agent.workspace_hints = self._workspace_skill_hints()
            else:
                self._push("status", chan=chan,
                           text=f"路由：{decision['taskType']} → {decision['chosen']}")
                agent = self._build_agent_with(provider, chan=chan)
            agent.settings = self._settings_with_patches()
            if cancel.is_set():
                stopped = True
                return

            self._chat_browser_urls = []

            async def _go() -> str:
                setattr(self, loop_attr, asyncio.get_running_loop())
                try:
                    return await agent.run(text)
                finally:
                    setattr(self, loop_attr, None)

            try:
                answer = asyncio.run(_go())
            except asyncio.CancelledError:
                stopped = True
                return
            if cancel.is_set():
                stopped = True
                return
            proj = self.projects.get(self.projects.active)
            emotion_name = ""
            display = answer
            try:
                from codeagent.voice.emotion import parse_emotion
                emotion, display = parse_emotion(answer)
                emotion_name = emotion.value
            except Exception:  # noqa: BLE001
                pass
            if proj is not None and conv_id:
                append_message(proj, conv_id, "assistant", display)
            try:
                self._maybe_showcase_website(text, display or answer or "", agent, chan)
            except Exception:  # noqa: BLE001
                log.exception("website showcase")
            self._push("done", chan=chan, text=display, emotion=emotion_name)
            self._speak(answer)
        except Exception as exc:  # noqa: BLE001 — surface to the UI
            if cancel.is_set():
                stopped = True
                return
            log.exception("chat failed")
            self._push("error", chan=chan, text=self._diagnose(exc))
        finally:
            with lock:
                setattr(self, busy_attr, False)
            if stopped:
                proj = self.projects.get(self.projects.active)
                if proj is not None and conv_id:
                    append_message(proj, conv_id, "assistant", "（已停止）")
                self._push("stopped", chan=chan, text="已停止")

    def _run_video_gen(
        self,
        prompt: str,
        resolution: str,
        num_frames: int,
        num_inference_steps: int,
        job: dict[str, Any] | None = None,
    ) -> None:
        self._run_video_gen_chan(prompt, resolution, num_frames, num_inference_steps, job, "A")

    def _run_video_gen2(
        self,
        prompt: str,
        resolution: str,
        num_frames: int,
        num_inference_steps: int,
        job: dict[str, Any] | None = None,
    ) -> None:
        self._run_video_gen_chan(prompt, resolution, num_frames, num_inference_steps, job, "B")

    def _run_video_gen_chan(
        self,
        prompt: str,
        resolution: str,
        num_frames: int,
        num_inference_steps: int,
        job: dict[str, Any] | None,
        chan: str,
    ) -> None:
        import time as time_mod

        from codeagent.videoops import (
            VideoOpsConfig,
            append_pipeline,
            bootstrap_workspace,
        )
        from codeagent.videoops.cloud import generate_cloud_video
        from codeagent.videoops.gradio import generate_wan_video

        is_a = chan == "A"
        cancel = self._cancel if is_a else self._cancel2
        lock = self._lock if is_a else self._lock2
        busy_attr = "_busy" if is_a else "_busy2"
        conv_id = self._conv_id if is_a else self._conv_id2
        stopped = False
        try:
            if cancel.is_set():
                stopped = True
                return
            job = job or self._active_video_job()
            if job is None:
                self._push("error", chan=chan, text="当前不是文生视频模型")
                return
            cfg = VideoOpsConfig.load()
            root = cfg.workspace()
            bootstrap_workspace(root)
            dest = root / "02-generate" / f"{job.get('backend', 'video')}-{int(time_mod.time())}.mp4"
            self._push("status", chan=chan, text="正在生成视频…")
            backend = job.get("backend") or "wan"
            if backend == "wan":
                ep = self._active_video_ep()
                if ep is None:
                    self._push("error", chan=chan, text="当前不是文生视频模型")
                    return
                result = asyncio.run(generate_wan_video(
                    ep.base, prompt, resolution, num_frames, num_inference_steps,
                    dest=dest,
                ))
            else:
                result = asyncio.run(generate_cloud_video(
                    prompt, dest, backend=backend,
                    resolution=resolution, num_frames=num_frames,
                    model=str(job.get("model") or ""),
                ))
            if cancel.is_set():
                stopped = True
                return
            if not result.get("ok"):
                self._push("error", chan=chan, text=result.get("error") or "视频生成失败")
                return
            path = str(result.get("path") or dest)
            append_pipeline(root, f"{backend} 生成 {Path(path).name}（{resolution}）")
            answer = f"视频已生成：{path}"
            proj = self.projects.get(self.projects.active)
            if proj is not None and conv_id:
                append_message(proj, conv_id, "assistant", answer)
            self._push("done", chan=chan, text=answer)
        except Exception as exc:  # noqa: BLE001 — surface to the UI
            if cancel.is_set():
                stopped = True
                return
            log.exception("video gen failed")
            self._push("error", chan=chan, text=self._diagnose(exc))
        finally:
            with lock:
                setattr(self, busy_attr, False)
            if stopped:
                self._push("stopped", chan=chan, text="已停止")

    def _workspace_skill_hints(self) -> str:
        """Project files + category so the model can recognize the work."""
        from codeagent.skills.runtime import workspace_skill_hints
        from codeagent.videoops import VideoOpsConfig

        extra: list[str] = []
        proj = self.projects.get(self.projects.active)
        root = Path(self.root) if self.root else None
        if proj is not None:
            extra.append(f"项目 {proj.name} 分类 {proj.category}")
            root = Path(proj.path).expanduser()
        try:
            vo = VideoOpsConfig.load()
            if vo.workspace().is_dir():
                extra.append("视频运营工作区已布置 短视频")
        except OSError:
            pass
        return workspace_skill_hints(root, extra=" ".join(extra))

    # ------------------------------------------------------------------
    # internal browser (GUI pump + live window)
    # ------------------------------------------------------------------

    def browser_pump(self) -> int:
        """Drain GUI jobs for the in-app browser window. Called from JS."""
        return self._browser_host.pump()

    def browser_status(self) -> dict[str, Any]:
        return self._browser.ui_state()

    def browser_goto(self, url: str) -> dict[str, Any]:
        """Open a page in the internal browser (worker thread + GUI pump)."""

        def work() -> None:
            try:
                asyncio.run(self._browser.run("navigate", url=url))
            except Exception as exc:  # noqa: BLE001
                log.exception("browser goto")
                self._push("browser", error=str(exc)[:300], **self._browser.ui_state())
                return
            self._push("browser", **self._browser.ui_state())

        threading.Thread(target=work, name="cca-browser", daemon=True).start()
        return {"ok": True, "url": url}

    def browser_reload(self) -> dict[str, Any]:
        url = self._browser.url
        if not url:
            return {"ok": False, "error": "还没有打开页面"}
        return self.browser_goto(url)

    def browser_show_window(self) -> dict[str, Any]:
        try:
            self._browser_host.ensure_window(
                self._browser.url or "about:blank", queued=False,
            )
            return {"ok": True}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)[:200]}

    def _agent_tools(self):
        """Default tools + knowledge vault + video ops when configured."""
        from codeagent.knowledge.tools import knowledge_tools
        from codeagent.videoops.tools import video_ops_tools

        registry = default_tools(self.root)
        registry.register(BrowserTool(engine=self._browser))
        for tool in knowledge_tools() + video_ops_tools():
            registry.register(tool)
        return registry

    def _build_agent_with(self, provider, chan: str = "A") -> Agent:
        """一次性路由 agent：不缓存（规则目标随消息而变）。"""
        from codeagent.security.policy import PermissionPolicy

        confirmer = self.confirmer if chan == "A" else self._confirmer2
        on_event = self._on_event if chan == "A" else self._on_event2
        policy = (
            PermissionPolicy.permissive()
            if self.config.auto_yes
            else build_policy(self.perm_levels, confirmer)
        )
        return Agent(
            provider=provider,
            tools=self._agent_tools(),
            permissions=policy,
            max_iterations=self._effective_max_iterations(),
            soft_iterations=True,
            budget=Budget(max_total_tokens=DESKTOP_TOKEN_BUDGET, soft=True),
            compactor=ConversationCompactor(
                provider, CompactionConfig(max_messages=24, keep_recent=8),
            ),
            skills=self._load_skills(),
            settings=self._settings_with_patches(),
            on_event=on_event,
            workspace_hints=self._workspace_skill_hints(),
        )

    def reset(self) -> bool:
        if self._agent is not None:
            self._agent.reset()
        self._agent = None
        return True

    # ------------------------------------------------------------------
    # voice reply
    # ------------------------------------------------------------------

    def set_voice_session(self, on: bool = True) -> dict[str, Any]:
        """Start or stop continuous listen→think→speak on the chat page."""
        self._voice_session = bool(on)
        if not self._voice_session:
            try:
                self.stop_native_listen()
            except Exception:  # noqa: BLE001
                pass
            try:
                from codeagent.voice.tts import stop_audio
                stop_audio()
            except Exception:  # noqa: BLE001
                pass
            self._push("voice", state="idle")
        else:
            self._push("voice", state="listening")
        return {"ok": True, "on": self._voice_session}

    def start_native_listen(self, locale: str = "zh-CN") -> dict[str, Any]:
        """Use macOS Speech framework (not WKWebView webkitSpeechRecognition).

        Starts on a background thread so the UI bridge never freezes while the
        audio engine / Speech framework initializes.
        """
        from codeagent.desktop.voice_listen import NativeSpeechSession

        if self._native_listen is None:
            self._native_listen = NativeSpeechSession()

        last_partial = {"t": 0.0, "text": ""}

        def on_text(text: str, final: bool) -> None:
            if final:
                self._push("voice", state="heard", text=text)
                return
            # Throttle partials — Speech fires dozens/sec; each used to block on
            # evaluate_js and freeze the window.
            now = time.monotonic()
            if text == last_partial["text"] and now - last_partial["t"] < 0.35:
                return
            if now - last_partial["t"] < 0.18 and not final:
                return
            last_partial["t"] = now
            last_partial["text"] = text
            self._push("voice", state="partial", text=text)

        def on_error(message: str) -> None:
            self._push("voice", state="listen_error", text=message)

        def _work() -> None:
            try:
                result = self._native_listen.start(
                    on_text, on_error, locale=locale or "zh-CN",
                )
            except Exception as exc:  # noqa: BLE001
                log.exception("native listen worker failed")
                self._push(
                    "voice", state="listen_error",
                    text=str(exc)[:180], open_settings=True,
                )
                return
            if result.get("ok"):
                self._push("voice", state="listening")
                return
            self._push(
                "voice",
                state="listen_error",
                text=result.get("error") or "无法启动系统听写",
                path=result.get("path") or "",
                open_settings=bool(result.get("open_settings")),
            )

        threading.Thread(target=_work, daemon=True, name="cca-native-listen").start()
        return {"ok": True, "async": True, "engine": "speech.framework"}

    def stop_native_listen(self) -> bool:
        sess = self._native_listen
        if sess is not None:
            sess.stop()
        return True

    def mic_permission_status(self) -> dict[str, Any]:
        """Query OS microphone / speech TCC status (instant, no dialogs)."""
        from codeagent.desktop.mic import mic_permission_status

        return mic_permission_status()

    def ensure_mic_permission(self) -> dict[str, Any]:
        """Gate voice start: authorized, need browser prompt, or open Settings."""
        from codeagent.desktop.mic import ensure_mic_permission

        return ensure_mic_permission()

    def request_mic_access(self) -> dict[str, Any]:
        """向系统申请麦克风 + 语音识别权限（短超时，避免卡死界面）。"""
        from codeagent.desktop.mic import request_mic_access

        return request_mic_access()

    def open_mic_settings(self) -> dict[str, Any]:
        """Open system Privacy → Microphone settings."""
        from codeagent.desktop.mic import open_mic_settings

        return open_mic_settings()

    def open_speech_settings(self) -> dict[str, Any]:
        """Open system Privacy → Speech Recognition settings."""
        from codeagent.desktop.mic import open_speech_settings

        return open_speech_settings()

    def stop_speaking(self) -> bool:
        try:
            from codeagent.voice.tts import stop_audio
            stop_audio()
        except Exception:  # noqa: BLE001
            return False
        # Notify UI; do not start another engine — cancel is final for this utterance.
        self._push("voice", state="spoken")
        return True

    def _should_speak(self) -> bool:
        return self._voice_session or self.config.voice_enabled

    def _speak(self, text: str, force: bool = False) -> None:
        # Mic continuous session must always voice-answer after the user speaks.
        speak = force or self._should_speak()
        if not speak or not (text or "").strip():
            if self._voice_session:
                self._push("voice", state="spoken")
            return

        def _play() -> None:
            from codeagent.voice.tts import (
                PlaybackCancelled,
                begin_utterance,
                playback_generation,
            )

            gen = begin_utterance()
            try:
                from codeagent.voice.emotion import parse_emotion, style_for
                from codeagent.voice.speech import cute_style, overlay_style, to_speech_text
                from codeagent.voice.tts import EdgeTTSProvider, resolve_voice, system_say

                emotion, clean = parse_emotion(text)
                spoken = to_speech_text(clean, max_len=800)
                if not spoken:
                    spoken = " ".join((clean or "").split())[:800]
                if not spoken:
                    self._push("voice", state="error", text="这条没有可朗读的文字")
                    return
                if playback_generation() != gen:
                    return
                self._push("voice", state="speaking", emotion=emotion.value)

                # Continuous mic chat: prefer OS say first (fast, offline), then
                # edge-tts. Typing "voice_enabled" still prefers neural edge.
                prefer_system = bool(self._voice_session)

                async def _go() -> None:
                    from codeagent.voice.tts import play_audio as _play_file

                    if playback_generation() != gen:
                        raise PlaybackCancelled()
                    if prefer_system:
                        try:
                            await asyncio.get_running_loop().run_in_executor(
                                None, lambda: system_say(spoken, self.config.voice_name)
                            )
                            return
                        except PlaybackCancelled:
                            raise
                        except Exception:
                            log.exception("system_say failed, trying edge-tts")

                    tts = EdgeTTSProvider(
                        voice=resolve_voice(self.config.voice_name),
                        emotion_voices=False,
                    )
                    style = overlay_style(
                        style_for(emotion),
                        cute_style(
                            self.config.voice_pitch,
                            self.config.voice_rate,
                            self.config.voice_cute_tone,
                        ),
                    )
                    style = type(style)(
                        voice=None,
                        rate=style.rate,
                        pitch=style.pitch,
                    )
                    try:
                        path = await tts.synthesize(spoken, style=style)
                        if playback_generation() != gen:
                            raise PlaybackCancelled()
                        await _play_file(path)
                    except PlaybackCancelled:
                        raise
                    except Exception:
                        if playback_generation() != gen:
                            raise PlaybackCancelled()
                        log.exception(
                            "edge-tts playback failed, falling back to system voice"
                        )
                        await asyncio.get_running_loop().run_in_executor(
                            None, lambda: system_say(spoken, self.config.voice_name)
                        )

                try:
                    asyncio.run(_go())
                except PlaybackCancelled:
                    return
                except Exception as exc:  # noqa: BLE001
                    if playback_generation() != gen:
                        return
                    log.exception("tts failed")
                    self._push("voice", state="error", text=str(exc)[:180])
            finally:
                if playback_generation() == gen:
                    self._push("voice", state="spoken")

        threading.Thread(target=_play, daemon=True, name="cca-tts").start()

    # ------------------------------------------------------------------
    # leader command center
    # ------------------------------------------------------------------

    def _leader_workers(self):
        from codeagent.leader import WorkerConfig

        raw = self.config.workers_json.strip()
        if raw:
            try:
                items = json.loads(raw)
                roster = [
                    WorkerConfig(
                        name=w.get("name", f"worker{i+1}"),
                        provider=w.get("provider", self.config.provider),
                        model=w.get("model") or None,
                        description=w.get("description", ""),
                    )
                    for i, w in enumerate(items)
                ]
                if roster:
                    return roster
            except (json.JSONDecodeError, TypeError, AttributeError):
                log.warning("workers_json invalid, falling back to default")
        return [WorkerConfig(
            name="worker",
            provider=self.config.provider,
            model=self.config.model or None,
            description="默认工人",
        )]

    def lead(self, text: str) -> bool:
        text = (text or "").strip()
        if not text:
            return False
        with self._lock:
            if self._busy:
                return False
            self._busy = True
            self._cancel.clear()
        threading.Thread(target=self._run_lead, args=(text,), daemon=True).start()
        return True

    def _run_lead(self, text: str) -> None:
        stopped = False
        try:
            from codeagent.harness import discover_harnesses
            from codeagent.leader import Leader, ProgressBoard, RunArchive

            board = ProgressBoard(
                on_change=lambda r: self._push(
                    "task", id=r.task_id, title=r.title, worker=r.worker,
                    status=r.status, detail=r.detail,
                )
            )
            leader = Leader(
                provider=self._build_provider(),
                workers=self._leader_workers(),
                root=self.root,
                skills=self._load_skills(),
                board=board,
                harnesses=discover_harnesses(),
                archive=RunArchive(),
                settings=self.settings,
                max_parallel=2,
                on_event=lambda kind, data: self._push("lead", event=kind, data=data),
            )

            async def _go() -> str:
                self._loop = asyncio.get_running_loop()
                try:
                    return await leader.command(text)
                finally:
                    self._loop = None

            try:
                reply = asyncio.run(_go())
            except asyncio.CancelledError:
                stopped = True
                return
            if self._cancel.is_set():
                stopped = True
                return
            self._push("lead_done", text=reply)
            self._speak(reply)
        except Exception as exc:  # noqa: BLE001
            if self._cancel.is_set():
                stopped = True
                return
            log.exception("lead failed")
            self._push("error", text=str(exc))
        finally:
            with self._lock:
                self._busy = False
            if stopped:
                self._push("stopped", text="已停止")

    def get_runs(self) -> list[dict[str, Any]]:
        from codeagent.leader import RunArchive

        try:
            return RunArchive().list(self.root)[:20]
        except Exception:  # noqa: BLE001
            return []

    # ------------------------------------------------------------------
    # memory
    # ------------------------------------------------------------------

    def _memory_store(self):
        from codeagent.memory import LocalMemoryStore

        return LocalMemoryStore(MEMORY_PATH.expanduser())

    def get_memories(self, query: str = "") -> list[dict[str, Any]]:
        store = self._memory_store()
        try:
            if query.strip():
                items = asyncio.run(store.search(query, limit=50))
            else:
                items = asyncio.run(store.list(limit=100))
        except Exception:  # noqa: BLE001
            return []
        return [
            {"id": m.id, "content": m.content, "created_at": m.created_at}
            for m in items
        ]

    def add_memory(self, content: str) -> bool:
        content = (content or "").strip()
        if not content:
            return False
        try:
            asyncio.run(self._memory_store().add(content))
            return True
        except Exception:  # noqa: BLE001
            return False

    def delete_memory(self, memory_id: str) -> bool:
        try:
            return bool(asyncio.run(self._memory_store().delete(memory_id)))
        except Exception:  # noqa: BLE001
            return False

    # ------------------------------------------------------------------
    # knowledge base (Obsidian / LLM Wiki vault)
    # ------------------------------------------------------------------

    def get_knowledge(self) -> dict[str, Any]:
        from dataclasses import asdict

        from codeagent.knowledge import KnowledgeConfig, list_pages, vault_status

        cfg = KnowledgeConfig.load()
        st = vault_status(cfg.vault_path())
        pages = []
        if st["ready"]:
            pages = [
                {
                    "rel": p.rel,
                    "title": p.title,
                    "preview": p.preview,
                    "mtime": p.mtime,
                    "size": p.size,
                }
                for p in list_pages(cfg.vault_path(), limit=40)
            ]
        return {"config": asdict(cfg), "status": st, "pages": pages}

    def save_knowledge_config(
        self,
        path: str = "",
        mode: str = "local",
        backend: str = "obsidian",
        enabled: bool = True,
    ) -> dict[str, Any]:
        from dataclasses import asdict

        from codeagent.knowledge import KnowledgeConfig, vault_status

        cfg = KnowledgeConfig.load()
        cfg.path = (path or "").strip() or cfg.path
        cfg.mode = mode if mode in ("local", "shared") else cfg.mode
        cfg.backend = backend if backend in ("obsidian", "llmwiki") else cfg.backend
        cfg.enabled = bool(enabled)
        cfg.save()
        self._agent = None
        return {
            "ok": True,
            "config": asdict(cfg),
            "status": vault_status(cfg.vault_path()),
        }

    def bootstrap_knowledge(self) -> dict[str, Any]:
        """One-click create Obsidian / LLM Wiki structure at configured path."""
        from dataclasses import asdict

        from codeagent.knowledge import KnowledgeConfig, bootstrap_vault, vault_status

        cfg = KnowledgeConfig.load()
        root = cfg.vault_path()
        try:
            result = bootstrap_vault(root)
        except OSError as exc:
            return {"ok": False, "error": str(exc)[:200]}
        cfg.bootstrapped = True
        cfg.enabled = True
        cfg.save()
        self._agent = None
        result["config"] = asdict(cfg)
        result["status"] = vault_status(root)
        log.info("knowledge vault bootstrapped: %s", root)
        return result

    def search_knowledge(self, query: str = "") -> list[dict[str, Any]]:
        from codeagent.knowledge import KnowledgeConfig, list_pages

        cfg = KnowledgeConfig.load()
        return [
            {
                "rel": p.rel,
                "title": p.title,
                "preview": p.preview,
                "mtime": p.mtime,
                "size": p.size,
            }
            for p in list_pages(cfg.vault_path(), query=query or "", limit=60)
        ]

    def read_knowledge_page(self, rel: str) -> dict[str, Any]:
        from codeagent.knowledge import KnowledgeConfig, read_page

        cfg = KnowledgeConfig.load()
        page = read_page(cfg.vault_path(), rel or "")
        return page or {"ok": False, "error": "页面不存在"}

    def ingest_knowledge(self, title: str, content: str) -> dict[str, Any]:
        from codeagent.knowledge import KnowledgeConfig, ingest_text, is_vault_ready

        cfg = KnowledgeConfig.load()
        root = cfg.vault_path()
        if not is_vault_ready(root):
            return {"ok": False, "error": "请先一键布置知识库"}
        title = (title or "").strip()
        content = (content or "").strip()
        if not title or not content:
            return {"ok": False, "error": "标题与内容必填"}
        try:
            return ingest_text(root, title, content)
        except OSError as exc:
            return {"ok": False, "error": str(exc)[:200]}

    def open_knowledge_folder(self) -> dict[str, Any]:
        import subprocess
        import sys

        from codeagent.knowledge import KnowledgeConfig

        root = KnowledgeConfig.load().vault_path()
        if not root.exists():
            return {"ok": False, "error": "路径不存在，请先一键布置"}
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", str(root)])
            elif sys.platform == "win32":
                subprocess.Popen(["explorer", str(root)])
            else:
                subprocess.Popen(["xdg-open", str(root)])
            return {"ok": True, "path": str(root)}
        except OSError as exc:
            return {"ok": False, "error": str(exc)[:200]}

    # ------------------------------------------------------------------
    # video ops (generate / edit / analyze / publish drafts)
    # ------------------------------------------------------------------

    def get_video_ops(self) -> dict[str, Any]:
        from dataclasses import asdict

        from codeagent.videoops import (
            BUNDLED_SKILLS,
            VideoOpsConfig,
            workspace_status,
        )

        cfg = VideoOpsConfig.load()
        from codeagent.videoops.gradio import probe_gradio_app, resolve_gradio_base

        base = resolve_gradio_base(cfg)
        gradio: dict[str, Any] = {"base": base, "online": False, "title": "", "endpoints": []}
        if base:
            info = asyncio.run(probe_gradio_app(base))
            if info:
                gradio = {
                    "base": base,
                    "online": True,
                    "title": info.get("title") or "",
                    "endpoints": info.get("endpoints") or [],
                }
        if not (cfg.comfy_base or "").strip():
            inferred = next(
                (e.base for e in self.assets.endpoints
                 if e.kind == "comfy" or str(e.base).rstrip("/").endswith(":8188")),
                "",
            )
            if inferred:
                from codeagent.videoops.comfy import normalize_comfy_base

                cfg.comfy_base = normalize_comfy_base(inferred)
        comfy: dict[str, Any] = {"base": cfg.comfy_base, "online": False, "models": []}
        if cfg.comfy_base:
            from codeagent.videoops.comfy import probe_comfy

            info = asyncio.run(probe_comfy(cfg.comfy_base))
            if info:
                comfy = {
                    "base": info["base"],
                    "online": True,
                    "models": [m.get("name") for m in (info.get("models") or []) if m.get("name")],
                }
        return {
            "config": asdict(cfg),
            "status": workspace_status(cfg.workspace()),
            "gradio": gradio,
            "comfy": comfy,
            "skills": [
                {"name": n, "description": d}
                for n, (d, _) in BUNDLED_SKILLS.items()
            ],
        }

    def save_video_ops_config(
        self,
        path: str = "",
        enabled: bool = True,
        gradio_base: str | None = None,
        comfy_base: str | None = None,
    ) -> dict[str, Any]:
        from dataclasses import asdict

        from codeagent.desktop.models import normalize_endpoint_base
        from codeagent.videoops import VideoOpsConfig, workspace_status
        from codeagent.videoops.gradio import probe_gradio_app

        cfg = VideoOpsConfig.load()
        cfg.path = (path or "").strip() or cfg.path
        cfg.enabled = bool(enabled)
        if gradio_base is not None:
            cfg.gradio_base = normalize_endpoint_base(gradio_base)
        if comfy_base is not None:
            from codeagent.videoops.comfy import normalize_comfy_base

            cfg.comfy_base = normalize_comfy_base(comfy_base)
        cfg.save()
        if cfg.gradio_base:
            self._ensure_gradio_endpoint(cfg.gradio_base)
        if cfg.comfy_base:
            self._ensure_comfy_endpoint(cfg.comfy_base)
        self._agent = None
        gradio: dict[str, Any] = {
            "base": cfg.gradio_base, "online": False, "title": "", "endpoints": [],
        }
        if cfg.gradio_base:
            info = asyncio.run(probe_gradio_app(cfg.gradio_base))
            if info:
                gradio = {
                    "base": cfg.gradio_base,
                    "online": True,
                    "title": info.get("title") or "",
                    "endpoints": info.get("endpoints") or [],
                }
        return {
            "ok": True,
            "config": asdict(cfg),
            "status": workspace_status(cfg.workspace()),
            "gradio": gradio,
        }

    def _ensure_gradio_endpoint(self, base: str) -> None:
        from codeagent.desktop.models import OllamaEndpoint, normalize_endpoint_base

        base = normalize_endpoint_base(base)
        if not base:
            return
        for ep in self.assets.endpoints:
            if ep.base.rstrip("/") == base:
                if ep.kind != "gradio":
                    ep.kind = "gradio"
                    self.assets.save()
                return
        self.assets.endpoints.append(OllamaEndpoint(
            base=base, label="WAN 文生视频", kind="gradio", role="backup",
        ))
        self.assets.save()

    def _remember_comfy_base(self, base: str) -> None:
        from codeagent.videoops import VideoOpsConfig
        from codeagent.videoops.comfy import normalize_comfy_base

        root = normalize_comfy_base(base)
        if not root:
            return
        cfg = VideoOpsConfig.load()
        if cfg.comfy_base == root:
            return
        cfg.comfy_base = root
        cfg.save()

    def _ensure_comfy_endpoint(self, base: str) -> None:
        from codeagent.desktop.models import OllamaEndpoint, normalize_endpoint_base

        base = normalize_endpoint_base(base)
        if not base:
            return
        for ep in self.assets.endpoints:
            if ep.base.rstrip("/") == base:
                if ep.kind != "comfy":
                    ep.kind = "comfy"
                    self.assets.save()
                return
        self.assets.endpoints.append(OllamaEndpoint(
            base=base, label="ComfyUI", kind="comfy", role="backup",
        ))
        self.assets.save()

    def bootstrap_video_ops(self) -> dict[str, Any]:
        from dataclasses import asdict

        from codeagent.videoops import (
            VideoOpsConfig,
            bootstrap_workspace,
            install_bundled_skills,
            workspace_status,
        )

        cfg = VideoOpsConfig.load()
        try:
            result = bootstrap_workspace(cfg.workspace())
            installed = install_bundled_skills()
        except OSError as exc:
            return {"ok": False, "error": str(exc)[:200]}
        cfg.bootstrapped = True
        cfg.skills_installed = True
        cfg.enabled = True
        cfg.save()
        self._agent = None
        result["config"] = asdict(cfg)
        result["status"] = workspace_status(cfg.workspace())
        result["skills_installed"] = installed
        log.info("video ops bootstrapped: %s", cfg.workspace())
        return result

    def save_video_ops_draft(
        self,
        title: str = "",
        description: str = "",
        tags: str = "",
        video_path: str = "",
        cover_path: str = "",
    ) -> dict[str, Any]:
        from codeagent.videoops import VideoOpsConfig, is_workspace_ready, save_publish_draft

        cfg = VideoOpsConfig.load()
        root = cfg.workspace()
        if not is_workspace_ready(root):
            return {"ok": False, "error": "请先一键布置视频运营工作区"}
        return save_publish_draft(root, {
            "title": title,
            "description": description,
            "tags": tags,
            "video_path": video_path,
            "cover_path": cover_path,
        })

    def get_studio(self) -> dict[str, Any]:
        from codeagent.videoops import VideoOpsConfig, toolchain_status, workspace_status
        from codeagent.videoops.comfy import probe_comfy
        from codeagent.videoops.studio import (
            STAGE_LABELS,
            STAGES,
            desk_dict,
            ensure_desk_workspace,
            load_desk,
        )

        root = ensure_desk_workspace()
        desk = load_desk(root)
        cfg = VideoOpsConfig.load()
        comfy: dict[str, Any] = {"base": cfg.comfy_base, "online": False, "models": []}
        if cfg.comfy_base:
            info = asyncio.run(probe_comfy(cfg.comfy_base, timeout=4.0))
            if info:
                comfy = {
                    "base": info["base"],
                    "online": True,
                    "models": [m.get("name") for m in (info.get("models") or []) if m.get("name")],
                }
        return {
            "ok": True,
            "desk": desk_dict(desk),
            "stages": [{"id": s, "label": STAGE_LABELS[s]} for s in STAGES],
            "comfy": comfy,
            "toolchain": toolchain_status(),
            "workspace": workspace_status(root),
            "busy": self._busy,
        }

    def _studio_desk(self) -> dict[str, Any]:
        from codeagent.videoops.studio import desk_dict, ensure_desk_workspace, load_desk

        return desk_dict(load_desk(ensure_desk_workspace()))

    def save_studio(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        from codeagent.videoops.studio import (
            apply_desk_patch, load_desk, save_desk, ensure_desk_workspace,
        )

        root = ensure_desk_workspace()
        desk = apply_desk_patch(load_desk(root), payload or {})
        save_desk(desk, root)
        return {"ok": True, "desk": self._studio_desk()}

    def studio_import_script(self, script: str) -> dict[str, Any]:
        from codeagent.videoops.studio import (
            load_desk, parse_script_shots, save_desk, ensure_desk_workspace,
        )

        incoming = parse_script_shots(script or "")
        if not incoming:
            return {"ok": False, "error": "没有解析到镜头。用「1. 画面」或「## 镜头名」分行。"}
        root = ensure_desk_workspace()
        desk = load_desk(root)
        desk.shots.extend(incoming)
        desk.stage = "board"
        save_desk(desk, root)
        return {"ok": True, "added": len(incoming), "desk": self._studio_desk()}

    def studio_add_shot(
        self,
        title: str = "",
        prompt: str = "",
        seconds: float = 4.0,
        engine: str = "auto",
    ) -> dict[str, Any]:
        from codeagent.videoops.studio import Shot, load_desk, save_desk, ensure_desk_workspace

        body = (prompt or title or "").strip()
        if not body:
            return {"ok": False, "error": "画面描述不能为空"}
        root = ensure_desk_workspace()
        desk = load_desk(root)
        desk.shots.append(Shot(
            title=(title or body[:24])[:80],
            prompt=body[:2000],
            seconds=seconds,
            engine=engine or "auto",
        ))
        desk.stage = "board"
        save_desk(desk, root)
        return {"ok": True, "desk": self._studio_desk()}

    def studio_remove_shot(self, shot_id: str) -> dict[str, Any]:
        from codeagent.videoops.studio import load_desk, save_desk, ensure_desk_workspace

        root = ensure_desk_workspace()
        desk = load_desk(root)
        before = len(desk.shots)
        desk.shots = [s for s in desk.shots if s.id != shot_id]
        if len(desk.shots) == before:
            return {"ok": False, "error": "镜头不存在"}
        save_desk(desk, root)
        return {"ok": True, "desk": self._studio_desk()}

    def studio_generate_shot(self, shot_id: str = "", all_pending: bool = False) -> dict[str, Any]:
        with self._lock:
            if self._busy:
                return {"ok": False, "error": "正在执行其他任务，请稍后再生成"}
            self._busy = True
            self._cancel.clear()
        threading.Thread(
            target=self._run_studio_generate,
            args=(shot_id, bool(all_pending)),
            daemon=True,
        ).start()
        return {"ok": True}

    def _run_studio_generate(self, shot_id: str, all_pending: bool) -> None:
        from codeagent.videoops.studio import generate_one_shot, load_desk, ensure_desk_workspace

        try:
            root = ensure_desk_workspace()
            desk = load_desk(root)
            if all_pending:
                ids = [s.id for s in desk.shots if s.status in ("draft", "error", "queued", "")]
                if not ids:
                    ids = [s.id for s in desk.shots if s.status != "done"]
            else:
                ids = [shot_id] if shot_id else (
                    [desk.shots[0].id] if desk.shots else []
                )
            if not ids:
                self._push("studio", action="error", text="没有可生成的镜头")
                return
            for sid in ids:
                if self._cancel.is_set():
                    self._push("studio", action="stopped", shot_id=sid)
                    return
                self._push("studio", action="running", shot_id=sid, text="正在生成镜头…")
                result = asyncio.run(generate_one_shot(load_desk(root), sid))
                if result.get("ok"):
                    shot = result.get("shot") or {}
                    self._push(
                        "studio", action="done", shot_id=sid,
                        clip=shot.get("clip") or "", text="镜头完成",
                    )
                else:
                    self._push(
                        "studio", action="error", shot_id=sid,
                        text=str(result.get("error") or "生成失败"),
                    )
                    if not all_pending:
                        return
        except Exception as exc:  # noqa: BLE001
            log.exception("studio generate failed")
            self._push("studio", action="error", text=str(exc)[:300])
        finally:
            with self._lock:
                self._busy = False
            self._push("studio", action="idle")

    def studio_assemble(self) -> dict[str, Any]:
        from codeagent.videoops.studio import assemble_desk, load_desk, ensure_desk_workspace

        desk = load_desk(ensure_desk_workspace())
        result = assemble_desk(desk)
        if result.get("ok"):
            result["desk"] = self._studio_desk()
        return result

    def studio_interrupt(self) -> dict[str, Any]:
        from codeagent.videoops import VideoOpsConfig
        from codeagent.videoops.comfy import interrupt_comfy

        self.stop()
        cfg = VideoOpsConfig.load()
        if cfg.comfy_base:
            return asyncio.run(interrupt_comfy(cfg.comfy_base))
        return {"ok": True}

    def open_video_ops_folder(self) -> dict[str, Any]:
        import subprocess
        import sys

        from codeagent.videoops import VideoOpsConfig

        root = VideoOpsConfig.load().workspace()
        if not root.exists():
            return {"ok": False, "error": "路径不存在，请先一键布置"}
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", str(root)])
            elif sys.platform == "win32":
                subprocess.Popen(["explorer", str(root)])
            else:
                subprocess.Popen(["xdg-open", str(root)])
            return {"ok": True, "path": str(root)}
        except OSError as exc:
            return {"ok": False, "error": str(exc)[:200]}

    # ------------------------------------------------------------------
    # skills / harnesses / logs
    # ------------------------------------------------------------------

    def get_skills(self) -> list[dict[str, str]]:
        library = self._load_skills()
        if library is None:
            return []
        return [
            {
                "name": s.name,
                "description": s.description,
                "source": s.metadata.get("source", ""),
                "pack": s.metadata.get("pack", ""),
            }
            for s in library
        ]

    def get_harnesses(self) -> list[dict[str, Any]]:
        from codeagent.harness import discover_harnesses

        return [
            {"name": h.name, "binary": h.executable, "available": h.available()}
            for h in discover_harnesses()
        ]

    def get_logs(self, lines: int = 120) -> list[str]:
        return tail_log(min(int(lines), 500))
