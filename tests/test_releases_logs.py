"""Version history (releases) and persistent run logging."""

from __future__ import annotations

import logging

import codeagent
from codeagent import RELEASES, changelog_text, latest
from codeagent.log import get_logger, setup_logging, tail_log


# ---------------------------------------------------------------------------
# releases
# ---------------------------------------------------------------------------


def test_latest_release_matches_package_version():
    assert latest().version == codeagent.__version__


def test_releases_are_ordered_and_unique():
    versions = [r.version for r in RELEASES]
    assert len(versions) == len(set(versions))
    assert versions == sorted(versions, key=lambda v: [int(x) for x in v.split(".")])


def test_every_release_has_date_and_highlights():
    for release in RELEASES:
        assert release.date
        assert release.highlights


def test_changelog_text_covers_all_versions():
    text = changelog_text()
    for release in RELEASES:
        assert release.version in text


# ---------------------------------------------------------------------------
# logging
# ---------------------------------------------------------------------------


def test_setup_logging_writes_records(tmp_path, monkeypatch):
    monkeypatch.setattr("codeagent.log._configured", False)
    log_file = tmp_path / "codeagent.log"
    path = setup_logging(log_file=log_file)
    assert path == log_file

    get_logger("test").info("hello-log-记录")
    for handler in logging.getLogger("codeagent").handlers:
        handler.flush()

    entries = tail_log(10, log_file=log_file)
    assert any("hello-log-记录" in line for line in entries)


def test_setup_logging_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr("codeagent.log._configured", False)
    setup_logging(log_file=tmp_path / "a.log")
    logger = logging.getLogger("codeagent")
    n_handlers = len(logger.handlers)
    setup_logging(log_file=tmp_path / "b.log")  # second call must not duplicate
    assert len(logger.handlers) == n_handlers


def test_tail_log_missing_file(tmp_path):
    assert tail_log(5, log_file=tmp_path / "nope.log") == []


def test_agent_run_emits_log_records(tmp_path, monkeypatch):
    import asyncio

    from codeagent import Agent
    from codeagent.core.types import LLMResponse
    from codeagent.llm.base import LLMProvider

    monkeypatch.setattr("codeagent.log._configured", False)
    log_file = tmp_path / "codeagent.log"
    setup_logging(log_file=log_file)

    class P(LLMProvider):
        name = "p"

        async def complete(self, messages, tools=None, system=None, **kw):
            return LLMResponse(content="done")

    asyncio.run(Agent(provider=P(model="m")).run("测试任务"))
    for handler in logging.getLogger("codeagent").handlers:
        handler.flush()

    entries = tail_log(20, log_file=log_file)
    assert any("run start" in line and "测试任务" in line for line in entries)
    assert any("run done" in line for line in entries)
