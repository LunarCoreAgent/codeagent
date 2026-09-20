"""Desktop UI bridge: config persistence, state, chat/lead push events,
memory & skills & logs surfaces."""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from pathlib import Path

import pytest

from codeagent.core.budget import BudgetExceededError
from codeagent.desktop.api import DesktopAPI, DesktopConfig, _format_conv_seed
from codeagent.desktop.ui import HTML


class FakeWindow:
    """Captures evaluate_js pushes like a real webview window."""

    def __init__(self):
        self.calls: list[dict] = []

    def evaluate_js(self, script: str):
        # Production push wraps: try{window._onEvent({...})}catch(e){}
        marker = "window._onEvent("
        start = script.find(marker)
        assert start >= 0, script[:120]
        start += len(marker)
        depth = 0
        end = None
        for i, ch in enumerate(script[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        assert end is not None
        self.calls.append(json.loads(script[start:end]))

    def kinds(self) -> list[str]:
        return [c["kind"] for c in self.calls]


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "codeagent.desktop.api.DESKTOP_CONFIG_PATH", tmp_path / "desktop.json"
    )
    monkeypatch.setattr(
        "codeagent.desktop.api.MEMORY_PATH", tmp_path / "memory.json"
    )
    monkeypatch.setattr(
        "codeagent.desktop.api.DEFAULT_SKILLS_DIR", tmp_path / "skills"
    )
    monkeypatch.setattr(
        "codeagent.settings.DEFAULT_SETTINGS_PATH", tmp_path / "settings.json"
    )
    monkeypatch.setattr(
        "codeagent.desktop.models.MODELS_PATH", tmp_path / "models.json"
    )
    monkeypatch.setattr(
        "codeagent.desktop.models.SECRETS_PATH", tmp_path / "secrets.json"
    )
    monkeypatch.setattr(
        "codeagent.desktop.router.ROUTER_PATH", tmp_path / "router.json"
    )
    monkeypatch.setattr(
        "codeagent.desktop.permissions.PERMS_PATH", tmp_path / "permissions.json"
    )
    monkeypatch.setattr(
        "codeagent.desktop.permissions.AUDIT_PATH", tmp_path / "audit.jsonl"
    )
    monkeypatch.setattr(
        "codeagent.desktop.activity.ACTIVITY_PATH", tmp_path / "activity.jsonl"
    )
    monkeypatch.setattr(
        "codeagent.desktop.activity.LEARNING_PATH", tmp_path / "learning.json"
    )
    monkeypatch.setattr(
        "codeagent.desktop.automation.WORKFLOWS_PATH", tmp_path / "workflows.json"
    )
    monkeypatch.setattr(
        "codeagent.desktop.cron.CRON_PATH", tmp_path / "cron.json"
    )
    monkeypatch.setattr(
        "codeagent.desktop.evolution.EVOLUTION_PATH", tmp_path / "evolution.json"
    )
    monkeypatch.setattr(
        "codeagent.desktop.projects.PROJECTS_INDEX", tmp_path / "projects.json"
    )
    monkeypatch.setattr(
        "codeagent.desktop.projects.DEFAULT_BASE", tmp_path / "proj-base"
    )
    monkeypatch.setattr(
        "codeagent.videoops.CONFIG_PATH", tmp_path / "videoops.json"
    )
    a = DesktopAPI(root=tmp_path)
    a._window = FakeWindow()
    # 对话类集成测试需要真实模型：默认本地 Ollama，可用环境变量
    # CODEAGENT_OLLAMA_BASE 指向局域网/远端 Ollama 端点
    base = os.environ.get("CODEAGENT_OLLAMA_BASE", "")
    if base:
        a.config.base_url = base
    return a


def wait_for(window: FakeWindow, kind: str, timeout: float | None = None) -> dict:
    # 集成测试等待真实模型回复时，可用 CODEAGENT_TEST_TIMEOUT 调大超时
    timeout = timeout if timeout is not None else float(os.environ.get("CODEAGENT_TEST_TIMEOUT", "8.0"))
    deadline = time.time() + timeout
    while time.time() < deadline:
        hit = [c for c in window.calls if c["kind"] == kind]
        if hit:
            return hit[-1]
        time.sleep(0.05)
    raise AssertionError(f"no push event of kind {kind!r}; got {window.kinds()}")


# ---------------------------------------------------------------------------
# config & state
# ---------------------------------------------------------------------------


def test_desktop_config_roundtrip(tmp_path):
    path = tmp_path / "desktop.json"
    DesktopConfig(
        provider="openrouter", model="m1", api_key="k",
        voice_enabled=True, voice_name="xiaochen",
        workers_json='[{"name":"a","provider":"ollama"}]',
    ).save(path)
    loaded = DesktopConfig.load(path)
    assert loaded.provider == "openrouter"
    assert loaded.voice_enabled is True
    assert loaded.voice_name == "xiaochen"
    assert loaded.voice_cute_tone is True
    assert loaded.memory_enabled is True
    assert "ollama" in loaded.workers_json


def test_desktop_config_ignores_unknown_fields(tmp_path):
    path = tmp_path / "desktop.json"
    path.write_text(json.dumps({"provider": "ollama", "hack": True}), encoding="utf-8")
    cfg = DesktopConfig.load(path)
    assert cfg.provider == "ollama"
    assert not hasattr(cfg, "hack")


def test_get_state(api):
    state = api.get_state()
    assert state["version"]
    assert "ollama" in state["providers"]
    assert "openrouter" in state["providers"]
    assert state["config"]["provider"] == "ollama"
    assert "settings" in state
    assert "voices" in state
    assert state["privacy_accepted"] is False
    assert state["privacy_version"]


def test_privacy_policy_accept_flow(api, tmp_path):
    from codeagent.desktop.privacy import PRIVACY_VERSION

    doc = api.get_privacy_policy()
    assert doc["version"] == PRIVACY_VERSION
    assert doc["sections"]
    assert doc["accepted"] is False
    r = api.accept_privacy()
    assert r["ok"] and r["privacy_accepted"]
    assert api.get_privacy_policy()["accepted"] is True
    assert api.get_state()["privacy_accepted"] is True
    saved = DesktopConfig.load(tmp_path / "desktop.json")
    assert saved.privacy_accepted_version == PRIVACY_VERSION
    assert saved.privacy_accepted_at


def test_privacy_markdown_matches_module():
    from pathlib import Path

    from codeagent.desktop.privacy import privacy_markdown

    root = Path(__file__).resolve().parents[1] / "PRIVACY.md"
    assert root.read_text(encoding="utf-8") == privacy_markdown()


def test_save_config_persists_and_resets_agent(api, tmp_path):
    api.save_config({"provider": "openai", "model": "gpt-4o-mini", "api_key": "k"})
    assert api.config.provider == "openai"
    assert api._agent is None
    assert api._agent2 is None
    reloaded = DesktopConfig.load(tmp_path / "desktop.json")
    assert reloaded.model == "gpt-4o-mini"


def test_companion_settings_roundtrip(api, tmp_path):
    r = api.save_config({
        "companion_enabled": True,
        "companion_preset": "2",
        "companion_name": "晚柠",
        "companion_nature": "温柔治愈，擅长倾听",
    })
    assert r["companion_enabled"] is True
    assert r["companion_name"] == "晚柠"
    loaded = DesktopConfig.load(tmp_path / "desktop.json")
    assert loaded.companion_enabled is True
    assert loaded.companion_preset == "2"
    assert "温柔" in loaded.companion_nature
    block = api._companion_prompt_rule()
    assert "晚柠" in block and "陪伴模式已开启" in block
    patched = api._settings_with_patches()
    assert "陪伴模式已开启" in patched.instructions


def test_save_settings_updates_personalization(api):
    api.save_settings({"nickname": "石头", "language": "中文"})
    assert api.settings.nickname == "石头"


def test_get_changelog(api):
    assert "0.21.0" in api.get_changelog()


# ---------------------------------------------------------------------------
# model assets (LCA-style)
# ---------------------------------------------------------------------------


def test_assets_default_endpoint(api):
    assets = api.get_model_assets()
    assert assets["endpoints"]  # default localhost endpoint exists
    assert assets["endpoints"][0]["base"] == "http://localhost:11434"
    assert assets["active"] == "route:free"
    assert assets["free_route"]["label"] == "自由路由"
    assert assets["active_label"] == "自由路由"


def test_add_and_remove_endpoint(api):
    r = api.add_endpoint("http://192.168.1.10:11434/")
    assert r["ok"]
    eps = api.get_model_assets()["endpoints"]
    ep = next(e for e in eps if e["base"] == "http://192.168.1.10:11434")
    assert api.remove_endpoint(ep["id"])
    assert not any(e["id"] == ep["id"]
                   for e in api.get_model_assets()["endpoints"])


def test_add_endpoint_rejects_duplicates(api):
    api.add_endpoint("http://x:11434")
    assert not api.add_endpoint("http://x:11434")["ok"]


def test_add_endpoint_normalizes_fullwidth_colon(api):
    r = api.add_endpoint("192.168.3.6：9000", label="DS")
    assert r["ok"]
    bases = [e["base"] for e in api.get_model_assets()["endpoints"]]
    assert "http://192.168.3.6:9000" in bases


def test_local_openai_endpoint_builds_openai_provider(api):
    from codeagent.desktop.models import OllamaEndpoint

    ep = OllamaEndpoint(base="http://192.168.3.6:9000", kind="openai", label="DS")
    api.assets.endpoints.append(ep)
    api.assets.save()
    api.set_active_model(f"local:deepseek-v4-flash@{ep.id}")
    provider = api._build_provider()
    assert provider.name == "openai"
    assert provider.model == "deepseek-v4-flash"
    assert "192.168.3.6:9000/v1" in str(provider.client.base_url)


def test_normalize_endpoint_base():
    from codeagent.desktop.models import normalize_endpoint_base

    assert normalize_endpoint_base("192.168.3.6：9000") == "http://192.168.3.6:9000"
    assert normalize_endpoint_base("http://host:11434/") == "http://host:11434"


def test_api_model_key_stored_as_pointer(api, tmp_path):
    r = api.add_api_model("https://api.deepseek.com/v1", "deepseek-chat",
                          label="DS", api_key="sk-real-key-1234")
    assert r["ok"]
    # store holds no plaintext key
    store_text = (tmp_path / "models.json").read_text(encoding="utf-8")
    assert "sk-real-key-1234" not in store_text
    # secret file holds it, owner-only
    secrets = (tmp_path / "secrets.json").read_text(encoding="utf-8")
    assert "sk-real-key-1234" in secrets
    import stat
    mode = (tmp_path / "secrets.json").stat().st_mode
    assert stat.S_IMODE(mode) == 0o600
    # UI sees only the mask
    listed = api.get_model_assets()["api_models"][0]
    assert listed["key_masked"].endswith("1234")
    assert "sk-real" not in listed["key_masked"]


def test_remove_api_model_deletes_secret(api, tmp_path):
    r = api.add_api_model("https://x/v1", "m", api_key="k123")
    assert api.remove_api_model(r["id"])
    assert "k123" not in (tmp_path / "secrets.json").read_text(encoding="utf-8")


def test_set_active_local_model(api):
    ep = api.assets.endpoints[0]
    r = api.set_active_model(f"local:qwen3:8b@{ep.id}")
    assert r["ok"] and "qwen3:8b" in r["active_label"]
    assert api._agent is None
    # persists
    from codeagent.desktop.models import ModelAssets
    assert ModelAssets.load().active == f"local:qwen3:8b@{ep.id}"


def test_active_api_model_builds_openai_provider(api):
    r = api.add_api_model("https://api.deepseek.com/v1", "deepseek-chat",
                          api_key="sk-x")
    api.set_active_model(f"api:{r['id']}")
    provider = api._build_provider()
    assert provider.name == "openai"
    assert provider.model == "deepseek-chat"
    assert provider.client.api_key == "sk-x"


def test_legacy_config_when_no_active_asset(api):
    provider = api._build_provider()
    assert provider.name == "ollama"  # falls back to desktop.json config


def test_diagnose_messages(api):
    assert "连不上" in api._diagnose(Exception("Connection refused"))
    assert "超时" in api._diagnose(Exception("request timed out"))
    assert "Key" in api._diagnose(Exception("401 Unauthorized"))
    assert "404" in api._diagnose(Exception("404 not found"))
    assert "兜底规则" in api._diagnose(ValueError("Empty provider spec"))
    assert "兜底规则" in api._diagnose(ValueError("自由路由未命中可用模型"))
    algo = api._diagnose(Exception(
        "Error code: 500 - {'error': {'message': '<500> InternalError.Algo: "
        "An error occurred in model serving', 'type': 'internal_server_error', "
        "'code': 'internal_server_error'}, 'id': 'chatcmpl-xxx'}"
    ))
    assert "500" in algo
    assert "服务" in algo
    assert "再发" in algo
    assert "chatcmpl" not in algo
    budget = api._diagnose(BudgetExceededError(
        "Token budget exceeded: 519841 tokens used (budget: 500000)"
    ))
    assert "token" in budget.lower()
    assert "新对话" in budget
    assert "519841" not in budget
    from codeagent.core.agent import MaxIterationsError

    iters = api._diagnose(MaxIterationsError("Agent did not finish within 50 iterations"))
    assert "往返" in iters and "新对话" in iters
    assert "50 iterations" not in iters


def test_desktop_agent_uses_soft_iterations(api, monkeypatch):
    from codeagent.desktop import api as api_mod

    captured = {}

    class FakeAgent:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(api_mod, "Agent", FakeAgent)
    monkeypatch.setattr(api, "_build_provider", lambda: object())
    monkeypatch.setattr(api, "_agent_tools", lambda: None)
    monkeypatch.setattr(api, "_load_skills", lambda: None)
    monkeypatch.setattr(api, "_settings_with_patches", lambda: None)
    monkeypatch.setattr(api, "_workspace_skill_hints", lambda: "")
    api.config.max_iterations = 120
    api._build_agent()
    assert captured.get("max_iterations") == 120
    assert captured.get("soft_iterations") is True


def test_max_iterations_config_clamped(api, tmp_path):
    from codeagent.desktop.api import DesktopConfig, clamp_max_iterations

    assert clamp_max_iterations(5) == 10
    assert clamp_max_iterations(999) == 300
    assert clamp_max_iterations("abc") == 80
    api.save_config({"max_iterations": 300})
    assert api.config.max_iterations == 300
    api.save_config({"max_iterations": 999})
    assert api.config.max_iterations == 300
    api.save_config({"max_iterations": 1})
    assert api.config.max_iterations == 10
    loaded = DesktopConfig.load(tmp_path / "desktop.json")
    # last save was 10
    assert loaded.max_iterations == 10


def test_ui_max_iterations_settings():
    assert 'id="sectAgentLimits"' in HTML
    assert 'id="cfg_max_iterations"' in HTML
    assert "agentLimitsFromForm" in HTML
    assert "syncMaxIterationsSlider" in HTML
    assert "max=\"300\"" in HTML
    assert "Agent 执行上限" in HTML
def test_format_conv_seed_truncates_long_history():
    msgs = [
        {"role": "user", "text": "hello"},
        {"role": "assistant", "text": "x" * 5000},
        {"role": "user", "text": "continue"},
    ]
    seed = _format_conv_seed(msgs)
    assert "hello" in seed
    assert "continue" in seed
    assert "已截断" in seed
    assert len(seed) < 5000


def test_get_overview(api):
    overview = api.get_overview()
    assert overview["version"]
    assert overview["provider"] == "ollama"
    assert isinstance(overview["skills"], int)
    assert isinstance(overview["memories"], int)
    assert isinstance(overview["harnesses"], int)
    assert isinstance(overview["recent_runs"], list)


# ---------------------------------------------------------------------------
# chat flow
# ---------------------------------------------------------------------------


def test_send_empty_rejected(api):
    assert api.send("   ") is False


def test_send_chat_pushes_events(api, monkeypatch):
    from codeagent.core.types import LLMResponse

    class FakeProvider:
        name = "fake"
        model = "fake-model"

        async def complete(self, messages, tools=None, system=None, **kw):
            return LLMResponse(content="你好，石头")

    monkeypatch.setattr(
        "codeagent.desktop.api.parse_provider_spec",
        lambda *a, **k: FakeProvider(),
    )
    assert api.send("你好") is True
    done = wait_for(api._window, "done")
    assert done["text"] == "你好，石头"
    assert "text" in api._window.kinds()


def test_send_error_pushes_error(api, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("连接失败")

    monkeypatch.setattr("codeagent.desktop.api.parse_provider_spec", boom)
    api.send("hi")
    err = wait_for(api._window, "error")
    assert "连接失败" in err["text"]


def test_reset_clears_agent(api):
    class StubAgent:
        reset_called = False

        def reset(self):
            self.reset_called = True

    stub = StubAgent()
    api._agent = stub
    assert api.reset() is True
    assert stub.reset_called
    assert api._agent is None


def test_stop_when_idle_is_noop(api):
    assert api.stop() is False
    assert api._busy is False


def test_stop_cancels_in_flight_chat(api, monkeypatch):
    from codeagent.core.types import LLMResponse

    class SlowProvider:
        name = "slow"
        model = "slow"

        async def complete(self, messages, tools=None, system=None, **kw):
            await asyncio.sleep(30)
            return LLMResponse(content="should not finish")

    monkeypatch.setattr(
        "codeagent.desktop.api.parse_provider_spec",
        lambda *a, **k: SlowProvider(),
    )
    assert api.send("请写很长的回复") is True
    deadline = time.time() + 2
    while time.time() < deadline and api._loop is None:
        time.sleep(0.02)
    assert api.stop() is True
    ev = wait_for(api._window, "stopped", timeout=4.0)
    assert ev["text"] == "已停止"
    assert api._busy is False
    assert "done" not in api._window.kinds()


# ---------------------------------------------------------------------------
# leader command center
# ---------------------------------------------------------------------------


def test_leader_workers_default(api):
    roster = api._leader_workers()
    assert len(roster) == 1
    assert roster[0].provider == "ollama"


def test_leader_workers_from_json(api):
    api.config.workers_json = json.dumps([
        {"name": "claude", "provider": "anthropic", "description": "代码"},
        {"name": "qwen", "provider": "ollama", "model": "qwen2.5-coder:7b"},
    ])
    roster = api._leader_workers()
    assert [w.name for w in roster] == ["claude", "qwen"]
    assert roster[1].model == "qwen2.5-coder:7b"


def test_leader_workers_invalid_json_falls_back(api):
    api.config.workers_json = "{broken"
    assert len(api._leader_workers()) == 1


def test_lead_pushes_task_and_done(api, monkeypatch):
    from codeagent.core.types import LLMResponse
    from codeagent.llm.base import LLMProvider

    class FakePlanner(LLMProvider):
        name = "fake"

        async def complete(self, messages, tools=None, system=None, **kw):
            # planner call → one assignment; worker call → answer
            if "任务拆解" in (system or ""):
                return LLMResponse(content=json.dumps({
                    "assignments": [{"worker": "worker", "task": "查一下"}]
                }))
            return LLMResponse(content="查完了")

    monkeypatch.setattr(
        "codeagent.desktop.api.parse_provider_spec",
        lambda *a, **k: FakePlanner(model="fake"),
    )
    monkeypatch.setattr(
        "codeagent.leader.leader.build_worker_agent",
        lambda config, root, **kw: __import__("codeagent").Agent(
            provider=FakePlanner(model="w"), tools=None
        ),
    )
    assert api.lead("检查项目") is True
    done = wait_for(api._window, "lead_done")
    assert "查完了" in done["text"]
    tasks = [c for c in api._window.calls if c["kind"] == "task"]
    assert any(t["status"] == "running" for t in tasks)
    assert any(t["status"] == "done" for t in tasks)


def test_get_runs_empty(api):
    assert api.get_runs() == []


# ---------------------------------------------------------------------------
# memory / skills / logs
# ---------------------------------------------------------------------------


def test_memory_add_list_search_delete(api):
    assert api.add_memory("用户喜欢 pytest") is True
    items = api.get_memories()
    assert any("pytest" in m["content"] for m in items)
    assert items[0]["source"] == "manual"
    hits = api.get_memories("pytest")
    assert hits
    assert api.update_memory(items[0]["id"], "用户喜欢 pytest 和 tmp_path") is True
    updated = api.get_memories()
    assert any("tmp_path" in m["content"] for m in updated)
    assert api.delete_memory(items[0]["id"]) is True
    assert api.get_memories() == []


def test_project_memory_is_isolated(api, tmp_path):
    assert api.add_memory("全局事实") is True
    first = api.create_project("甲", str(tmp_path / "memproj"))
    assert first["ok"]
    assert api.add_memory("甲的事实") is True
    names_a = [m["content"] for m in api.get_memories()]
    assert any("甲的事实" in c for c in names_a)
    assert all("全局事实" not in c for c in names_a)
    assert any("开始记录项目「甲」" in c for c in names_a)
    second = api.create_project("乙", str(tmp_path / "memproj"))
    assert second["ok"]
    names_b = [m["content"] for m in api.get_memories()]
    assert all("甲的事实" not in c for c in names_b)
    assert any("开始记录项目「乙」" in c for c in names_b)
    api.switch_project(first["project"]["id"])
    names_again = [m["content"] for m in api.get_memories()]
    assert any("甲的事实" in c for c in names_again)


def test_send_auto_records_turn(api, monkeypatch, tmp_path):
    from codeagent.core.types import LLMResponse

    class FakeProvider:
        name = "fake"
        model = "fake-model"

        async def complete(self, messages, tools=None, system=None, **kw):
            return LLMResponse(content="记下了")

    monkeypatch.setattr(
        "codeagent.desktop.api.parse_provider_spec",
        lambda *a, **k: FakeProvider(),
    )
    api.create_project("记事", str(tmp_path / "memproj"))
    assert api.send("帮我改登录页") is True
    wait_for(api._window, "done")
    items = api.get_memories()
    assert any(m["kind"] == "turn" and "帮我改登录页" in m["content"] for m in items)
    assert any(m["kind"] == "progress" and "帮我改登录页" in m["content"] for m in items)


def test_memory_backs_up_to_knowledge(api, tmp_path, monkeypatch):
    monkeypatch.setattr("codeagent.knowledge.CONFIG_PATH", tmp_path / "knowledge.json")
    vault = tmp_path / "vault"
    assert api.save_knowledge_config(str(vault), "local", "obsidian", True)["ok"]
    assert api.bootstrap_knowledge()["ok"]
    api.create_project("备份项", str(tmp_path / "memproj"))
    assert api.add_memory("备份这条事实") is True
    files = list((vault / "raw" / "conversations").glob("*.md"))
    assert files
    blob = "\n".join(p.read_text(encoding="utf-8") for p in files)
    assert "备份这条事实" in blob


def test_desktop_agent_wires_memory(api, monkeypatch):
    from codeagent.desktop import api as api_mod

    captured: dict = {}

    class FakeAgent:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(api_mod, "Agent", FakeAgent)
    monkeypatch.setattr(api, "_build_provider", lambda: object())
    monkeypatch.setattr(api, "_load_skills", lambda: None)
    monkeypatch.setattr(api, "_settings_with_patches", lambda: None)
    monkeypatch.setattr(api, "_workspace_skill_hints", lambda: "")
    api.add_memory("用户喜欢 pytest")
    api._build_agent()
    assert captured.get("memory") is not None
    tools = captured.get("tools")
    assert tools is not None
    assert tools.get("memory_save") is not None
    api.save_config({"memory_enabled": False})
    api._build_agent()
    assert captured.get("memory") is None


def test_get_skills_includes_bundled(api):
    names = {s["name"] for s in api.get_skills()}
    assert "video-ops-pipeline" in names
    assert "short-drama-script" in names
    assert "fusion-router" in names
    assert "cpython" in names
    assert "browser-skill" in names
    assert "ego-browser" in names
    assert "voice-surface" in names
    assert "mobile-app-ui" in names
    assert "wechat-miniprogram" in names
    assert "weapp-agent-mcp" in names
    assert "m3e-canvas" in names
    assert "stop-slop-zh" in names
    stop = next(s for s in api.get_skills() if s["name"] == "stop-slop-zh")
    assert "github.com/VincentOld/stop-slop-zh" in stop["source"]


def test_get_skills_lists_pack(api, tmp_path):
    skills_dir = tmp_path / "skills"
    pack = skills_dir / "demo"
    pack.mkdir(parents=True)
    (pack / "SKILL.md").write_text(
        "---\nname: demo\ndescription: 演示技能\n---\n\n内容\n", encoding="utf-8"
    )
    skills = api.get_skills()
    names = {s["name"] for s in skills}
    assert "demo" in names
    demo = next(s for s in skills if s["name"] == "demo")
    assert demo["description"] == "演示技能"


def test_get_harnesses_shape(api):
    for h in api.get_harnesses():
        assert {"name", "binary", "available"} <= set(h)


def test_get_logs_returns_list(api):
    assert isinstance(api.get_logs(10), list)


# ---------------------------------------------------------------------------
# UI shell
# ---------------------------------------------------------------------------


def test_ui_has_all_pages_and_bridge():
    for page in ("dashboard", "chat", "studio", "lead", "memory", "skills", "logs",
                 "settings", "models", "router", "permissions", "versions",
                 "automation", "cron", "learning", "evolution", "project",
                 "knowledge", "videoops", "privacy"):
        assert f'id="page-{page}"' in HTML
    assert "pywebview.api.send" in HTML
    assert "pywebview.api.stop" in HTML
    assert "pywebview.api.lead" in HTML
    assert "pywebview.api.get_overview" in HTML
    assert "pywebview.api.get_memories" in HTML
    assert "pywebview.api.get_skills" in HTML
    assert "融合技能" in HTML
    assert "skillPackOf" in HTML
    assert "use_skill" in HTML
    assert "自动识别" in HTML
    assert "pywebview.api.get_logs" in HTML
    assert "pywebview.api.get_models_page" in HTML
    assert "pywebview.api.save_mixture" in HTML
    assert "语音面 · 嗲嗲声" in HTML
    assert "cfg_cute" in HTML
    assert "开启嗲嗲声" in HTML
    assert "试听嗲嗲声" in HTML
    assert "syncCuteSliders" in HTML
    assert "previewCuteVoice" in HTML
    assert "voiceConfigFromForm" in HTML
    assert "陪伴型 AI" in HTML
    assert 'id="sectCompanion"' in HTML
    assert 'id="cfg_memory"' in HTML
    assert "每个项目单独一本" in HTML
    assert "pywebview.api.update_memory" in HTML
    assert 'id="cfg_companion"' in HTML
    assert "companionConfigFromForm" in HTML
    assert "COMPANION_PRESETS" in HTML
    assert "applyCompanionPreset" in HTML
    assert "开启陪伴模式" in HTML
    assert "max-width: 1040px" in HTML
    assert ".chat-col" in HTML
    assert 'id="micBtn"' in HTML
    assert "toggleVoice" in HTML
    assert "micPermDialog" in HTML
    assert "open_mic_settings" in HTML
    assert "ensure_mic_permission" in HTML
    assert "allowMicAndStart" in HTML
    assert "request_mic_access" in HTML
    assert "start_native_listen" in HTML
    assert "stop_native_listen" in HTML
    assert "系统听写" in HTML
    assert "state==='heard'" in HTML
    assert "隐私与安全性 → 麦克风" in HTML
    assert "打开「麦克风」系统页" in HTML
    assert "LunarCore Agent 是另一个软件" in HTML
    assert "register_mic_with_tcc_async" in Path(
        __file__).resolve().parents[1].joinpath("src/codeagent/desktop/app.py").read_text(encoding="utf-8")
    assert "webkitSpeechRecognition" in HTML
    assert "pywebview.api.set_voice_session" in HTML
    assert "pywebview.api.route_sandbox" in HTML
    assert "pywebview.api.set_permission_level" in HTML
    assert "pywebview.api.resolve_confirm" in HTML
    assert "pywebview.api.get_versions" in HTML
    assert "pywebview.api.send_feedback" in HTML
    assert 'id="sectFeedback"' in HTML
    assert "openFeedbackMail" in HTML
    assert "pywebview.api.open_feedback_mail" in HTML
    assert "alan_dan@live.com" in HTML
    assert ">问题反馈<" in HTML
    assert "openOfficialSite" in HTML
    assert "pywebview.api.open_official_site" in HTML
    assert "http://codecoreagent.com" in HTML
    assert "http://codecoreagent.com/privacy.html" in HTML
    assert "openPrivacyPage" in HTML
    assert ">官网<" in HTML
    assert "pywebview.api.get_workflows" in HTML
    assert "pywebview.api.add_cron_job" in HTML
    assert "pywebview.api.learn_now" in HTML
    assert "pywebview.api.run_evolution_now" in HTML
    assert "pywebview.api.set_patch_status" in HTML
    assert "pywebview.api.approve_skill" in HTML
    assert "pywebview.api.get_nav_status" in HTML
    assert "pywebview.api.browser_status" in HTML
    assert "pywebview.api.browser_pump" in HTML
    assert 'id="page-browser"' in HTML
    assert 'data-page="browser"' in HTML
    assert "function bootUi" in HTML
    assert "pywebviewready" in HTML
    assert "pywebview.api.get_privacy_policy" in HTML
    assert "pywebview.api.accept_privacy" in HTML
    assert 'id="page-privacy"' in HTML
    assert 'id="privacyDialog"' in HTML
    assert "ensurePrivacyAccepted" in HTML
    assert "window._onEvent" in HTML
    assert "CodeCoreAgent" in HTML
    assert '<div class="name">codeagent</div>' not in HTML
    assert "CodeCoreAgent 就绪" in HTML
    assert 'alt="CodeCoreAgent"' in HTML
    assert "__BRAND_LOGO_LIGHT__" in HTML
    assert "__BRAND_LOGO_DARK__" in HTML
    # 设置页/侧栏展开后内容超出窗口须能滚动，不能被 body overflow 裁死
    assert "#main { flex: 1; display: flex; flex-direction: column; min-width: 0;" in HTML
    assert "min-height: 0; overflow: hidden;" in HTML
    assert ".page-body { flex: 1; overflow-y: auto;" in HTML
    assert "min-height: 0; -webkit-overflow-scrolling: touch;" in HTML
    assert "min-height: 0; overflow-y: auto;" in HTML  # #sidebar


# ---------------------------------------------------------------------------
# mixtures (LCA 聚合池)
# ---------------------------------------------------------------------------


def _two_members(api):
    ep = api.assets.endpoints[0]
    r = api.add_api_model("https://api.deepseek.com/v1", "deepseek-chat")
    return [f"local:qwen3:8b@{ep.id}", f"api:{r['id']}"]


def test_mixture_create_requires_two_members(api):
    members = _two_members(api)
    r = api.save_mixture("测试池", "weighted", members[:1])
    assert not r["ok"] and "至少" in r["error"]
    r = api.save_mixture("", "weighted", members)
    assert not r["ok"]
    r = api.save_mixture("测试池", "weighted", members)
    assert r["ok"]
    mixes = api.get_model_assets()["mixtures"]
    assert len(mixes) == 1
    assert mixes[0]["name"] == "测试池"
    assert mixes[0]["strategy"] == "weighted"
    assert len(mixes[0]["members"]) == 2
    assert mixes[0]["fallback"]  # 默认第一个成员


def test_mixture_edit_reset_fallback_and_delete(api):
    members = _two_members(api)
    api.save_mixture("池子", "cascade", members)
    mix = api.assets.mixtures[0]
    # 编辑：换掉成员，兜底被移出时重置
    r = api.save_mixture("池子v2", "weighted", [members[1], members[0]], mix.id)
    assert r["ok"]
    assert api.assets.mixtures[0].name == "池子v2"
    assert api.delete_mixture(mix.id)
    assert api.assets.mixtures == []


def test_mixture_active_builds_aggregate(api):
    members = _two_members(api)
    api.save_mixture("混合", "cascade", members)
    mix = api.assets.mixtures[0]
    api.set_active_model(f"mix:{mix.id}")
    provider = api._build_provider()
    assert provider.name == "aggregate"
    assert len(provider.providers) == 2
    assert "混合" in api._active_label()


def test_mixture_toggle_persists(api):
    members = _two_members(api)
    api.save_mixture("开关池", "weighted", members)
    mix = api.assets.mixtures[0]
    assert api.toggle_mixture(mix.id, False)
    from codeagent.desktop.models import ModelAssets
    assert ModelAssets.load().mixtures[0].enabled is False


# ---------------------------------------------------------------------------
# router (LCA 路由引擎)
# ---------------------------------------------------------------------------


def test_router_rule_crud_and_move(api):
    members = _two_members(api)
    api.save_mixture("池", "weighted", members)
    target = f"mix:{api.assets.mixtures[0].id}"
    assert api.add_route_rule("代码调试", "报错,bug", target)["ok"]
    assert api.add_route_rule("兜底", "", target)["ok"]
    rules = api.get_router()["rules"]
    assert len(rules) == 2
    assert rules[0]["target_label"].startswith("聚合池")
    # move: 兜底 initially same priority; moving first down swaps order
    first = rules[0]["id"]
    assert api.move_route_rule(first, 1)
    assert api.get_router()["rules"][1]["id"] == first
    assert api.toggle_route_rule(first, False)
    assert api.delete_route_rule(first)
    assert len(api.get_router()["rules"]) == 1


def test_router_sandbox_keyword_hit(api):
    members = _two_members(api)
    api.save_mixture("调试池", "rule", members)
    target = f"mix:{api.assets.mixtures[0].id}"
    api.add_route_rule("代码调试", "报错,bug", target)
    r = api.route_sandbox("帮我看看这个报错")
    assert r["ok"]
    assert r["taskType"] == "代码调试"
    assert r["strategy"] == "规则直通"
    assert "调试池" in r["chosen"]


def test_router_sandbox_ideographic_keywords(api):
    """中文顿号/逗号分隔的关键词应能单独命中。"""
    from codeagent.desktop.router import split_keywords

    assert split_keywords("代码、分析、验证") == ["代码", "分析", "验证"]
    assert split_keywords("报错，bug;fix") == ["报错", "bug", "fix"]
    members = _two_members(api)
    api.save_mixture("分析池", "rule", members)
    target = f"mix:{api.assets.mixtures[0].id}"
    api.add_route_rule("代码分析", "代码、分析、验证", target)
    r = api.route_sandbox("请帮我分析这段日志")
    assert r["ok"]
    assert r["strategy"] == "规则直通"
    assert r["target"] == target
    assert "分析池" in r["chosen"]


def test_router_sandbox_fallback_rule(api):
    members = _two_members(api)
    target = f"api:{api.assets.api_models[0].id}"
    api.add_route_rule("兜底", "", target)
    r = api.route_sandbox("随便聊聊")
    assert r["strategy"] == "兜底分发"
    assert r["cost"] == 0.005


def test_router_sandbox_default_direct(api):
    r = api.route_sandbox("你好")
    assert r["strategy"] == "默认直连"
    assert r["chosen"] == "（当前激活模型）"


def test_router_weights_clamped(api):
    w = api.save_route_weights(150, -5, 60)
    assert w == {"cost": 100, "quality": 0, "local_first": 60}
    from codeagent.desktop.router import RouterStore
    assert RouterStore.load().weights.cost == 100


def test_chat_routes_through_rule(api, monkeypatch):
    """命中规则时，对话真实走规则目标而非激活模型。"""
    from codeagent.core.types import LLMResponse

    seen = {}

    class FakeProvider:
        def __init__(self, model):
            self.model = model
            self.name = "fake"

        async def complete(self, messages, tools=None, system=None, **kw):
            seen["model"] = self.model
            return LLMResponse(content="ok")

    monkeypatch.setattr(
        "codeagent.desktop.api.parse_provider_spec",
        lambda *a, **k: FakeProvider("legacy"),
    )
    monkeypatch.setattr(
        "codeagent.desktop.models.OllamaProvider",
        lambda model, base_url: FakeProvider(model),
        raising=False,
    )
    monkeypatch.setattr(
        "codeagent.llm.ollama.OllamaProvider",
        lambda model, base_url: FakeProvider(model),
    )
    ep = api.assets.endpoints[0]
    api.add_route_rule("代码调试", "报错", f"local:routed-model@{ep.id}")
    assert api.send("这里有报错") is True
    wait_for(api._window, "done")
    assert seen["model"] == "routed-model"
    # 状态栏提示了路由决策
    assert any("路由" in c.get("text", "") for c in api._window.calls
               if c["kind"] == "status")


def test_set_active_free_route(api):
    r = api.set_active_model("route:free")
    assert r["ok"]
    assert r["active_label"] == "自由路由"
    assert api.assets.active == "route:free"
    r2 = api.set_active_model("")
    assert r2["active_label"] == "自由路由"
    assert api.assets.active == "route:free"


def test_pinned_model_skips_free_route(api, monkeypatch):
    """钉死具体模型时，规则不得改道。"""
    from codeagent.core.types import LLMResponse

    seen = {}

    class FakeProvider:
        def __init__(self, model):
            self.model = model
            self.name = "fake"

        async def complete(self, messages, tools=None, system=None, **kw):
            seen["model"] = self.model
            return LLMResponse(content="ok")

    monkeypatch.setattr(
        "codeagent.desktop.api.parse_provider_spec",
        lambda *a, **k: FakeProvider("legacy"),
    )
    monkeypatch.setattr(
        "codeagent.llm.ollama.OllamaProvider",
        lambda model, base_url: FakeProvider(model),
    )
    ep = api.assets.endpoints[0]
    api.set_active_model(f"local:pinned-model@{ep.id}")
    api.add_route_rule("代码调试", "报错", f"local:routed-model@{ep.id}")
    assert api.send("这里有报错") is True
    wait_for(api._window, "done")
    assert seen["model"] == "pinned-model"


def test_chat_free_route_falls_back_to_mixture(api, monkeypatch):
    """自由路由未命中关键词时，走第一个启用的聚合池，而不是空 Provider。"""
    from codeagent.core.types import LLMResponse

    seen = {}

    class FakeProvider:
        def __init__(self, model):
            self.model = model
            self.name = "fake"

        async def complete(self, messages, tools=None, system=None, **kw):
            seen["model"] = self.model
            return LLMResponse(content="ok")

    monkeypatch.setattr(
        "codeagent.desktop.api.parse_provider_spec",
        lambda *a, **k: FakeProvider("legacy"),
    )
    monkeypatch.setattr(
        "codeagent.llm.ollama.OllamaProvider",
        lambda model, base_url: FakeProvider(model),
    )
    members = _two_members(api)
    api.save_mixture("默认池", "cascade", members)
    api.set_active_model("route:free")
    api.config.provider = ""
    api.config.model = ""
    assert api.send("你好呀") is True
    wait_for(api._window, "done")
    assert seen["model"] == "qwen3:8b"


def test_chat_free_route_cloud_500_fails_over(api, monkeypatch):
    """自由路由命中通义后若 500，自动改走聚合池里的本地模型。"""
    from codeagent.core.types import LLMResponse

    seen: list[str] = []

    class BoomCloud:
        name = "openai"

        def __init__(self, model, **kwargs):
            self.model = model

        async def complete(self, messages, tools=None, system=None, **kw):
            seen.append(self.model)
            raise RuntimeError(
                "Error code: 500 - {'error': {'message': '<500> InternalError.Algo: "
                "An error occurred in model serving', 'code': 'internal_server_error'}}"
            )

    class LocalOk:
        name = "ollama"

        def __init__(self, model, **kwargs):
            self.model = model

        async def complete(self, messages, tools=None, system=None, **kw):
            seen.append(self.model)
            return LLMResponse(content="local-backup")

    monkeypatch.setattr("codeagent.llm.openai.OpenAIProvider", BoomCloud)
    monkeypatch.setattr("codeagent.llm.ollama.OllamaProvider", LocalOk)
    r = api.add_api_model(
        "https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-boom",
    )
    ep = api.assets.endpoints[0]
    api.save_mixture("默认池", "cascade", [
        f"local:qwen3:8b@{ep.id}", f"api:{r['id']}",
    ])
    api.set_active_model("route:free")
    api.add_route_rule("分析", "分析", f"api:{r['id']}")
    assert api.send("请分析一下这个问题") is True
    done = wait_for(api._window, "done")
    assert done["text"] == "local-backup"
    assert "qwen-boom" in seen
    assert "qwen3:8b" in seen


def test_chat_free_route_empty_assets_friendly_error(api, monkeypatch):
    """自由路由既无规则也无模型资产、偏好又为空时，给出中文提示而不是 Empty provider spec。"""
    api.set_active_model("route:free")
    api.config.provider = ""
    api.config.model = ""
    monkeypatch.setattr(api, "_probed_local", lambda ttl=30.0: {})
    assert api.send("随便聊聊") is True
    err = wait_for(api._window, "error")
    assert "自由路由" in err["text"]
    assert "Empty provider spec" not in err["text"]


def test_chat_free_route_falls_back_to_local(api, monkeypatch):
    """自由路由未命中规则时，可用本机模型兜底，不再要求空关键词规则。"""
    from codeagent.core.types import LLMResponse

    seen = {}

    class FakeProvider:
        def __init__(self, model):
            self.model = model
            self.name = "fake"

        async def complete(self, messages, tools=None, system=None, **kw):
            seen["model"] = self.model
            return LLMResponse(content="ok")

    monkeypatch.setattr(
        "codeagent.desktop.api.parse_provider_spec",
        lambda *a, **k: FakeProvider("legacy"),
    )
    monkeypatch.setattr(
        "codeagent.llm.ollama.OllamaProvider",
        lambda model, base_url: FakeProvider(model),
    )
    ep = api.assets.endpoints[0]
    monkeypatch.setattr(api, "_probed_local", lambda ttl=30.0: {ep.id: ["qwen3:8b"]})
    api.set_active_model("route:free")
    api.config.provider = ""
    api.config.model = ""
    assert api.send("你好呀") is True
    wait_for(api._window, "done")
    assert seen["model"] == "qwen3:8b"


# ---------------------------------------------------------------------------
# permissions (LCA 权限控制)
# ---------------------------------------------------------------------------


def test_permissions_matrix_and_levels(api):
    data = api.get_permissions()
    caps = {c["id"]: c for c in data["capabilities"]}
    assert {"fs_read", "fs_write", "shell", "network", "delegate"} <= set(caps)
    assert caps["fs_write"]["level"] == "confirm"  # default
    r = api.set_permission_level("fs_write", "off")
    assert r["ok"]
    assert api.get_permissions()["capabilities"][1]["level"] == "off"
    assert not api.set_permission_level("fs_write", "bogus")["ok"]
    # 审计留痕
    audit = api.get_permissions()["audit"]
    assert any("文件写入" in a["action"] for a in audit)


def test_permission_policy_mapping(api):
    import asyncio
    from codeagent.core.types import ToolCall
    from codeagent.desktop.permissions import build_policy
    from codeagent.security.policy import ApprovalDecision

    levels = {"fs_read": "full", "fs_write": "off", "shell": "readonly",
              "network": "full", "delegate": "off"}
    policy = build_policy(levels, None)

    async def check(tool):
        return await policy.authorize(ToolCall(name=tool, arguments={}), 0)

    assert asyncio.run(check("read_file")) == ApprovalDecision.APPROVE
    assert asyncio.run(check("write_file")) == ApprovalDecision.DENY
    assert asyncio.run(check("bash")) == ApprovalDecision.DENY
    assert asyncio.run(check("web_fetch")) == ApprovalDecision.APPROVE
    assert asyncio.run(check("browser")) == ApprovalDecision.APPROVE
    assert asyncio.run(check("delegate")) == ApprovalDecision.DENY
    # 拒绝已记入审计
    from codeagent.desktop.permissions import read_audit
    assert any("write_file" in a["action"] for a in read_audit())


def test_confirmer_approve_and_timeout(api):
    import asyncio
    import threading
    from codeagent.core.types import ToolCall
    from codeagent.desktop.permissions import Confirmer
    from codeagent.security.policy import ApprovalDecision, RiskLevel

    pushes = []
    confirmer = Confirmer(lambda kind, data: pushes.append((kind, data)))
    call = ToolCall(name="bash", arguments={"command": "ls"})

    result = {}

    def ask():
        result["d"] = confirmer.ask(call, RiskLevel.EXECUTE)

    t = threading.Thread(target=ask)
    t.start()
    # 等 push 到达后批准
    deadline = time.time() + 5
    while not pushes and time.time() < deadline:
        time.sleep(0.02)
    assert pushes and pushes[0][0] == "confirm"
    cid = pushes[0][1]["id"]
    assert confirmer.resolve(cid, True)
    t.join(timeout=5)
    assert result["d"] == ApprovalDecision.APPROVE

    # 超时路径：把超时缩到 0.1s
    confirmer.TIMEOUT_S = 0.1
    d = confirmer.ask(call, RiskLevel.EXECUTE)
    assert d == ApprovalDecision.DENY


def test_versions_page_data(api):
    v = api.get_versions()
    assert v["current"]["version"]
    assert v["current"]["points"]
    assert isinstance(v["history"], list) and v["history"]


# ---------------------------------------------------------------------------
# activity stream & self-learning (LCA 卷三 · 自我学习)
# ---------------------------------------------------------------------------


def test_open_feedback_mail(api, monkeypatch):
    opened: list[str] = []
    monkeypatch.setattr("webbrowser.open", lambda url, new=0: opened.append(url) or True)
    r = api.open_feedback_mail()
    assert r["ok"]
    assert r["mailto"].startswith("mailto:alan_dan@live.com")
    assert "CodeCoreAgent" in r["mailto"]
    assert opened and opened[0] == r["mailto"]


def test_open_official_site(api, monkeypatch):
    opened: list[str] = []
    monkeypatch.setattr("webbrowser.open", lambda url, new=0: opened.append(url) or True)
    r = api.open_official_site()
    assert r["ok"]
    assert r["url"] == "http://codecoreagent.com"
    assert opened and opened[0] == r["url"]


def test_open_privacy_page(api, monkeypatch):
    opened: list[str] = []
    monkeypatch.setattr("webbrowser.open", lambda url, new=0: opened.append(url) or True)
    r = api.open_privacy_page()
    assert r["ok"]
    assert r["url"] == "http://codecoreagent.com/privacy.html"
    assert opened and opened[0] == r["url"]


def test_feedback_writes_learn_activity(api):
    assert api.send_feedback(True)["ok"]
    assert api.send_feedback(False)["ok"]
    entries = api.get_activity()
    learns = [e for e in entries if e["kind"] == "learn"]
    assert any("正向" in e["text"] for e in learns)
    assert any("点踩" in e["text"] for e in learns)


def test_learn_now_requires_samples(api):
    r = api.learn_now()
    assert not r["ok"] and "反馈样本" in r["error"]


def test_learn_now_upserts_today(api):
    api.send_feedback(True)
    api.send_feedback(True)
    api.send_feedback(False)
    r = api.learn_now()
    assert r["ok"] and r["samples"] == 3 and r["accuracy"] == 67
    data = api.get_learning()
    assert data["total_samples"] == 3
    assert data["records"][-1]["thumbs_up"] == 2
    # 同日覆盖而非追加
    api.send_feedback(True)
    r2 = api.learn_now()
    assert r2["samples"] == 4
    assert len(api.get_learning()["records"]) == 1


def test_learn_now_low_accuracy_shifts_local_first(api):
    api.send_feedback(False)
    api.send_feedback(False)
    api.send_feedback(True)
    before = api.router.weights.local_first
    r = api.learn_now()
    assert r["ok"] and r["accuracy"] == 33
    assert api.router.weights.local_first == min(100, before + 5)


# ---------------------------------------------------------------------------
# automation workflows (LCA 卷三 · 自动化)
# ---------------------------------------------------------------------------


def _wf_steps():
    return [{"name": "采集", "tool": ""}, {"name": "汇总", "tool": ""}]


def test_workflow_crud(api):
    assert not api.add_workflow("", "", "manual", _wf_steps())["ok"]
    assert not api.add_workflow("x", "", "manual", [])["ok"]
    r = api.add_workflow("巡检", "每日代码巡检", "cron", _wf_steps())
    assert r["ok"]
    wfs = api.get_workflows()
    assert len(wfs) == 1 and wfs[0]["name"] == "巡检"
    assert wfs[0]["trigger"] == "cron"
    assert wfs[0]["step_labels"] == ["当前激活模型", "当前激活模型"]
    assert api.delete_workflow(wfs[0]["id"])
    assert api.get_workflows() == []


def test_workflow_run_executes_steps_and_audits(api, monkeypatch):
    seen = []

    def fake_run_step(step, context):
        seen.append((step.name, context))
        return f"产出-{step.name}"

    api.runner._run_step = fake_run_step
    api.add_workflow("测试流", "", "manual", _wf_steps())
    wf = api.get_workflows()[0]
    assert api.run_workflow(wf["id"])["ok"]
    deadline = time.time() + 5
    while time.time() < deadline:
        cur = api.get_workflows()[0]
        if cur["status"] == "idle" and cur["runs"] == 1:
            break
        time.sleep(0.05)
    else:
        raise AssertionError("workflow did not finish")
    # 步骤链：第二步拿到第一步的产出作为上下文
    assert seen[0] == ("采集", "")
    assert seen[1][0] == "汇总" and "产出-采集" in seen[1][1]
    assert cur["last_run"] != "-"
    kinds = [e["text"] for e in api.get_activity() if e["kind"] == "workflow"]
    assert any("开始执行" in t for t in kinds)
    assert any("执行完成" in t for t in kinds)


def test_workflow_continuous_loops_until_paused(api):
    rounds = []

    def fake_run_step(step, context):
        rounds.append(step.name)
        return "ok"

    api.runner._run_step = fake_run_step
    import codeagent.desktop.automation as auto
    auto.CONTINUOUS_DELAY_S = 0.05
    api.add_workflow("连续流", "", "manual", [{"name": "s", "tool": ""}])
    wf = api.get_workflows()[0]
    assert api.set_workflow_continuous(wf["id"], True)
    api.run_workflow(wf["id"])
    deadline = time.time() + 5
    while len(rounds) < 3 and time.time() < deadline:
        time.sleep(0.05)
    assert len(rounds) >= 3  # 自动衔接了多轮
    api.pause_workflow(wf["id"])
    assert api.get_workflows()[0]["status"] == "paused"


def test_workflow_double_start_rejected(api):
    block = threading.Event()

    def slow_step(step, context):
        block.wait(2)
        return "ok"

    api.runner._run_step = slow_step
    api.add_workflow("慢流", "", "manual", [{"name": "s", "tool": ""}])
    wf = api.get_workflows()[0]
    assert api.run_workflow(wf["id"])["ok"]
    r = api.run_workflow(wf["id"])
    assert not r["ok"] and "运行中" in r["error"]
    block.set()


# ---------------------------------------------------------------------------
# cron (LCA 卷三 · 定时任务)
# ---------------------------------------------------------------------------


def test_cron_expression_matching():
    from codeagent.desktop.cron import cron_matches

    tm = time.struct_time((2026, 8, 31, 8, 0, 0, 0, 243, 0))  # 周一 08:00
    assert cron_matches("0 8 * * *", tm)
    assert cron_matches("*/30 * * * *", tm)
    assert cron_matches("0 8 * * 1", tm)
    assert not cron_matches("0 9 * * *", tm)
    assert not cron_matches("0 8 * * 5", tm)
    assert not cron_matches("bad", tm)
    assert not cron_matches("61 * * * *", tm)


def test_cron_next_run_hint():
    from codeagent.desktop.cron import next_run_hint

    hint = next_run_hint("*/30 * * * *")
    assert hint != "待调度器计算"
    assert len(hint) == len("08-31 09:00")


def test_cron_job_crud(api):
    assert not api.add_cron_job("", "0 8 * * *", "x")["ok"]
    assert not api.add_cron_job("x", "0 8", "x")["ok"]  # 非五字段
    r = api.add_cron_job("每晚备份", "0 2 * * *", "备份对话")
    assert r["ok"]
    jobs = api.get_cron()["jobs"]
    assert len(jobs) == 1 and jobs[0]["enabled"]
    assert jobs[0]["next_run"] != "待调度器计算"
    assert api.toggle_cron_job(jobs[0]["id"], False)
    assert not api.get_cron()["jobs"][0]["enabled"]
    assert api.delete_cron_job(jobs[0]["id"])
    assert api.get_cron()["jobs"] == []


def test_cron_scheduler_tick_fires_due_job(api):
    fired = []
    api.scheduler._run_action = lambda job: fired.append(job.id) or True
    api.add_cron_job("每分钟", "* * * * *", "心跳")
    hit = api.scheduler.tick()
    assert len(hit) == 1 and fired
    job = api.get_cron()["jobs"][0]
    assert job["last_result"] == "success"
    assert job["last_run"] != "-"
    # 同一分钟不重复触发
    assert api.scheduler.tick() == []


def test_cron_scheduler_disabled_job_skipped(api):
    api.scheduler._run_action = lambda job: True
    api.add_cron_job("停用任务", "* * * * *", "x")
    job = api.get_cron()["jobs"][0]
    api.toggle_cron_job(job["id"], False)
    assert api.scheduler.tick() == []


def test_cron_evolution_job_fires(api):
    api.scheduler._run_action = lambda job: True
    api.evolution.settings.enabled = True
    api.evolution.settings.cron = "* * * * *"
    hit = api.scheduler.tick()
    assert "__evolution__" in hit
    assert api.evolution.runs  # 进化作业真的跑了一轮


# ---------------------------------------------------------------------------
# evolution (LCA 卷三 · 进化日志)
# ---------------------------------------------------------------------------


def test_evolution_run_produces_patches(api):
    r = api.run_evolution_now()
    assert r["ok"] and r["patches"] >= 1
    data = api.get_evolution()
    assert len(data["runs"]) == 1
    run = data["runs"][0]
    assert [p["name"] for p in run["phases"]] == list(
        ["复盘员", "归因员", "路由师", "记忆官", "教官"])
    # L0 + autoApplyL01 → 直接 active
    assert any(p["status"] == "active" for p in data["patches"])


def test_evolution_l2_patch_needs_approval(api):
    # 跑多轮直到 L2 补丁（凭证类）出现
    for _ in range(3):
        api.run_evolution_now()
    patches = api.get_evolution()["patches"]
    l2 = next((p for p in patches if p["level"] == "L2"), None)
    assert l2 is not None
    assert l2["status"] == "pending"  # L2 必须人工批准


def test_patch_state_machine(api):
    api.run_evolution_now()
    patch = api.get_evolution()["patches"][0]
    assert api.set_patch_status(patch["id"], "disabled")["ok"]
    assert api.get_evolution()["patches"][0]["status"] == "disabled"
    assert api.set_patch_status(patch["id"], "active")["ok"]
    assert api.set_patch_status(patch["id"], "rolledback")["ok"]
    # 回滚是终态，但接口幂等
    assert not api.set_patch_status(patch["id"], "bogus")["ok"]
    # 审计：回滚记 denied
    from codeagent.desktop.permissions import read_audit
    audit = read_audit(20)
    rollback = next(a for a in audit if "回滚" in a["action"])
    assert rollback["result"] == "denied"


def test_active_patches_injected_into_settings(api):
    api.run_evolution_now()
    settings = api._settings_with_patches()
    assert settings.instructions  # 有补丁注入
    api.settings.instructions = "原有说明"
    settings = api._settings_with_patches()
    assert "原有说明" in settings.instructions  # 不覆盖用户个性化


def test_approve_skill_becomes_workflow(api):
    api.run_evolution_now()
    api.run_evolution_now()  # 第二轮才草拟技能
    runs = api.get_evolution()["runs"]
    draft_run = next((r for r in runs if r["skill_drafts"]), None)
    assert draft_run is not None
    draft = draft_run["skill_drafts"][0]
    r = api.approve_skill(draft_run["id"], draft["id"])
    assert r["ok"]
    wfs = api.get_workflows()
    assert any(w["name"] == draft["name"] and w["trigger"] == "cron"
               for w in wfs)
    # 重复批准被拒
    assert not api.approve_skill(draft_run["id"], draft["id"])["ok"]


def test_evolution_settings_gates(api):
    r = api.save_evolution_settings(False, True, True, "0 3 * * *")
    assert r["ok"]
    s = api.get_evolution()["settings"]
    assert not s["enabled"] and s["cron"] == "0 3 * * *"
    # 非法 cron 不覆盖
    api.save_evolution_settings(True, True, True, "bad")
    assert api.get_evolution()["settings"]["cron"] == "0 3 * * *"


def test_nav_status(api):
    s = api.get_nav_status()
    assert {"running", "online", "mixtures", "local", "api", "active"} <= set(s)
    assert s["local"] == 1  # fixture 默认本机端点
    assert s["api"] == 0
    assert s["mixtures"] == 0
    assert s["active"] == "自由路由"


def test_nav_status_counts_configured_assets(api):
    members = _two_members(api)
    api.save_mixture("状态池", "weighted", members)
    s = api.get_nav_status()
    assert s["api"] == 1
    assert s["mixtures"] == 1
    assert s["local"] >= 1


def test_internal_browser_ready_without_bsk(api):
    st = api.browser_status()
    assert "内置浏览器" in st["ready_text"]
    assert st["backend"] == "idle"
    assert not api._browser.has_gui
    assert api.browser_pump() == 0
    assert api._browser.has_gui  # JS interval arms the live window
    brow = api._agent_tools().get("browser")
    assert brow is not None
    assert brow.engine is api._browser


def test_voice_session_injects_emotion_prompt(api):
    assert api.set_voice_session(True)["on"] is True
    text = api._settings_with_patches().instructions or ""
    assert "[emotion:happy]" in text
    assert "语音连续对话" in text
    assert api.set_voice_session(False)["on"] is False
    kinds = api._window.kinds()
    assert "voice" in kinds


def test_open_mic_settings_uses_privacy_microphone_url(monkeypatch):
    from codeagent.desktop import mic as mic_mod

    calls = []

    def fake_run(cmd, **kw):
        calls.append(list(cmd))

        class R:
            returncode = 0
            stderr = ""

        return R()

    monkeypatch.setattr(mic_mod.sys, "platform", "darwin")
    monkeypatch.setattr(mic_mod.subprocess, "run", fake_run)
    r = mic_mod.open_mic_settings()
    assert r["ok"] is True
    assert "Privacy_Microphone" in calls[0][1]
    assert "com.apple.settings.PrivacySecurity.extension" in calls[0][1]
    assert "麦克风" in r["path"]
    assert "CodeCoreAgent" in r["hint"]


def test_mic_permission_status_and_ensure(api, monkeypatch):
    from codeagent.desktop import mic as mic_mod

    monkeypatch.setattr(mic_mod, "mic_permission_status", lambda: {
        "status": "authorized", "speech_status": "authorized", "platform": "darwin",
    })
    assert api.mic_permission_status()["status"] == "authorized"
    assert api.ensure_mic_permission()["ok"] is True

    monkeypatch.setattr(mic_mod, "mic_permission_status", lambda: {
        "status": "authorized", "speech_status": "not_determined", "platform": "darwin",
    })
    monkeypatch.setattr(
        mic_mod, "request_mic_access",
        lambda timeout=90.0: {
            "ok": True, "status": "authorized", "speech_status": "authorized",
            "registered": True,
        },
    )
    r = api.ensure_mic_permission()
    assert r["ok"] is True and r.get("speech_status") == "authorized"

    opened = {}
    monkeypatch.setattr(mic_mod, "mic_permission_status", lambda: {
        "status": "authorized", "speech_status": "denied", "platform": "darwin",
    })
    monkeypatch.setattr(
        mic_mod, "request_mic_access",
        lambda timeout=90.0: {
            "ok": False, "status": "authorized", "speech_status": "denied",
            "message": mic_mod.SPEECH_SETTINGS_HINT, "path": mic_mod.SPEECH_SETTINGS_PATH,
        },
    )
    monkeypatch.setattr(
        mic_mod, "open_speech_settings",
        lambda: opened.update(speech=True) or {
            "ok": True, "path": mic_mod.SPEECH_SETTINGS_PATH,
        },
    )
    r = api.ensure_mic_permission()
    assert r["ok"] is False and r["open_settings"] is True
    assert opened.get("speech") is True
    assert "语音识别" in (r.get("message") or "")

    opened.clear()
    monkeypatch.setattr(mic_mod, "mic_permission_status", lambda: {
        "status": "denied", "speech_status": "denied", "platform": "darwin",
    })
    monkeypatch.setattr(
        mic_mod, "open_mic_settings",
        lambda: opened.update(ok=True) or {"ok": True, "path": "x"},
    )
    r = api.ensure_mic_permission()
    assert r["ok"] is False and r["open_settings"] is True
    assert opened.get("ok") is True
    assert api.open_mic_settings()["ok"] is True


def test_request_mic_access_api(api, monkeypatch):
    from codeagent.desktop import mic as mic_mod

    monkeypatch.setattr(
        mic_mod, "request_mic_access",
        lambda timeout=90.0: {
            "ok": True, "status": "authorized", "speech_status": "authorized",
            "registered": True,
        },
    )
    assert api.request_mic_access()["registered"] is True


def test_html_mentions_speech_recognition_gate():
    assert "语音识别" in HTML
    assert "open_speech_settings" in HTML
    assert "只开麦克风不够" in HTML


def test_html_mic_perm_settings_section():
    assert 'id="sectMicPerm"' in HTML
    assert "麦克风与语音识别权限" in HTML
    assert "refreshMicPermStatus" in HTML
    assert "requestMicFromSettings" in HTML
    assert "openMicFromSettings" in HTML
    assert "openSpeechFromSettings" in HTML


def test_start_native_listen_wires_events(api, monkeypatch):
    class FakeSession:
        def __init__(self):
            self.started = False
            self.on_text = None
            self._ev = threading.Event()

        def start(self, on_text, on_error=None, locale="zh-CN"):
            self.started = True
            self.on_text = on_text
            self._ev.set()
            return {"ok": True, "engine": "speech.framework", "locale": locale}

        def stop(self):
            self.started = False

    fake = FakeSession()
    monkeypatch.setattr(
        "codeagent.desktop.voice_listen.NativeSpeechSession",
        lambda: fake,
    )
    r = api.start_native_listen("zh-CN")
    assert r["ok"] is True and r.get("async") is True
    assert fake._ev.wait(2.0)
    assert fake.started
    fake.on_text("你好世界", True)
    time.sleep(0.05)
    kinds = api._window.kinds()
    assert "voice" in kinds
    assert api.stop_native_listen() is True


def test_native_speech_commit_once():
    from codeagent.desktop.voice_listen import NativeSpeechSession

    sess = NativeSpeechSession()
    calls: list[tuple[str, bool]] = []
    sess._on_text = lambda t, f: calls.append((t, f))
    sess._active = True
    sess._committed = False
    sess._finish_utterance = lambda: None  # type: ignore[method-assign]
    sess._commit("你好呀")
    sess._commit("你好呀")
    sess._commit("")
    assert calls == [("你好呀", True)]
    assert sess._committed is True


def test_html_mentions_voice_answer_chip():
    assert "说完了 — 正在想并准备语音回答" in HTML


def test_macos_mic_status_mapping(monkeypatch):
    from codeagent.desktop import mic as mic_mod

    class Device:
        @staticmethod
        def authorizationStatusForMediaType_(media):
            assert media == "soun"
            return 3

    class Bundle:
        def load(self):
            return True

    monkeypatch.setattr(mic_mod.sys, "platform", "darwin")
    import sys
    import types

    fake_objc = types.ModuleType("objc")
    fake_objc.lookUpClass = lambda name: Device
    fake_foundation = types.ModuleType("Foundation")
    fake_foundation.NSBundle = types.SimpleNamespace(
        bundleWithPath_=lambda path: Bundle()
    )
    monkeypatch.setitem(sys.modules, "objc", fake_objc)
    monkeypatch.setitem(sys.modules, "Foundation", fake_foundation)
    assert mic_mod._macos_status() == "authorized"
    assert mic_mod.mic_permission_status()["status"] == "authorized"


# ---------------------------------------------------------------------------
# theme (浅色主题)
# ---------------------------------------------------------------------------


def test_theme_persists_in_config(api, tmp_path):
    api.save_config({"theme": "light"})
    assert api.config.theme == "light"
    assert DesktopConfig.load(tmp_path / "desktop.json").theme == "light"
    api.save_config({"theme": "auto"})
    assert api.config.theme == "auto"
    # 非法值回退深色
    api.save_config({"theme": "neon"})
    assert api.config.theme == "dark"


def test_ui_has_light_theme_and_toggle():
    assert "body.light" in HTML
    assert "codeagent-theme" in HTML
    # 主题切换位于偏好设置页：深色 / 浅色 / 自动跟随系统 三档分段控件
    assert 'id="themeTabs"' in HTML
    assert 'data-theme="dark"' in HTML
    assert 'data-theme="light"' in HTML
    assert 'data-theme="auto"' in HTML
    assert "setTheme" in HTML
    assert "prefers-color-scheme: light" in HTML


# ---------------------------------------------------------------------------
# chat composer: attachments / thinking / copy-share
# ---------------------------------------------------------------------------


def test_attachment_text_file(tmp_path):
    from codeagent.desktop.attachments import read_attachment

    f = tmp_path / "notes.md"
    f.write_text("# 标题\n内容", encoding="utf-8")
    info = read_attachment(f)
    assert info["kind"] == "text"
    assert "标题" in info["text"]


def test_attachment_docx_stdlib_extraction(tmp_path):
    import zipfile
    from codeagent.desktop.attachments import read_attachment

    f = tmp_path / "doc.docx"
    with zipfile.ZipFile(f, "w") as zf:
        zf.writestr("word/document.xml",
                    "<w:p><w:t>你好世界</w:t></w:p><w:p><w:t>第二段</w:t></w:p>")
    info = read_attachment(f)
    assert info["kind"] == "docx"
    assert "你好世界" in info["text"] and "第二段" in info["text"]


def test_attachment_binary_and_image_fallback(tmp_path):
    from codeagent.desktop.attachments import read_attachment

    img = tmp_path / "p.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
    info = read_attachment(img)
    assert info["kind"] == "image" and not info["text"] and info["note"]

    blob = tmp_path / "d.bin"
    blob.write_bytes(bytes(range(256)))
    info = read_attachment(blob)
    assert info["kind"] == "binary" and info["note"]


def test_attachment_long_text_capped(tmp_path):
    from codeagent.desktop.attachments import MAX_CHARS, read_attachment

    f = tmp_path / "big.txt"
    f.write_text("x" * (MAX_CHARS + 5000), encoding="utf-8")
    info = read_attachment(f)
    assert len(info["text"]) == MAX_CHARS
    assert "截取" in info["note"]


def test_format_attachments():
    from codeagent.desktop.attachments import format_attachments

    block = format_attachments([
        {"name": "a.txt", "size": "3 B", "text": "hello", "note": ""},
        {"name": "b.png", "size": "1 KB", "text": "", "note": "图片文件"},
    ])
    assert "【附件：a.txt" in block and "hello" in block
    assert "b.png" in block and "图片文件" in block


def test_send_combines_attachments(api):
    captured = {}
    orig_run = api._run_chat
    api._run_chat = lambda text, _recall="": (captured.setdefault("text", text),
                                  setattr(api, "_busy", False))
    api._attachments = [{"name": "a.txt", "size": "3 B", "text": "文件内容",
                         "note": ""}]
    assert api.send("看看这个") is True
    assert "文件内容" in captured["text"] and "看看这个" in captured["text"]
    assert api._attachments == []
    api._run_chat = orig_run


def test_send_memory_query_uses_user_text_not_attachments(api):
    captured = {}
    orig_run = api._run_chat

    def stub(text, memory_query=""):
        captured["text"] = text
        captured["recall"] = memory_query
        api._busy = False

    api._run_chat = stub
    api._attachments = [{"name": "a.txt", "size": "3 B", "text": "附件里写了数据库",
                         "note": ""}]
    assert api.send("偏好怎么配") is True
    assert captured["recall"] == "偏好怎么配"
    assert "数据库" in captured["text"]
    api._run_chat = orig_run


def test_send_attachment_only_no_text(api):
    api._run_chat = lambda text, _recall="": setattr(api, "_busy", False)
    api._attachments = [{"name": "a.txt", "size": "3 B", "text": "x", "note": ""}]
    assert api.send("") is True  # 仅附件也可发送
    assert api._attachments == []


def test_remove_attachment(api):
    api._attachments = [{"name": "a"}, {"name": "b"}]
    rest = api.remove_attachment(0)
    assert [a["name"] for a in rest] == ["b"]


def test_copy_text_uses_system_clipboard(api):
    sample = "hello 剪贴板"
    assert api.copy_text(sample) is True  # macOS pbcopy
    assert sample in api.read_clipboard()


def test_clipboard_copy_falls_back_to_usr_bin_pbcopy(monkeypatch):
    import subprocess

    calls = []

    def fake_run(cmd, **kw):
        calls.append(list(cmd))

        class R:
            returncode = 0
            stdout = b""

        return R()

    monkeypatch.setattr("codeagent.desktop.api._macos_pasteboard_write", lambda text: False)
    monkeypatch.setattr(subprocess, "run", fake_run)
    from codeagent.desktop.api import _clipboard_copy

    assert _clipboard_copy("hello") is True
    assert calls[0] == ["/usr/bin/pbcopy"]


def test_webkit_clipboard_prefs_enable_dom_paste():
    seen: list[tuple] = []

    class Prefs:
        def setValue_forKey_(self, value, key):
            seen.append((key, value))

        def setJavaScriptCanAccessClipboard_(self, value):
            seen.append(("setter", value))

    class Config:
        def preferences(self):
            return Prefs()

    class Web:
        def configuration(self):
            return Config()

    class View:
        webview = Web()

    from codeagent.desktop.app import apply_webkit_clipboard_prefs

    apply_webkit_clipboard_prefs(View())
    assert ("DOMPasteAllowed", True) in seen
    assert ("javaScriptCanAccessClipboard", True) in seen
    assert ("setter", True) in seen


def test_speak_text_replays_without_voice_toggle(api, monkeypatch):
    seen = {}
    monkeypatch.setattr(api, "stop_speaking", lambda: True)
    monkeypatch.setattr(
        api, "_speak", lambda text, force=False: seen.update(text=text, force=force)
    )
    assert api.speak_text("请回播这一段") is True
    assert seen["text"] == "请回播这一段"
    assert seen["force"] is True
    assert api.speak_text("   ") is False


def test_stop_speaking_pushes_spoken(api, monkeypatch):
    stopped = {}
    monkeypatch.setattr(
        "codeagent.voice.tts.stop_audio",
        lambda: stopped.update(ok=True),
    )
    assert api.stop_speaking() is True
    assert stopped.get("ok") is True
    assert "voice" in api._window.kinds()
    assert any(
        c.get("kind") == "voice" and c.get("state") == "spoken"
        for c in api._window.calls
    )


def test_clipboard_copy_windows_uses_utf16(monkeypatch):
    import subprocess

    calls = []

    def fake_run(cmd, **kw):
        calls.append((list(cmd), kw.get("input")))

        class R:
            returncode = 0
            stdout = b""

        return R()

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr("sys.platform", "win32")
    from codeagent.desktop.api import _clipboard_copy, _win_clip_bin

    assert _clipboard_copy("你好") is True
    assert calls[0][0] == [_win_clip_bin()]
    assert calls[0][1] == "你好".encode("utf-16le")


def test_thinking_config_validation(api):
    api.save_config({"thinking": "high"})
    assert api.config.thinking == "high"
    api.save_config({"thinking": "extreme"})
    assert api.config.thinking == "medium"


def test_thinking_injected_into_settings(api):
    api.save_config({"thinking": "high"})
    s = api._settings_with_patches()
    assert "思考强度=高" in s.instructions
    api.save_config({"thinking": "low"})
    assert "思考强度=低" in api._settings_with_patches().instructions


def test_ui_chat_composer_features():
    assert 'id="attBtn"' in HTML and 'id="attRow"' in HTML
    assert 'id="thinkingSel"' in HTML
    assert "function addThink" in HTML
    assert "think-block" in HTML
    assert "思考过程" in HTML
    assert "ev.kind==='thinking'" in HTML
    assert "function addThinkTool" in HTML
    assert "function ensureThink" in HTML
    assert "think-tools" in HTML and "think-reason" in HTML
    assert "addThinkTool(ev.name" in HTML  # 工具调用收进思考折叠块
    assert "think-wrap" in HTML  # 同一轮只保留一块思考过程
    assert 'id="modelPicker"' in HTML  # 页眉模型选择
    assert "route:free" in HTML
    assert "自由路由" in HTML
    assert "选择模型…" not in HTML
    assert 'id="composerProj"' not in HTML  # 输入区不再放项目/模型下拉
    assert 'id="videoGenBar"' in HTML
    assert 'id="vg_res"' in HTML and 'id="vg_frames"' in HTML and 'id="vg_steps"' in HTML
    assert "syncVideoGenBar" in HTML
    assert "isVideoModelSelected" in HTML
    assert "composer-video" in HTML
    assert "function renderReply" in HTML
    assert "cls==='bot'?renderReply" in HTML
    assert "curBot.innerHTML=renderReply" in HTML
    assert "msg-actions" in HTML and "copy_text" in HTML
    assert "copyChatAll" in HTML and "复制全部" in HTML
    assert 'id="replayBtn"' in HTML and "speakText" in HTML
    assert 'id="stopSpeakTool"' in HTML and "stopSpeak()" in HTML
    assert "停止播报" in HTML
    assert "setSpeakingUi" in HTML
    assert "stop_speaking" in HTML
    assert "⏹ 停止播报" in HTML
    assert "回播失败" in HTML
    assert "🔊 回播" in HTML
    assert "speak_text" in HTML
    assert "chatPlainText" in HTML
    assert "user-select: text" in HTML
    assert "_ctxSel" in HTML and "insertAtCursor" in HTML
    assert "execCommand('copy')" in HTML
    assert HTML.find("pywebview.api.copy_text") < HTML.find("navigator.clipboard.writeText")
    assert "WKWebView 需打开 DOMPasteAllowed" in HTML
    app_src = Path(__file__).resolve().parents[1].joinpath(
        "src/codeagent/desktop/app.py"
    ).read_text(encoding="utf-8")
    assert "text_select=True" in app_src
    assert "private_mode=False" in app_src
    assert "DOMPasteAllowed" in app_src
    assert "export_message" in HTML
    assert "pick_attachments" in HTML
    assert 'id="stopBtn"' in HTML and "stopChat()" in HTML
    assert "setChatBusy" in HTML
    assert "ev.kind==='stopped'" in HTML
    assert "hidden>停止" not in HTML


# ---------------------------------------------------------------------------
# theme startup injection（重启后主题保持）
# ---------------------------------------------------------------------------


def test_themed_html_injects_light(tmp_path, monkeypatch):
    import codeagent.desktop.api as api_mod
    from codeagent.desktop.app import _themed_html

    monkeypatch.setattr(api_mod, "DESKTOP_CONFIG_PATH", tmp_path / "d.json")
    DesktopConfig(theme="light").save(tmp_path / "d.json")
    assert '<body class="light">' in _themed_html()

    DesktopConfig(theme="dark").save(tmp_path / "d.json")
    assert '<body class="light">' not in _themed_html()


def test_themed_html_auto_follows_system(tmp_path, monkeypatch):
    import codeagent.desktop.api as api_mod
    import codeagent.desktop.app as app_mod

    monkeypatch.setattr(api_mod, "DESKTOP_CONFIG_PATH", tmp_path / "d.json")
    DesktopConfig(theme="auto").save(tmp_path / "d.json")
    monkeypatch.setattr(app_mod, "_system_light", lambda: True)
    assert '<body class="light">' in app_mod._themed_html()
    monkeypatch.setattr(app_mod, "_system_light", lambda: False)
    assert '<body class="light">' not in app_mod._themed_html()


def test_ui_theme_storage_is_fault_tolerant():
    # localStorage 抛异常也不能阻断保存：全部走安全包装
    assert "storeSet(THEME_KEY,t)" in HTML
    assert "try{localStorage" in HTML or "catch(e)" in HTML
    # 启动时无条件以服务端配置为准
    assert "applyTheme(st.config.theme" in HTML


# ---------------------------------------------------------------------------
# detect_service（自动识别必须带 Key）
# ---------------------------------------------------------------------------


class _FakeResp:
    def __init__(self, status, payload=None):
        self.status_code = status
        self._payload = payload or {}

    def json(self):
        return self._payload


class _FakeClient:
    """记录请求头并返回脚本化响应的 httpx.AsyncClient 替身。"""

    script = {}   # url_suffix -> _FakeResp | Exception
    seen = []     # (url, headers)

    def __init__(self, **kw):
        self.headers = kw.get("headers") or {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url):
        _FakeClient.seen.append((url, dict(self.headers)))
        for suffix, outcome in _FakeClient.script.items():
            if url.endswith(suffix):
                if isinstance(outcome, Exception):
                    raise outcome
                return outcome
        raise ConnectionError("no script")


def _patch_client(monkeypatch, script):
    import httpx
    from codeagent.desktop import models as m

    _FakeClient.script = script
    _FakeClient.seen = []
    monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)
    return m


def test_probe_endpoint_info_falls_back_to_openai(monkeypatch):
    import asyncio
    from codeagent.desktop import models as m

    _patch_client(monkeypatch, {
        "/api/tags": _FakeResp(404, {"error": {"message": "unknown"}}),
        "/v1/models": _FakeResp(200, {
            "data": [{"id": "deepseek-v4-flash", "context_length": 128000}],
        }),
    })
    info = asyncio.run(m.probe_endpoint_info("http://192.168.3.6:9000"))
    assert info["kind"] == "openai"
    assert info["models"][0]["name"] == "deepseek-v4-flash"


def test_probe_endpoint_info_detects_gradio(monkeypatch):
    import asyncio
    from codeagent.desktop import models as m

    _patch_client(monkeypatch, {
        "/api/tags": _FakeResp(404),
        "/v1/models": _FakeResp(404),
        "/models": _FakeResp(404),
        "/config": _FakeResp(200, {
            "version": "6.26.0",
            "title": "WAN-1.3B 文生视频",
            "components": [{}],
            "dependencies": [{}],
        }),
        "/gradio_api/info": _FakeResp(200, {
            "named_endpoints": {"/generate_video": {}},
        }),
    })
    info = asyncio.run(m.probe_endpoint_info("http://192.168.3.23:7860"))
    assert info["kind"] == "gradio"
    assert info["models"][0]["name"] == "WAN-1.3B 文生视频"
    assert info["models"][0]["quant"] == "文生视频"


def test_detect_service_gradio(monkeypatch):
    m = _patch_client(monkeypatch, {
        "/models": _FakeResp(404),
        "/v1/models": _FakeResp(404),
        "/api/tags": _FakeResp(404),
        "/config": _FakeResp(200, {
            "version": "6.26.0",
            "title": "WAN-1.3B 文生视频",
            "components": [{}],
            "dependencies": [{}],
        }),
        "/gradio_api/info": _FakeResp(200, {
            "named_endpoints": {"/generate_video": {}},
        }),
    })
    r = asyncio.run(m.detect_service("http://192.168.3.23:7860"))
    assert r["kind"] == "gradio"
    assert "WAN-1.3B" in r["models"][0]
    assert "对话" in r["note"]


def test_gradio_endpoint_is_not_chat_provider():
    from codeagent.desktop.models import ModelAssets, OllamaEndpoint

    ep = OllamaEndpoint(base="http://192.168.3.23:7860", kind="gradio", id="g1")
    assets = ModelAssets(endpoints=[ep], active="local:WAN@g1")
    assert assets.resolve_member("local:WAN@g1") is None


def test_set_active_gradio_video_model(api):
    from codeagent.desktop.models import OllamaEndpoint

    ep = OllamaEndpoint(base="http://192.168.3.23:7860", kind="gradio",
                        id="g1", label="WAN")
    api.assets.endpoints = [ep]
    r = api.set_active_model("local:WAN@g1")
    assert r["ok"]
    assert "文生视频" in r["active_label"]
    assert api._active_video_ep() is not None


def test_send_video_params_without_gradio_still_chats(api):
    """Extra send() args are ignored unless a Gradio model is active."""
    captured = {}
    orig = api._run_chat
    api._run_chat = lambda text, _recall="": (captured.setdefault("text", text),
                                  setattr(api, "_busy", False))
    api._run_video_gen = lambda *a, **k: captured.setdefault("video", True)
    assert api.send("你好", "1080p", 81, 40) is True
    assert captured.get("text") == "你好"
    assert "video" not in captured
    api._run_chat = orig


def test_ui_mentions_gradio_video():
    assert "Gradio 文生视频" in HTML
    assert "去视频运营" in HTML
    assert "不能作为对话模型添加" in HTML
    assert "ComfyUI 节点图" in HTML


def test_probe_endpoint_info_detects_comfy(monkeypatch):
    import asyncio
    from codeagent.desktop import models as m

    _patch_client(monkeypatch, {
        "/api/tags": _FakeResp(404),
        "/v1/models": _FakeResp(404),
        "/models": _FakeResp(404),
        "/config": _FakeResp(404),
        "/system_stats": _FakeResp(200, {"system": {"os": "win"}, "devices": []}),
        "/models/checkpoints": _FakeResp(200, ["sdxl.safetensors"]),
        "/models/diffusion_models": _FakeResp(200, []),
        "/models/loras": _FakeResp(200, []),
    })
    info = asyncio.run(m.probe_endpoint_info("http://192.168.3.23:8188"))
    assert info["kind"] == "comfy"
    assert info["models"][0]["name"] == "sdxl.safetensors"
    assert info["models"][0]["quant"] == "节点图"


def test_detect_service_comfy(monkeypatch):
    m = _patch_client(monkeypatch, {
        "/models": _FakeResp(404),
        "/v1/models": _FakeResp(404),
        "/api/tags": _FakeResp(404),
        "/config": _FakeResp(404),
        "/system_stats": _FakeResp(200, {"system": {}, "devices": []}),
        "/models/checkpoints": _FakeResp(200, ["flux.safetensors"]),
        "/models/diffusion_models": _FakeResp(200, []),
        "/models/loras": _FakeResp(200, []),
    })
    r = asyncio.run(m.detect_service("http://192.168.3.23:8188"))
    assert r["kind"] == "comfy"
    assert "flux.safetensors" in r["models"]
    assert "对话" in r["note"]


def test_comfy_endpoint_is_not_chat_provider():
    from codeagent.desktop.models import ModelAssets, OllamaEndpoint

    ep = OllamaEndpoint(base="http://192.168.3.23:8188", kind="comfy", id="c1")
    assets = ModelAssets(endpoints=[ep], active="local:sdxl@c1")
    assert assets.resolve_member("local:sdxl@c1") is None


def test_add_endpoint_8188_marks_comfy(api):
    r = api.add_endpoint("http://192.168.3.23:8188", label="3.23")
    assert r["ok"]
    assert r["kind"] == "comfy"
    ep = next(e for e in api.assets.endpoints if e.base.endswith(":8188"))
    assert ep.kind == "comfy"


def test_detect_requires_key_hint(monkeypatch):
    m = _patch_client(monkeypatch, {"/models": _FakeResp(401)})
    r = asyncio.run(m.detect_service("https://api.deepseek.com/v1"))
    assert r["kind"] == "unknown" and "API Key" in r["error"]


def test_detect_sends_bearer_key(monkeypatch):
    m = _patch_client(monkeypatch, {
        "/models": _FakeResp(200, {"data": [{"id": "deepseek-chat"}]}),
    })
    r = asyncio.run(m.detect_service("https://api.deepseek.com/v1", "sk-x"))
    assert r["kind"] == "openai" and r["models"] == ["deepseek-chat"]
    assert _FakeClient.seen[0][1]["Authorization"] == "Bearer sk-x"


def test_detect_bad_key_message(monkeypatch):
    m = _patch_client(monkeypatch, {"/models": _FakeResp(403)})
    r = asyncio.run(m.detect_service("https://api.x.com/v1", "bad"))
    assert "鉴权失败" in r["error"]


def test_detect_v1_fallback(monkeypatch):
    m = _patch_client(monkeypatch, {
        "/v1/models": _FakeResp(200, {"data": [{"id": "qwen-max"}]}),
    })
    # 用户填的是根域名，无 /v1
    r = asyncio.run(m.detect_service("https://dashscope.aliyuncs.com", "sk-x"))
    assert r["kind"] == "openai" and r["models"] == ["qwen-max"]


def test_detect_ollama_fallback(monkeypatch):
    m = _patch_client(monkeypatch, {
        "/api/tags": _FakeResp(200, {"models": [{"name": "qwen3:8b"}]}),
    })
    r = asyncio.run(m.detect_service("http://localhost:11434"))
    assert r["kind"] == "ollama" and r["models"] == ["qwen3:8b"]


def test_ui_detect_fills_model_dropdown():
    # 识别后模型填进下拉菜单供用户选择（不再是弹窗）
    assert "modelDialog" not in HTML
    assert '<select id="am_model"' in HTML
    assert "先点「自动识别」列出全部模型" in HTML
    assert "am_model_wrap" in HTML
    assert "请从下拉菜单选择" in HTML
    # 识别失败降级为手动输入框
    assert "模型名（手动填写）" in HTML


def test_detect_timeout_error_is_actionable(monkeypatch):
    import httpx
    m = _patch_client(monkeypatch, {"/models": httpx.ConnectTimeout("")})
    # ConnectTimeout 的 str() 为空，也必须给出可读提示
    r = asyncio.run(m.detect_service("https://openai.app.msh.team/v1", "sk-x"))
    assert r["kind"] == "unknown"
    assert "ConnectTimeout" in r["error"] and "VPN" in r["error"]


def test_detect_moonshot_alt_host_fallback(monkeypatch):
    # .cn 鉴权失败 → 自动用同一把 Key 重试 .ai，成功后回填新 base_url
    m = _patch_client(monkeypatch, {
        "api.moonshot.cn/v1/models": _FakeResp(401),
        "api.moonshot.ai/v1/models": _FakeResp(200, {"data": [{"id": "kimi-k2"}]}),
    })
    r = asyncio.run(m.detect_service("https://api.moonshot.cn/v1", "sk-x"))
    assert r["kind"] == "openai" and r["models"] == ["kimi-k2"]
    assert r["base_url"] == "https://api.moonshot.ai/v1"
    assert "已自动切换" in r["note"]


def test_detect_no_alt_fallback_without_key(monkeypatch):
    # 无 Key 的 401 不触发换站（应先提示填 Key）
    m = _patch_client(monkeypatch, {"/models": _FakeResp(401)})
    r = asyncio.run(m.detect_service("https://api.moonshot.cn/v1"))
    assert r["kind"] == "unknown" and "API Key" in r["error"]


# ---------------------------------------------------------------------------
# projects（项目工作区：文件夹 + 对话持久化）
# ---------------------------------------------------------------------------


def test_project_create_makes_folder(api, tmp_path):
    r = api.create_project("爬虫项目", str(tmp_path / "base"))
    assert r["ok"]
    folder = tmp_path / "base" / "爬虫项目"
    assert folder.is_dir()
    assert (folder / "project.json").is_file()
    assert (folder / "conversations").is_dir()
    assert (folder / "files").is_dir()
    # 工作根目录切到项目文件夹
    assert api.root == folder
    assert api.projects.active == r["project"]["id"]


def test_project_folder_name_dedup(api, tmp_path):
    api.create_project("重名", str(tmp_path / "b"))
    r2 = api.create_project("重名", str(tmp_path / "b"))
    assert (tmp_path / "b" / "重名-2").is_dir()
    assert r2["project"]["path"].endswith("重名-2")


def test_project_switch_changes_root(api, tmp_path):
    r1 = api.create_project("P1", str(tmp_path / "b"))
    r2 = api.create_project("P2", str(tmp_path / "b"))
    assert api.root.name == "P2"
    api.switch_project(r1["project"]["id"])
    assert api.root.name == "P1"
    assert api._conv_id is None  # 切换后开新对话


def fake_llm(monkeypatch):
    """让对话类测试用假 provider（确定性、不依赖真实模型）。"""
    from codeagent.core.types import LLMResponse

    class FakeProvider:
        name = "fake"
        model = "fake-model"

        async def complete(self, messages, tools=None, system=None, **kw):
            return LLMResponse(content="好，已记下。")

    monkeypatch.setattr("codeagent.desktop.api.parse_provider_spec",
                        lambda *a, **k: FakeProvider())


def test_project_delete_keeps_folder(api, tmp_path):
    r = api.create_project("保留我", str(tmp_path / "b"))
    folder = Path(r["project"]["path"])
    assert api.delete_project(r["project"]["id"]) is True
    assert folder.is_dir()  # 文件夹保留
    assert api.projects.get(r["project"]["id"]) is None


def test_conversation_persisted_in_project_folder(api, tmp_path, monkeypatch):
    fake_llm(monkeypatch)
    api.create_project("记录", str(tmp_path / "b"))
    api.send("你好，记住这句话")
    wait_for(api._window, "done")
    proj = api.projects.get(api.projects.active)
    convs = list((Path(proj.path) / "conversations").glob("*.jsonl"))
    assert len(convs) == 1
    content = convs[0].read_text(encoding="utf-8")
    assert "你好，记住这句话" in content
    # md 可读版同步生成
    md = convs[0].with_suffix(".md")
    assert md.is_file() and "🧑 用户" in md.read_text(encoding="utf-8")


def test_conversation_list_and_load(api, tmp_path, monkeypatch):
    fake_llm(monkeypatch)
    api.create_project("历史", str(tmp_path / "b"))
    api.send("第一条消息")
    wait_for(api._window, "done")
    items = api.get_conversations()["items"]
    assert len(items) == 1 and items[0]["count"] == 2
    assert "第一条消息" in items[0]["title"]
    r = api.load_conversation(items[0]["id"])
    assert r["ok"] and len(r["messages"]) == 2
    # 载入后续聊：下一条消息带前文上下文
    captured = {}
    orig = api._run_chat
    api._run_chat = lambda t, _recall="": (captured.setdefault("t", t),
                               setattr(api, "_busy", False))
    api.send("继续")
    assert "本会话之前的对话记录" in captured["t"]
    api._run_chat = orig


def test_new_conversation_starts_fresh(api, tmp_path, monkeypatch):
    fake_llm(monkeypatch)
    api.create_project("多对话", str(tmp_path / "b"))
    api.send("对话一")
    wait_for(api._window, "done")
    api.new_conversation()
    api.send("对话二")
    wait_for(api._window, "done")
    proj = api.projects.get(api.projects.active)
    convs = list((Path(proj.path) / "conversations").glob("*.jsonl"))
    assert len(convs) == 2  # 所有对话都保留


def test_ui_has_projects_surface():
    assert 'id="projectList"' in HTML
    assert 'id="projDialog"' in HTML
    assert 'id="convPicker"' in HTML and 'id="newConvBtn"' in HTML
    assert 'id="chatProjSel"' in HTML
    assert 'id="composerProj"' not in HTML
    assert "onChatProject" in HTML and "fillProjectSelects" in HTML
    assert "createProject" in HTML and "switchProject" in HTML
    assert "loadConv" in HTML
    assert 'id="page-project"' in HTML
    assert 'id="pj_cat"' not in HTML  # 侧栏不再按分类展示
    assert "lab.className='proj-cat'" not in HTML
    assert "optgroup" not in HTML
    assert "loadProjectRecords" in HTML
    assert "get_project_records" in HTML


def test_ui_mentions_project_export_import():
    assert "exportProject" in HTML and "importProject" in HTML
    assert "export_project" in HTML and "import_project" in HTML
    assert "replayConvMessages" in HTML
    assert "📥 导入项目" in HTML and "📤 导出项目" in HTML


def test_ui_project_base_disk_picker():
    assert "pickProjectBase" in HTML and "pick_project_base" in HTML
    assert 'id="pj_disks"' in HTML
    assert "disk_roots" in HTML or "setProjectBase" in HTML
    assert "选择…" in HTML


def test_project_category(api, tmp_path):
    r = api.create_project("官网", str(tmp_path / "b"), "工作")
    assert r["project"]["category"] == "工作"
    r2 = api.create_project("日记", str(tmp_path / "b"), "个人")
    assert r2["project"]["category"] == "个人"
    cats = {p["category"] for p in api.get_projects()["projects"]}
    assert cats == {"工作", "个人"}


def test_ensure_default_creates_folder(tmp_path, monkeypatch):
    from codeagent.desktop.projects import ProjectStore
    monkeypatch.setattr("codeagent.desktop.projects.DEFAULT_BASE", tmp_path / "base")
    monkeypatch.setattr("codeagent.desktop.projects.PROJECTS_INDEX", tmp_path / "idx.json")
    store = ProjectStore()
    proj = store.ensure_default()
    assert proj.name == "默认项目"
    assert Path(proj.path).is_dir()
    assert (Path(proj.path) / "files").is_dir()
    assert store.ensure_default().id == proj.id  # 不重复创建


def test_attachment_copied_into_project_files(api, tmp_path):
    api.create_project("附件箱", str(tmp_path / "b"))
    src = tmp_path / "需求.md"
    src.write_text("内容", encoding="utf-8")
    info = api._ingest_attachment(src)
    dest = Path(info["saved"])
    assert dest.is_file()
    assert dest.parent.name == "files"
    assert dest.read_text(encoding="utf-8") == "内容"
    rec = api.get_project_records()
    assert rec["ok"] and any(f["name"] == "需求.md" for f in rec["files"])


def test_project_records_lists_conversations(api, tmp_path):
    from codeagent.desktop.projects import append_message

    api.create_project("记录页", str(tmp_path / "b"), "学习")
    proj = api.projects.get(api.projects.active)
    api._conv_id = "20260902-test-1"
    append_message(proj, api._conv_id, "user", "今天学了什么")
    append_message(proj, api._conv_id, "assistant", "学了项目分类")
    rec = api.get_project_records()
    assert rec["ok"] and rec["project"]["name"] == "记录页"
    assert rec["conversations"] and "今天学了什么" in rec["conversations"][0]["title"]
    assert rec["conversations"][0]["count"] == 2


def test_desktop_api_knowledge(api, tmp_path, monkeypatch):
    monkeypatch.setattr("codeagent.knowledge.CONFIG_PATH", tmp_path / "knowledge.json")
    root = tmp_path / "vault"
    r = api.save_knowledge_config(str(root), "local", "obsidian", True)
    assert r["ok"]
    boot = api.bootstrap_knowledge()
    assert boot["ok"] and boot["status"]["ready"]
    assert api.search_knowledge("overview")
    assert api.ingest_knowledge("笔记", "跨电脑共享测试")["ok"]
    d = api.get_knowledge()
    assert d["status"]["ready"] and d["config"]["path"] == str(root)


def test_desktop_api_video_ops(api, tmp_path, monkeypatch):
    monkeypatch.setattr("codeagent.videoops.CONFIG_PATH", tmp_path / "videoops.json")
    monkeypatch.setattr("codeagent.videoops.SKILLS_DIR", tmp_path / "skills")
    root = tmp_path / "video-ws"
    r = api.save_video_ops_config(str(root), True)
    assert r["ok"]
    boot = api.bootstrap_video_ops()
    assert boot["ok"] and boot["status"]["ready"]
    assert "short-drama-script" in boot["skills_installed"]
    draft = api.save_video_ops_draft("标题", "简介", "tag1", "/tmp/a.mp4", "")
    assert draft["ok"]
    d = api.get_video_ops()
    assert d["status"]["draft"]["title"] == "标题"
    names = {s["name"] for s in d["skills"]}
    assert "libtv-generate" in names
    assert "wan-gradio" in names

    async def fake_probe(base, timeout=4.0):
        return {"title": "WAN-1.3B 文生视频", "version": "6.26.0",
                "endpoints": ["/generate_video"]}

    monkeypatch.setattr("codeagent.videoops.gradio.probe_gradio_app", fake_probe)
    r2 = api.save_video_ops_config(str(root), True, "http://192.168.3.23:7860")
    assert r2["gradio"]["online"] and "WAN" in r2["gradio"]["title"]
    assert r2["ok"]
    assert r2["config"]["gradio_base"] == "http://192.168.3.23:7860"
    bases = [e.base for e in api.assets.endpoints]
    assert "http://192.168.3.23:7860" in bases
    kind = next(e.kind for e in api.assets.endpoints if e.base.endswith(":7860"))
    assert kind == "gradio"


# ---------------------------------------------------------------------------
# 第二对话进程（B）：同一项目可并行两个对话
# ---------------------------------------------------------------------------


def test_send2_pushes_events_on_channel_b(api, monkeypatch):
    from codeagent.core.types import LLMResponse

    class FakeProvider:
        name = "fake"
        model = "fake-model"

        async def complete(self, messages, tools=None, system=None, **kw):
            return LLMResponse(content="B 的回复")

    monkeypatch.setattr(
        "codeagent.desktop.api.parse_provider_spec",
        lambda *a, **k: FakeProvider(),
    )
    assert api.send2("B 你好") is True
    done = wait_for(api._window, "done")
    assert done["text"] == "B 的回复"
    assert done["chan"] == "B"


def test_dual_conversations_run_concurrently(api, monkeypatch):
    from codeagent.core.types import LLMResponse

    class SlowProvider:
        name = "slow"
        model = "slow"

        async def complete(self, messages, tools=None, system=None, **kw):
            await asyncio.sleep(30)
            return LLMResponse(content="finish")

    monkeypatch.setattr(
        "codeagent.desktop.api.parse_provider_spec",
        lambda *a, **k: SlowProvider(),
    )
    assert api.send("A 长回复") is True
    assert api.send2("B 长回复") is True
    # 两个进程独立忙碌，互不阻塞
    assert api._busy is True and api._busy2 is True
    # 分别中断各自进程
    assert api.stop2() is True
    ev = wait_for(api._window, "stopped")
    assert ev["chan"] == "B"
    assert api._busy2 is False
    assert api._busy is True  # A 仍在运行
    assert api.stop() is True


def test_second_conversation_management(api, tmp_path):
    # 新对话 B 重置进程状态
    api._conv_id2 = "20260908-test-b"
    api.new_conversation2()
    assert api._conv_id2 is None
    st = api.get_second_state()
    assert st["busy"] is False and st["current"] == ""

    # 载入历史对话 B
    from codeagent.desktop.projects import append_message, load_conversation

    api.create_project("B 项目", str(tmp_path / "b"), "学习")
    proj = api.projects.get(api.projects.active)
    cid = "20260908-test-b2"
    append_message(proj, cid, "user", "B 历史问题")
    append_message(proj, cid, "assistant", "B 历史回答")
    r = api.load_conversation2(cid)
    assert r["ok"] is True and len(r["messages"]) == 2
    assert api._conv_id2 == cid

    # reset2 清理第二 agent
    class StubAgent:
        reset_called = False

        def reset(self):
            self.reset_called = True

    api._agent2 = StubAgent()
    assert api.reset2() is True
    assert api._agent2 is None

    # resolve_confirm2 走独立确认器
    assert api.resolve_confirm2("nonexistent", True) is False


def test_ui_dual_chat_markup():
    # 双对话：页眉切换按钮 + B 列（chatColB / inputB / sendBtnB / 停止）
    assert 'id="dualBtn"' in HTML
    assert 'id="colB"' in HTML and 'id="chatColB"' in HTML
    assert 'id="inputB"' in HTML and 'id="sendBtnB"' in HTML and 'id="stopBtnB"' in HTML
    assert 'id="convPickerB"' in HTML and 'id="newConvBtnB"' in HTML
    assert 'id="copyChatBtnB"' in HTML
    assert "sendChatB" in HTML and "stopChatB" in HTML
    assert "loadConv2" in HTML and "loadConversations2" in HTML and "newChatB" in HTML
    assert "pywebview.api.send2" in HTML and "pywebview.api.stop2" in HTML
    assert "pywebview.api.read_clipboard" in HTML  # 右键粘贴回退
    assert "ev.chan" in HTML  # 事件按对话进程分流


def test_ui_second_window_markup():
    # 独立对话窗口（B）：chat-only 页面复用主样式
    from codeagent.desktop.ui import CHAT_HTML

    assert 'id="chatColB"' in CHAT_HTML and 'id="inputB"' in CHAT_HTML
    assert 'id="sendBtnB"' in CHAT_HTML and 'id="stopBtnB"' in CHAT_HTML
    assert 'id="convPickerB"' in CHAT_HTML and 'id="newConvBtnB"' in CHAT_HTML
    assert 'id="copyChatBtnB"' in CHAT_HTML
    assert "pywebview.api.send2" in CHAT_HTML and "pywebview.api.stop2" in CHAT_HTML
    assert "pywebview.api.read_clipboard" in CHAT_HTML  # 右键粘贴回退
    assert "_ctxSel" in CHAT_HTML and "WKWebView 需打开 DOMPasteAllowed" in CHAT_HTML
    assert "speakText" in CHAT_HTML and "replayLast" in CHAT_HTML
    assert 'id="stopSpeakToolB"' in CHAT_HTML and "停止播报" in CHAT_HTML
    assert "stopSpeak()" in CHAT_HTML
    assert "⏹ 停止播报" in CHAT_HTML
    assert "resolve_confirm2" in CHAT_HTML  # B 通道工具确认
    assert "window._onEvent" in CHAT_HTML and "ev.chan" in CHAT_HTML
    assert "pywebview.api.open_second_window" in HTML  # 主窗口「新窗口」按钮


def test_push_b_routes_to_second_window(api):
    # B 事件同时推给主窗口与独立对话窗口，A 只推主窗口
    win_b = FakeWindow()
    api._window_b = win_b
    api._push("text", chan="B", text="独立窗口内容")
    assert len(api._window.calls) == 1 and len(win_b.calls) == 1
    assert win_b.calls[0]["chan"] == "B" and win_b.calls[0]["text"] == "独立窗口内容"
    api._push("tool", chan="A", name="shell")
    assert len(api._window.calls) == 2 and len(win_b.calls) == 1


def test_voice_push_does_not_require_blocking_evaluate_js(api):
    """Recognition callbacks must use fire-and-forget push (no semaphore wait)."""
    api._push("voice", state="partial", text="你好")
    api._push("voice", state="heard", text="你好世界")
    voice = [c for c in api._window.calls if c.get("kind") == "voice"]
    assert [c["state"] for c in voice] == ["partial", "heard"]
    assert hasattr(api, "_eval_js_fire_and_forget")


def test_open_second_window_safe(api):
    # 未启动 webview 时也能安全返回（后台线程捕获 ImportError）
    r = api.open_second_window()
    assert r["ok"] is True and r["opened"] is True
    # 重复调用：_window_b 尚未被线程写入，仍返回可创建
    r2 = api.open_second_window()
    assert r2["ok"] is True


def test_assets_probe_cache_avoids_repeat(api, monkeypatch):
    # 对话页来回切换不应反复全量探测模型
    calls = {"n": 0}

    async def fake_probe_all(endpoints):
        calls["n"] += 1
        return {"endpoints": [
            {"id": e.id, "base": e.base, "ok": False, "kind": "", "models": []}
            for e in endpoints
        ]}

    monkeypatch.setattr("codeagent.desktop.api.probe_all", fake_probe_all)
    api.get_model_assets()
    api.get_model_assets()  # TTL 内命中缓存，不再探测
    assert calls["n"] == 1
    # 增删端点会失效缓存，下次调用重新探测
    api.add_endpoint("http://192.168.9.9:11434", label="缓存测试")
    api.get_model_assets()
    assert calls["n"] == 2


def test_set_dual_mode_resizes_window(api):
    # 开启双对话：窗口加宽 1.5 倍；关闭还原
    class ResizableWindow:
        initial_width = 1280
        initial_height = 840
        calls = []

        def resize(self, width, height):
            self.calls.append((width, height))

    w = ResizableWindow()
    api._window = w
    assert api.set_dual_mode(True) is True
    assert w.calls[-1] == (1920, 840)  # 1280 * 1.5
    assert api.set_dual_mode(False) is True
    assert w.calls[-1] == (1280, 840)
    # 无窗口时安全返回
    api._window = None
    assert api.set_dual_mode(True) is False


def test_ui_dual_markup_has_resize_call():
    from codeagent.desktop.ui import HTML

    assert "set_dual_mode" in HTML  # 双对话切换时联动窗口缩放
