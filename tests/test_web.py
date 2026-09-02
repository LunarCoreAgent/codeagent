"""Web tools: web_fetch / web_scrape against a real local HTTP server."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from codeagent.tools import WebFetchTool, WebScrapeTool, web_tools

scrapling = pytest.importorskip("scrapling", reason="scrapling not installed")

HTML = """<!DOCTYPE html><html><head><title>测试页</title>
<style>.x{color:red}</style></head>
<body><h1>产品列表</h1>
<div class="product"><h2>苹果</h2><a href="/p/1">详情</a></div>
<div class="product"><h2>香蕉</h2><a href="/p/2">详情</a></div>
<script>var x=1;</script></body></html>"""


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(HTML.encode())

    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def server():
    srv = HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/"
    srv.shutdown()


async def test_web_fetch_returns_clean_text(server):
    out = await WebFetchTool().execute(url=server)
    assert "[HTTP 200]" in out
    assert "产品列表" in out
    assert "苹果" in out
    assert "var x=1" not in out  # script 已剥离
    assert "color:red" not in out  # style 已剥离


async def test_web_fetch_with_selector(server):
    out = await WebFetchTool().execute(url=server, selector=".product h2")
    assert "苹果" in out and "香蕉" in out
    assert "产品列表" not in out  # 选择器外的内容不返回


async def test_web_fetch_selector_no_match(server):
    out = await WebFetchTool().execute(url=server, selector=".nonexistent")
    assert "no elements matched" in out


async def test_web_fetch_truncates(server):
    out = await WebFetchTool().execute(url=server, max_chars=10)
    assert len(out) < 100


async def test_web_scrape_structured_extraction(server):
    out = await WebScrapeTool().execute(
        url=server,
        selectors={"title": ".product h2::text", "link": ".product a::attr(href)"},
    )
    payload = json.loads(out)
    assert payload["status"] == 200
    assert payload["data"]["title"] == ["苹果", "香蕉"]
    assert payload["data"]["link"] == ["/p/1", "/p/2"]


async def test_web_scrape_limit(server):
    out = await WebScrapeTool().execute(
        url=server, selectors={"title": ".product h2::text"}, limit=1,
    )
    assert json.loads(out)["data"]["title"] == ["苹果"]


def test_web_tools_factory():
    tools = web_tools()
    assert {t.name for t in tools} == {"web_fetch", "web_scrape"}
    assert all(t.risk_level.name == "READ_ONLY" for t in tools)
