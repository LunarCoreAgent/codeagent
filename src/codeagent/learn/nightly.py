"""Night study: 02:00–06:00 read each project, research, store locally."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

from codeagent.desktop.activity import log_activity
from codeagent.learn.collect import (
    ProjectCorpus,
    build_queries,
    collect_project,
    projects_with_conversations,
)
from codeagent.learn.research import WebHit, research_query
from codeagent.learn.store import LearnedNote, LearnedStore

STATE_PATH = Path("~/.codeagent/night_learn.json").expanduser()
START_HOUR = 2
END_HOUR = 6
MAX_NOTES_PER_PROJECT = 8


@dataclass
class NightLearnSettings:
    """User must turn this on in 自我学习; default is off."""

    enabled: bool = False
    start_hour: int = START_HOUR
    end_hour: int = END_HOUR
    web_enabled: bool = True


@dataclass
class NightLearnState:
    settings: NightLearnSettings = field(default_factory=NightLearnSettings)
    last_date: str = ""
    status: str = "idle"  # idle | running | done | partial
    cursor: int = 0
    last_summary: str = ""
    notes_today: int = 0
    done_ids: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path | None = None) -> "NightLearnState":
        path = Path(path or STATE_PATH).expanduser()
        if not path.is_file():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return cls()
        raw = data.get("settings") if isinstance(data.get("settings"), dict) else {}
        known = set(NightLearnSettings.__dataclass_fields__)
        settings = NightLearnSettings(**{k: v for k, v in raw.items() if k in known})
        done = data.get("done_ids") if isinstance(data.get("done_ids"), list) else []
        return cls(
            settings=settings,
            last_date=str(data.get("last_date") or ""),
            status=str(data.get("status") or "idle"),
            cursor=int(data.get("cursor") or 0),
            last_summary=str(data.get("last_summary") or ""),
            notes_today=int(data.get("notes_today") or 0),
            done_ids=[str(x) for x in done if str(x).strip()],
        )

    def save(self, path: Path | None = None) -> None:
        path = Path(path or STATE_PATH).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({
                "settings": asdict(self.settings),
                "last_date": self.last_date,
                "status": self.status,
                "cursor": self.cursor,
                "last_summary": self.last_summary,
                "notes_today": self.notes_today,
                "done_ids": list(self.done_ids),
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def in_night_window(
    tm: time.struct_time | None = None,
    start_hour: int = START_HOUR,
    end_hour: int = END_HOUR,
) -> bool:
    """True during [start, end) local time. Default 02:00–06:00."""
    stamp = tm or time.localtime()
    start = max(0, min(23, int(start_hour)))
    end = max(1, min(24, int(end_hour)))
    if start == end:
        return False
    if start < end:
        return start <= stamp.tm_hour < end
    return stamp.tm_hour >= start or stamp.tm_hour < end


def window_deadline(now: float | None = None, end_hour: int = END_HOUR) -> float:
    stamp = time.localtime(now or time.time())
    end = max(1, min(24, int(end_hour)))
    base = time.mktime((
        stamp.tm_year, stamp.tm_mon, stamp.tm_mday,
        end, 0, 0, 0, 0, stamp.tm_isdst,
    ))
    current = now or time.time()
    if base <= current:
        base += 24 * 3600
    return base


def _heuristic_notes(corpus: ProjectCorpus, hits: list[WebHit]) -> list[LearnedNote]:
    notes: list[LearnedNote] = []
    if corpus.chats or corpus.thinking or corpus.code:
        notes.append(LearnedNote(
            id="",
            project_id=corpus.project_id,
            project_name=corpus.project_name,
            kind="tech",
            title=f"{corpus.project_name} 项目阅读摘要",
            content=(
                f"语言：{', '.join(corpus.languages) or '未识别'}。"
                f"主题：{', '.join(corpus.topics[:6])}。"
                f"对话要点：{(corpus.chats or '无')[:360]}"
                + (f" 思考：{corpus.thinking[:240]}" if corpus.thinking else "")
            ),
            query="项目阅读",
        ))
    if corpus.code:
        notes.append(LearnedNote(
            id="",
            project_id=corpus.project_id,
            project_name=corpus.project_name,
            kind="code",
            title=f"{corpus.project_name} 代码结构",
            content="主要文件： " + "、".join(corpus.files[:12]) + "\n" + corpus.code[:700],
            query="代码",
        ))
    for hit in hits:
        snippet = (hit.snippet or "").strip()
        if len(snippet) < 80:
            continue
        notes.append(LearnedNote(
            id="",
            project_id=corpus.project_id,
            project_name=corpus.project_name,
            kind=hit.kind,
            title=hit.title or hit.query,
            content=snippet[:900],
            source_url=hit.url,
            query=hit.query,
        ))
    return notes[:MAX_NOTES_PER_PROJECT]


def _parse_llm_notes(raw: str, corpus: ProjectCorpus) -> list[LearnedNote]:
    text = (raw or "").strip()
    if not text:
        return []
    start, end = text.find("["), text.rfind("]")
    if start < 0 or end <= start:
        return []
    try:
        payload = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return []
    notes: list[LearnedNote] = []
    if not isinstance(payload, list):
        return []
    for item in payload[:MAX_NOTES_PER_PROJECT]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        content = str(item.get("content") or "").strip()
        if not title or not content:
            continue
        notes.append(LearnedNote(
            id="",
            project_id=corpus.project_id,
            project_name=corpus.project_name,
            kind=str(item.get("kind") or "tech"),
            title=title,
            content=content[:1200],
            source_url=str(item.get("source_url") or ""),
            query=str(item.get("query") or "夜间分析"),
        ))
    return notes


def distill_notes(
    corpus: ProjectCorpus,
    hits: list[WebHit],
    chat_fn: Callable[[str], str] | None = None,
) -> list[LearnedNote]:
    fallback = _heuristic_notes(corpus, hits)
    if chat_fn is None:
        return fallback
    web_block = "\n\n".join(
        f"### {h.title}\n种类：{h.kind}\n网址：{h.url}\n{h.snippet[:1200]}"
        for h in hits[:6]
    ) or "（今晚未能取到网页，只根据本项目材料整理）"
    prompt = (
        "你是 CodeCoreAgent 的夜间自学。阅读本项目对话、思考过程、代码，"
        "以及网上检索到的资料，整理成可检索的短知识。"
        "覆盖：代码、设计、UI 设计、流程设计、数据库设计、技术。"
        "只输出 JSON 数组，每项："
        '{"kind":"code|design|ui|flow|database|tech","title":"...","content":"...","source_url":"","query":"..."}'
        " content 用中文，具体、可执行，不要空话。最多 6 条。\n\n"
        f"{corpus.digest()}\n\n网上资料：\n{web_block}"
    )
    try:
        parsed = _parse_llm_notes(chat_fn(prompt), corpus)
    except Exception:  # noqa: BLE001
        parsed = []
    return parsed or fallback


def study_project(
    project: Any,
    *,
    store: LearnedStore,
    memory_writer: Callable[[LearnedNote], None] | None = None,
    chat_fn: Callable[[str], str] | None = None,
    fetch: Callable[[str], str] | None = None,
    web_enabled: bool = True,
    deadline: float | None = None,
) -> dict[str, Any]:
    """Read one project, optionally research the web, persist notes."""
    if deadline and time.time() >= deadline:
        return {"ok": False, "skipped": True, "reason": "window_closed"}
    corpus = collect_project(project)
    hits: list[WebHit] = []
    if web_enabled:
        for kind, query in build_queries(corpus):
            if deadline and time.time() >= deadline:
                break
            hits.extend(research_query(kind, query, fetch=fetch, max_pages=1))
    notes = distill_notes(corpus, hits, chat_fn=chat_fn)
    saved = 0
    for note in notes:
        if deadline and time.time() >= deadline:
            break
        added = store.add(note)
        if added is None:
            continue
        saved += 1
        if memory_writer is not None:
            try:
                memory_writer(added)
            except Exception:  # noqa: BLE001
                pass
    return {
        "ok": True,
        "project_id": corpus.project_id,
        "project_name": corpus.project_name,
        "notes": saved,
        "queries": len(hits),
        "files": len(corpus.files),
    }


def run_night_learn(
    projects: list[Any],
    *,
    state: NightLearnState | None = None,
    state_path: Path | None = None,
    db_path: Path | None = None,
    memory_writer: Callable[[LearnedNote], None] | None = None,
    chat_fn: Callable[[str], str] | None = None,
    fetch: Callable[[str], str] | None = None,
    now: float | None = None,
    deadline: float | None = None,
    manual: bool = False,
    reset_day: bool = False,
) -> dict[str, Any]:
    """Study remaining projects until 06:00 (or until the list ends)."""
    path = Path(state_path or STATE_PATH).expanduser()
    state = state or NightLearnState.load(path)
    today = time.strftime("%Y-%m-%d", time.localtime(now or time.time()))
    if reset_day or state.last_date != today:
        state.cursor = 0
        state.notes_today = 0
        state.status = "idle"
        state.last_date = today
        state.done_ids = []
    # 自动调度：当天已完成则不再重复开跑（否则每 30 秒会再触发）
    if not manual and state.status == "done" and state.last_date == today:
        return {
            "ok": True,
            "status": "done",
            "skipped": True,
            "results": [],
            **_stats(state, LearnedStore(db_path)),
        }
    if not manual and not state.settings.enabled:
        return {"ok": False, "error": "夜间自学已关闭"}
    if deadline is None and not manual:
        deadline = window_deadline(now, state.settings.end_hour)
    store = LearnedStore(db_path)
    eligible = projects_with_conversations(list(projects or []))
    done = set(state.done_ids)
    items = [
        p for p in eligible
        if str(getattr(p, "id", "") or "") not in done
    ]
    state.status = "running"
    state.save(path)
    log_activity(
        "learn",
        f"夜间自学开始：复盘 {len(items)} 个待学项目"
        f"（有对话 {len(eligible)}）"
        + ("（手动）" if manual else ""),
    )
    results: list[dict[str, Any]] = []
    if not items:
        state.status = "done"
        if not eligible:
            state.last_summary = "没有可复盘的项目：请先在项目里产生对话"
        else:
            state.last_summary = (
                f"夜间自学完成：今日已覆盖 {len(eligible)} 个有对话项目"
            )
        state.save(path)
        log_activity("learn", state.last_summary)
        return {"ok": True, "status": "done", "results": [], **_stats(state, store)}
    index = 0
    while index < len(items):
        if deadline and time.time() >= deadline:
            state.status = "partial"
            state.cursor = len(state.done_ids)
            state.last_summary = (
                f"窗口结束，已学 {len(state.done_ids)}/{len(eligible)} 个项目"
            )
            state.save(path)
            log_activity("learn", state.last_summary)
            return {"ok": True, "status": "partial", "results": results, **_stats(state, store)}
        project = items[index]
        info = study_project(
            project,
            store=store,
            memory_writer=memory_writer,
            chat_fn=chat_fn,
            fetch=fetch,
            web_enabled=state.settings.web_enabled,
            deadline=deadline,
        )
        results.append(info)
        pid = str(getattr(project, "id", "") or info.get("project_id") or "")
        # 窗口内跳过不算完成，留待下一轮续跑
        if info.get("skipped") and info.get("reason") == "window_closed":
            state.status = "partial"
            state.cursor = len(state.done_ids)
            state.last_summary = (
                f"窗口结束，已学 {len(state.done_ids)}/{len(eligible)} 个项目"
            )
            state.save(path)
            log_activity("learn", state.last_summary)
            return {"ok": True, "status": "partial", "results": results, **_stats(state, store)}
        if pid and pid not in state.done_ids:
            state.done_ids.append(pid)
        if info.get("ok"):
            state.notes_today += int(info.get("notes") or 0)
        index += 1
        state.cursor = len(state.done_ids)
        state.save(path)
    state.status = "done"
    state.last_summary = (
        f"夜间自学完成：{len(eligible)} 个项目，新写入 {state.notes_today} 条知识"
    )
    state.save(path)
    log_activity("learn", state.last_summary)
    return {"ok": True, "status": "done", "results": results, **_stats(state, store)}


def _stats(state: NightLearnState, store: LearnedStore) -> dict[str, Any]:
    return {
        "notes_today": state.notes_today,
        "total": store.count(),
        "summary": state.last_summary,
        "cursor": state.cursor,
    }
