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
