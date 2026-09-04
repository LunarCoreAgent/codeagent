"""Tests for CodeCoreAgent knowledge vault (Obsidian / LLM Wiki)."""

from __future__ import annotations

from pathlib import Path

from codeagent.desktop.ui import HTML
from codeagent.knowledge import (
    KnowledgeConfig,
    bootstrap_vault,
    ingest_text,
    is_vault_ready,
    list_pages,
    read_page,
    vault_status,
)
from codeagent.knowledge.tools import knowledge_tools


def test_bootstrap_creates_llm_wiki_layout(tmp_path):
    root = tmp_path / "wiki"
    r = bootstrap_vault(root)
    assert r["ok"] and r["ready"]
    assert is_vault_ready(root)
    assert (root / "AGENTS.md").is_file()
    assert (root / "wiki" / "index.md").is_file()
    assert (root / "wiki" / "overview.md").is_file()
    assert (root / "raw" / "inbox").is_dir()
    assert (root / ".obsidian" / "app.json").is_file()
    # idempotent
    r2 = bootstrap_vault(root)
    assert r2["ok"] and r2["created"] == []


def test_list_search_ingest(tmp_path):
    root = tmp_path / "kb"
    bootstrap_vault(root)
    ingest_text(root, "架构决策", "采用聚合池做故障转移")
    pages = list_pages(root, query="overview")
    assert any(p.rel.endswith("overview.md") for p in pages)
    found = list_pages(root, query="聚合")
    assert any("inbox" in p.rel for p in found)
    page = read_page(root, "wiki/overview.md")
    assert page and "CodeCoreAgent" in page["content"]


def test_path_traversal_blocked(tmp_path):
    root = tmp_path / "kb"
    bootstrap_vault(root)
    assert read_page(root, "../secrets.txt") is None
    assert read_page(root, "wiki/../../etc/passwd") is None


def test_knowledge_config_roundtrip(tmp_path, monkeypatch):
    cfg_path = tmp_path / "knowledge.json"
    monkeypatch.setattr("codeagent.knowledge.CONFIG_PATH", cfg_path)
    cfg = KnowledgeConfig(mode="shared", backend="llmwiki", path=str(tmp_path / "shared"))
    cfg.save(cfg_path)
    loaded = KnowledgeConfig.load(cfg_path)
    assert loaded.mode == "shared"
    assert loaded.backend == "llmwiki"
    assert loaded.path.endswith("shared")


def test_knowledge_tools_require_ready_vault(tmp_path, monkeypatch):
    cfg_path = tmp_path / "knowledge.json"
    monkeypatch.setattr("codeagent.knowledge.CONFIG_PATH", cfg_path)
    monkeypatch.setattr("codeagent.knowledge.tools.KnowledgeConfig", KnowledgeConfig)
    cfg = KnowledgeConfig(path=str(tmp_path / "empty"), enabled=True)
    cfg.save(cfg_path)
    assert knowledge_tools(cfg) == []
    bootstrap_vault(tmp_path / "empty")
    tools = knowledge_tools(cfg)
    assert {t.name for t in tools} >= {
        "knowledge_search", "knowledge_read", "knowledge_ingest",
    }


def test_ui_has_knowledge_page():
    assert 'data-page="knowledge"' in HTML
    assert 'id="page-knowledge"' in HTML
    assert "一键布置" in HTML
    assert "pywebview.api.bootstrap_knowledge" in HTML
    assert "pywebview.api.save_knowledge_config" in HTML
    assert "loadKnowledge" in HTML
