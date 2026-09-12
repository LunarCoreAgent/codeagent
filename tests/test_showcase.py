"""Website showcase helpers: detect task, extract URLs, serve static dist."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from codeagent.browser.showcase import (
    SHOWCASE_NUDGE,
    ensure_local_preview,
    extract_preview_urls,
    find_static_site_root,
    looks_like_website_finished,
    looks_like_website_task,
    pick_preview_url,
    preview_unavailable_html,
    probe_http,
)


def test_looks_like_website_task():
    assert looks_like_website_task("帮我改官网落地页")
    assert looks_like_website_task("build a vite react landing page")
    assert not looks_like_website_task("修复 cron 调度器空指针")


def test_extract_preview_urls():
    text = "预览：http://127.0.0.1:5173/home 以及 http://localhost:3000"
    urls = extract_preview_urls(text)
    assert urls[0].startswith("http://127.0.0.1:5173")
    assert urls[1].startswith("http://localhost:3000")


def test_find_static_site_root(tmp_path: Path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>ok</html>", encoding="utf-8")
    assert find_static_site_root(tmp_path) == dist.resolve()
    nested = tmp_path / "site" / "build"
    nested.mkdir(parents=True)
    (nested / "index.html").write_text("<html>n</html>", encoding="utf-8")
    # Prefer top-level dist when present
    assert find_static_site_root(tmp_path) == dist.resolve()


def test_ensure_local_preview_serves(tmp_path: Path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html><body>hi</body></html>", encoding="utf-8")
    url = ensure_local_preview(tmp_path)
    assert url and url.startswith("http://127.0.0.1:")
    assert probe_http(url)
    # Reuse same server
    assert ensure_local_preview(tmp_path) == url


def test_pick_preview_url_skips_dead_prefers_live(tmp_path: Path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html><body>live</body></html>", encoding="utf-8")
    dead = "http://127.0.0.1:9/"  # discard port, never listening
    with patch("codeagent.browser.showcase.discover_local_preview", return_value=None):
        url = pick_preview_url(
            f"预览 {dead} 已完成",
            workspace=tmp_path,
        )
    assert url and probe_http(url)
    assert ":9" not in url


def test_preview_unavailable_html_mentions_url():
    html = preview_unavailable_html("http://127.0.0.1:4173/")
    assert "4173" in html
    assert "打不开" in html


def test_showcase_nudge_mentions_browser():
    assert "browser" in SHOWCASE_NUDGE
    assert "file://" in SHOWCASE_NUDGE
    assert "白屏" in SHOWCASE_NUDGE
    assert looks_like_website_finished("做网站", "已完成首页改版")
