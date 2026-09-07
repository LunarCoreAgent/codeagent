"""ComfyUI fusion: prompt patch + comfy tool without a live server."""

from __future__ import annotations

from codeagent.tools.comfyui import INSTALL_HINT, ComfyTool
from codeagent.videoops.comfy import patch_workflow_prompt, resolve_comfy_base


def test_patch_workflow_prompt_skips_negative():
    wf = {
        "prompt": {
            "1": {
                "class_type": "CLIPTextEncode",
                "_meta": {"title": "Positive"},
                "inputs": {"text": "old", "clip": ["2", 0]},
            },
            "3": {
                "class_type": "CLIPTextEncode",
                "_meta": {"title": "Negative"},
                "inputs": {"text": "bad", "clip": ["2", 0]},
            },
        }
    }
    assert patch_workflow_prompt(wf, "a red boat") == 1
    assert wf["prompt"]["1"]["inputs"]["text"] == "a red boat"
    assert wf["prompt"]["3"]["inputs"]["text"] == "bad"


def test_resolve_comfy_base_defaults_to_8188(monkeypatch):
    class _Cfg:
        comfy_base = ""

    monkeypatch.setattr(
        "codeagent.videoops.VideoOpsConfig.load",
        classmethod(lambda cls, path=None: _Cfg()),
    )
    assert resolve_comfy_base("").endswith(":8188")
    assert resolve_comfy_base("127.0.0.1:8188") == "http://127.0.0.1:8188"


async def test_comfy_status_offline_explains_install(monkeypatch):
    async def offline(_base, timeout=3.0):
        return None

    monkeypatch.setattr("codeagent.videoops.comfy.probe_comfy", offline)
    text = await ComfyTool().execute(action="status", base="http://127.0.0.1:8188")
    assert "8188" in text
    assert "不是聊天模型" in INSTALL_HINT
    assert "github.com/Comfy-Org/ComfyUI" in text or "comfy.org" in text


async def test_comfy_queue_requires_workflow():
    text = await ComfyTool().execute(action="queue")
    assert "workflow_path" in text


def test_default_tools_include_comfy():
    from codeagent.tools import default_tools

    assert default_tools().get("comfy") is not None


async def test_probe_comfy_lists_gguf_from_unet_loader(monkeypatch):
    from codeagent.videoops import comfy as c

    class _Resp:
        def __init__(self, status, payload):
            self.status_code = status
            self._payload = payload

        def json(self):
            return self._payload

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_a):
            return False

        async def get(self, url):
            if url.endswith("/system_stats"):
                return _Resp(200, {"system": {}, "devices": []})
            if url.endswith("/object_info/UnetLoaderGGUF"):
                return _Resp(200, {
                    "UnetLoaderGGUF": {
                        "input": {
                            "required": {
                                "unet_name": [[
                                    "MiniMax-H3-FL2VA-Q4_K_M.gguf",
                                    "MiniMax-H3-Ref2VA-Q4_K_M.gguf",
                                ]],
                            }
                        }
                    }
                })
            if "/models/" in url:
                return _Resp(200, [])
            return _Resp(404, {})

        def __init__(self, **_kw):
            pass

    monkeypatch.setattr(c.httpx, "AsyncClient", _Client)
    info = await c.probe_comfy("http://192.168.3.23:8188")
    names = [m["name"] for m in info["models"]]
    assert "MiniMax-H3-FL2VA-Q4_K_M.gguf" in names


async def test_probe_comfy_lists_checkpoints(monkeypatch):
    from codeagent.videoops import comfy as c

    class _Resp:
        def __init__(self, status, payload):
            self.status_code = status
            self._payload = payload

        def json(self):
            return self._payload

    class _Client:
        def __init__(self, **_kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_a):
            return False

        async def get(self, url):
            if url.endswith("/system_stats"):
                return _Resp(200, {"system": {}, "devices": []})
            if url.endswith("/models/checkpoints"):
                return _Resp(200, ["a.safetensors"])
            if "/models/" in url:
                return _Resp(200, [])
            return _Resp(404, {})

    monkeypatch.setattr(c.httpx, "AsyncClient", _Client)
    info = await c.probe_comfy("http://192.168.3.23:8188")
    assert info and info["ok"]
    assert info["models"][0]["name"] == "a.safetensors"
