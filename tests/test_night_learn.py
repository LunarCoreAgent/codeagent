"""Night study: collect project corpus, store notes, retrieve on task."""

from __future__ import annotations

import time
from pathlib import Path

from codeagent.core.agent import Agent
from codeagent.core.types import LLMResponse
from codeagent.desktop.projects import Project, append_event
from codeagent.learn.collect import build_queries, collect_project
from codeagent.learn.nightly import (
    NightLearnState,
    in_night_window,
    run_night_learn,
    study_project,
)
from codeagent.learn.research import _safe_url, search_web
from codeagent.learn.store import LearnedNote, LearnedStore, recall_learned
from codeagent.llm.base import LLMProvider
from codeagent.memory.store import LocalMemoryStore


class FakeProvider(LLMProvider):
    name = "fake"

    def __init__(self, replies: list[str]) -> None:
        super().__init__(model="fake")
        self.replies = list(replies)
        self.seen_system_prompts: list[str] = []

    async def complete(self, messages, tools=None, system=None, **kwargs):
        self.seen_system_prompts.append(system or "")
        text = self.replies.pop(0) if self.replies else "ok"
        return LLMResponse(content=text)


def _project(tmp_path: Path, name: str = "相册") -> Project:
    root = tmp_path / name
    root.mkdir(parents=True, exist_ok=True)
    (root / "app.py").write_text(
        "def gallery():\n    return 'sqlite schema users'\n",
        encoding="utf-8",
    )
    proj = Project(name=name, path=str(root), id="p1")
    append_event(proj, "c1", "user", text="把相册首页做得更好看，数据库用 SQLite")
    append_event(proj, "c1", "thinking", text="先看现有 UI 组件和表结构")
    append_event(proj, "c1", "assistant", text="准备改布局并补 users 表")
    return proj


def test_collect_reads_chat_thinking_and_code(tmp_path: Path):
    proj = _project(tmp_path)
    corpus = collect_project(proj)
    assert "更好看" in corpus.chats
    assert "UI 组件" in corpus.thinking
    assert "gallery" in corpus.code
    assert "Python" in corpus.languages
    kinds = [k for k, _ in build_queries(corpus)]
    assert "ui" in kinds and "database" in kinds and "code" in kinds


def test_learned_store_dedup_and_search(tmp_path: Path):
    store = LearnedStore(tmp_path / "codecore.sqlite")
    note = LearnedNote(
        id="",
        project_id="p1",
        project_name="相册",
        kind="ui",
        title="相册首页卡片布局",
        content="列表用卡片网格，主色留白，按钮放右下角。",
        query="相册 UI",
    )
    assert store.add(note) is not None
    assert store.add(note) is None
    assert store.count("p1") == 1
    hits = store.search("卡片 布局", project_id="p1")
    assert hits and hits[0].title == "相册首页卡片布局"
    texts = recall_learned("卡片", project_id="p1", path=tmp_path / "codecore.sqlite")
    assert texts and "UI 设计" in texts[0]


def test_collect_skips_empty_and_keeps_chatted(tmp_path: Path):
    from codeagent.learn.collect import projects_with_conversations

    empty = Project(name="空", path=str(tmp_path / "empty"), id="e1")
    (tmp_path / "empty").mkdir()
    chatted = _project(tmp_path / "with", "有对话")
    chatted.id = "p2"
    kept = projects_with_conversations([empty, chatted])
    assert [p.id for p in kept] == [chatted.id]


def test_run_night_learn_skips_empty_projects(tmp_path: Path):
    empty_root = tmp_path / "空壳"
    empty_root.mkdir()
    empty = Project(name="空壳", path=str(empty_root), id="e0")
    chatted = _project(tmp_path, "相册")
    state = NightLearnState()
    state.settings.web_enabled = False
    result = run_night_learn(
        [empty, chatted],
        state=state,
        state_path=tmp_path / "night_learn.json",
        db_path=tmp_path / "codecore.sqlite",
        manual=True,
        reset_day=True,
    )
    assert result["ok"] and result["status"] == "done"
    assert result["notes_today"] >= 1
    names = [r.get("project_name") for r in result["results"]]
    assert "相册" in names
    assert "空壳" not in names


def test_night_window_hours():
    inside = time.struct_time((2026, 9, 22, 3, 10, 0, 1, 265, 0))
    edge = time.struct_time((2026, 9, 22, 2, 0, 0, 1, 265, 0))
    closed = time.struct_time((2026, 9, 22, 6, 0, 0, 1, 265, 0))
    day = time.struct_time((2026, 9, 22, 14, 0, 0, 1, 265, 0))
    assert in_night_window(inside)
    assert in_night_window(edge)
    assert not in_night_window(closed)
    assert not in_night_window(day)


def test_study_project_without_web(tmp_path: Path):
    proj = _project(tmp_path)
    store = LearnedStore(tmp_path / "codecore.sqlite")
    result = study_project(proj, store=store, web_enabled=False)
    assert result["ok"] and result["notes"] >= 1
    assert store.count("p1") >= 1


def test_run_night_learn_persists_and_recalls(tmp_path: Path):
    proj = _project(tmp_path)
    pages = {
        "https://html.duckduckgo.com/html/?q=x": (
            '<a class="result__a" href="https://example.com/ui">相册 UI 指南</a>'
        ),
        "https://lite.duckduckgo.com/lite/?q=x": "",
        "https://example.com/ui": "<html><body><p>卡片网格和留白让相册更好看。</p></body></html>",
    }

    def fake_fetch(url: str) -> str:
        for key, body in pages.items():
            if url.startswith(key.split("?")[0]) or url == key:
                return body
        if "example.com/ui" in url:
            return pages["https://example.com/ui"]
        if "duckduckgo.com/html" in url:
            return pages["https://html.duckduckgo.com/html/?q=x"]
        return ""

    state = NightLearnState()
    state.settings.web_enabled = True
    result = run_night_learn(
        [proj],
        state=state,
        state_path=tmp_path / "night_learn.json",
        db_path=tmp_path / "codecore.sqlite",
        fetch=fake_fetch,
        manual=True,
        reset_day=True,
    )
    assert result["ok"] and result["status"] == "done"
    assert result["notes_today"] >= 1
    notes = recall_learned("相册", project_id="p1", path=tmp_path / "codecore.sqlite")
    assert notes


def test_search_web_rejects_localhost():
    assert _safe_url("http://127.0.0.1/secret") == ""
    assert _safe_url("http://192.168.1.8/docs") == ""
    assert _safe_url("https://example.com/a") == "https://example.com/a"

    html = '<a class="result__a" href="https://docs.example.com/x">文档</a>'
    hits = search_web("docs", fetch=lambda url: html)
    assert hits and hits[0][0] == "https://docs.example.com/x"


async def test_agent_injects_learned_knowledge(tmp_path: Path):
    store = LocalMemoryStore(tmp_path / "mem.json")
    await store.add(
        "【UI 设计】相册首页用卡片网格",
        {"kind": "learned_ui", "source": "night-learn"},
    )
    provider = FakeProvider(["ok"])
    agent = Agent(provider=provider, memory=store, system_prompt="BASE")
    agent.recall_learned = lambda q: ["【数据库设计】users 表存相册路径"]
    await agent.run("把相册首页做得更好看，并设计数据库")
    prompt = provider.seen_system_prompts[0]
    assert "夜间自学知识" in prompt
    assert "卡片网格" in prompt
    assert "本机记忆库检索" in prompt
    assert "users 表" in prompt


async def test_agent_injects_sqlite_when_memory_has_no_hits(tmp_path: Path):
    store = LocalMemoryStore(tmp_path / "mem.json")
    await store.add("无关的旧进度", {"kind": "progress"})
    provider = FakeProvider(["ok"])
    agent = Agent(provider=provider, memory=store, system_prompt="BASE")
    agent.recall_learned = lambda q: ["【UI 设计】卡片网格布局"]
    await agent.run("zzzzz unrelated query")
    prompt = provider.seen_system_prompts[0]
    assert "本机记忆库检索" in prompt
    assert "卡片网格" in prompt


def test_auto_night_learn_skips_when_already_done(tmp_path: Path):
    proj = _project(tmp_path)
    state = NightLearnState()
    state.settings.web_enabled = False
    state.settings.enabled = True
    first = run_night_learn(
        [proj],
        state=state,
        state_path=tmp_path / "night_learn.json",
        db_path=tmp_path / "codecore.sqlite",
        manual=False,
        reset_day=True,
    )
    assert first["ok"] and first["status"] == "done"
    second = run_night_learn(
        [proj],
        state=NightLearnState.load(tmp_path / "night_learn.json"),
        state_path=tmp_path / "night_learn.json",
        db_path=tmp_path / "codecore.sqlite",
        manual=False,
    )
    assert second.get("skipped") is True
    assert second["status"] == "done"


def test_night_learn_resumes_by_project_id(tmp_path: Path):
    a = _project(tmp_path, "甲")
    a.id = "a1"
    b = _project(tmp_path, "乙")
    b.id = "b1"
    state = NightLearnState()
    state.settings.web_enabled = False
    state.settings.enabled = True
    state.last_date = time.strftime("%Y-%m-%d")
    state.done_ids = ["a1"]
    state.status = "partial"
    result = run_night_learn(
        [a, b],
        state=state,
        state_path=tmp_path / "night_learn.json",
        db_path=tmp_path / "codecore.sqlite",
        manual=False,
    )
    assert result["ok"]
    names = [r.get("project_name") for r in result["results"]]
    assert "乙" in names
    assert "甲" not in names
    assert "b1" in NightLearnState.load(tmp_path / "night_learn.json").done_ids


def test_scheduler_night_learn_only_in_window(tmp_path: Path):
    from codeagent.desktop.cron import CronScheduler, CronStore

    fired: list[str] = []
    sched = CronScheduler(
        CronStore(),
        run_action=lambda job: True,
        night_learn_enabled=lambda: True,
        run_night_learn=lambda: fired.append("night"),
    )
    night = time.mktime((2026, 9, 22, 3, 15, 0, 0, 0, -1))
    day = time.mktime((2026, 9, 22, 15, 15, 0, 0, 0, -1))
    assert sched.maybe_night_learn(now=night) is True
    if sched._night_thread:
        sched._night_thread.join(timeout=2)
    assert fired == ["night"]
    assert sched.maybe_night_learn(now=day) is False
