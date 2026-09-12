"""Website showcase helpers: detect task, extract URLs, serve static dist."""

from __future__ import annotations

from pathlib import Path

from codeagent.browser.showcase import (
    SHOWCASE_NUDGE,
    ensure_local_preview,
    extract_preview_urls,
    find_static_site_root,
    looks_like_website_finished,
    looks_like_website_task,
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
    # Reuse same server
    assert ensure_local_preview(tmp_path) == url


def test_showcase_nudge_mentions_browser():
    assert "browser" in SHOWCASE_NUDGE
    assert "file://" in SHOWCASE_NUDGE
    assert looks_like_website_finished("做网站", "已完成首页改版")
