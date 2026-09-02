"""Xiaozhi client: OTA check-in + WebSocket protocol against local mock servers."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

websockets = pytest.importorskip("websockets", reason="websockets not installed")
httpx = pytest.importorskip("httpx", reason="httpx not installed")

from codeagent.xiaozhi import (
    ActivationRequiredError,
    OtaClient,
    XiaozhiClient,
    XiaozhiConfig,
    XiaozhiProtocol,
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def test_config_generates_and_persists_identity(tmp_path):
    path = tmp_path / "xz.json"
    config = XiaozhiConfig.load(path)
    assert config.device_id.count(":") == 5  # MAC format
    assert len(config.client_id) == 32       # UUID hex
    again = XiaozhiConfig.load(path)
    assert again.device_id == config.device_id
    assert again.client_id == config.client_id


# ---------------------------------------------------------------------------
# OTA
# ---------------------------------------------------------------------------

def _serve_json(payload: dict):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            # consume the request body first: closing the socket with unread
            # data can RST the connection and break the client under load
            length = int(self.headers.get("Content-Length") or 0)
            if length:
                self.rfile.read(length)
            body = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    srv = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/ota/"


async def test_ota_activated(tmp_path):
    srv, url = _serve_json({
        "firmware": {"version": "1.9.0"},
        "websocket": {"url": "wss://example.com/xiaozhi/v1/", "token": "tok123"},
    })
    config = XiaozhiConfig.load(tmp_path / "xz.json")
    config.ota_url = url
    result = await OtaClient(config).check_in()
    srv.shutdown()
    assert result.activated
    assert result.websocket_url.startswith("wss://")
    assert result.websocket_token == "tok123"
    assert result.firmware_version == "1.9.0"


async def test_ota_activation_required(tmp_path):
    srv, url = _serve_json({
        "activation": {"code": "A1B2C3", "message": "请在控制台添加设备"},
    })
    config = XiaozhiConfig.load(tmp_path / "xz.json")
    config.ota_url = url
    result = await OtaClient(config).check_in()
    srv.shutdown()
    assert not result.activated
    assert result.activation_code == "A1B2C3"
    with pytest.raises(ActivationRequiredError):
        raise ActivationRequiredError(result)


# ---------------------------------------------------------------------------
# Protocol: full flow against a mock xiaozhi server
# ---------------------------------------------------------------------------

async def _run_mock_server(handler):
    from websockets.asyncio.server import serve

    server = await serve(handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    return server, f"ws://127.0.0.1:{port}"


async def test_protocol_full_conversation_flow():
    captured = {}

    async def mock_server(ws):
        captured["headers"] = ws.request.headers
        hello = json.loads(await ws.recv())
        assert hello["type"] == "hello"
        assert hello["audio_params"]["format"] == "opus"
        await ws.send(json.dumps({
            "type": "hello", "transport": "websocket", "session_id": "s-1",
        }))
        listen = json.loads(await ws.recv())
        assert listen["type"] == "listen" and listen["state"] == "start"
        audio = await ws.recv()
        assert isinstance(audio, bytes)  # binary opus frame
        stop = json.loads(await ws.recv())
        assert stop["state"] == "stop"
        # server replies: stt → llm emotion → tts start → audio → sentence → stop
        await ws.send(json.dumps({"type": "stt", "text": "你好"}))
        await ws.send(json.dumps({"type": "llm", "emotion": "happy", "text": "😀"}))
        await ws.send(json.dumps({"type": "tts", "state": "start"}))
        await ws.send(b"\x00\x01fake-opus")
        await ws.send(json.dumps({"type": "tts", "state": "sentence_start", "text": "你好呀"}))
        await ws.send(json.dumps({"type": "tts", "state": "stop"}))
        await ws.close()

    server, url = await _run_mock_server(mock_server)
    try:
        client = XiaozhiClient(config=XiaozhiConfig(device_id="aa:bb:cc:dd:ee:ff", client_id="cid"))
        await client.protocol.connect(url, "tok", "aa:bb:cc:dd:ee:ff", "cid", proxy=None)
        assert client.protocol.session_id == "s-1"

        events = await client.say([b"\x01\x02fake-pcm-opus"])
        assert events.stt_text == "你好"
        assert events.emotion == "happy"
        assert events.sentences == ["你好呀"]
        assert events.audio_frames == [b"\x00\x01fake-opus"]

        # 鉴权头符合小智协议（Headers 对象大小写不敏感）
        headers = captured["headers"]
        assert headers["Authorization"] == "Bearer tok"
        assert headers["Protocol-Version"] == "1"
        assert headers["Device-Id"] == "aa:bb:cc:dd:ee:ff"
        await client.close()
    finally:
        server.close()


async def test_protocol_rejects_bad_handshake():
    async def bad_server(ws):
        await ws.recv()
        await ws.send(json.dumps({"type": "not-hello"}))

    server, url = await _run_mock_server(bad_server)
    try:
        protocol = XiaozhiProtocol()
        import pytest as _pytest
        with _pytest.raises(RuntimeError, match="handshake"):
            await protocol.connect(url, "t", "d", "c", proxy=None)
    finally:
        server.close()


def test_message_builders():
    protocol = XiaozhiProtocol()
    protocol.session_id = "s-42"
    assert protocol.hello_message()["audio_params"]["sample_rate"] == 16000
    listen = protocol.listen_message("start", mode="auto")
    assert listen == {"session_id": "s-42", "type": "listen", "state": "start", "mode": "auto"}
    detect = protocol.listen_message("detect", text="你好小智")
    assert detect["text"] == "你好小智"
    assert protocol.abort_message()["reason"] == "wake_word_detected"
