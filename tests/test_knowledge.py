"""Tests for CodeCoreAgent knowledge vault (Obsidian / LLM Wiki)."""

from __future__ import annotations

from pathlib import Path

from codeagent.desktop.ui import HTML
from codeagent.knowledge import (
    KnowledgeConfig,
    bootstrap_vault,
    ensure_knowledge_vault,
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
    monkeypatch.setattr("codeagent.knowledge.tools.ensure_knowledge_vault", ensure_knowledge_vault)
    cfg = KnowledgeConfig(path=str(tmp_path / "empty"), enabled=True)
    cfg.save(cfg_path)
    # Auto-deploy on first tools() call
    tools = knowledge_tools(cfg)
    assert {t.name for t in tools} >= {
        "knowledge_search", "knowledge_read", "knowledge_ingest",
    }
    assert is_vault_ready(tmp_path / "empty")


def test_ensure_knowledge_vault_auto_deploys(tmp_path, monkeypatch):
    cfg_path = tmp_path / "knowledge.json"
    monkeypatch.setattr("codeagent.knowledge.CONFIG_PATH", cfg_path)
    root = tmp_path / "auto-wiki"
    cfg = KnowledgeConfig(path=str(root), enabled=True)
    cfg.save(cfg_path)
    r = ensure_knowledge_vault(cfg, config_path=cfg_path)
    assert r["ok"] and r.get("ready")
    assert is_vault_ready(root)
    assert (root / "wiki" / "concepts" / "openviking.md").is_file()
    assert (root / "wiki" / "concepts" / "tencentdb-agent-memory.md").is_file()
    assert "OpenViking" in (root / "AGENTS.md").read_text(encoding="utf-8")
    loaded = KnowledgeConfig.load(cfg_path)
    assert loaded.bootstrapped is True
    # idempotent
    r2 = ensure_knowledge_vault(cfg, config_path=cfg_path)
    assert r2["ok"] and r2.get("ready")
    assert r2.get("created") == []  # 二次调用不重种


def test_ui_has_knowledge_page():
    assert 'data-page="knowledge"' in HTML
    assert 'id="page-knowledge"' in HTML
    assert "修复布置" in HTML
    assert "自动部署" in HTML or "随安装自动部署" in HTML
    assert "pywebview.api.bootstrap_knowledge" in HTML
    assert "pywebview.api.save_knowledge_config" in HTML
    assert "局域网硬盘" in HTML
    assert "pickKnowledgePath" in HTML
    assert "pick_knowledge_path" in HTML
    assert 'id="sectKnowledgePath"' in HTML
    assert 'id="cfg_kb_path"' in HTML
    assert "saveKnowledgePathFromSettings" in HTML
    assert "loadKnowledge" in HTML
    assert "get_knowledge(false, true)" in HTML
    assert "页数未统计" in HTML
