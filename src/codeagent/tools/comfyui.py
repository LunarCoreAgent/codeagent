"""Agent tool for a local ComfyUI server (https://github.com/Comfy-Org/ComfyUI)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from codeagent.security.policy import RiskLevel
from codeagent.tools.base import Tool

INSTALL_HINT = (
    "本机 ComfyUI 还没起来。它是节点图引擎，不是聊天模型。\n"
    "1) 桌面版：https://www.comfy.org/download （Windows / macOS）\n"
    "2) 源码：git clone https://github.com/Comfy-Org/ComfyUI "
    "后按 README 建 venv，运行 python main.py --listen 0.0.0.0 --port 8188\n"
    "浏览器打开 http://127.0.0.1:8188。局域网还要 --listen 0.0.0.0。\n"
    "SD 权重放 models/checkpoints；MiniMax-H3 等 GGUF 放 models/diffusion_models，"
    "并安装 city96/ComfyUI-GGUF，否则下拉里搜不到。\n"
    "自动化必须用菜单 Save (API Format) 的 JSON，不要用手绘一张新图。"
)


class ComfyTool(Tool):
    name = "comfy"
    description = (
        "Talk to local ComfyUI (default http://127.0.0.1:8188): probe, queue an "
        "API-format workflow, optionally patch the positive prompt, download "
        "images/videos. Not a chat model. Call this yourself for 文生图 / "
        "节点图 / Comfy — do not ask the user to click Queue."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "status | queue | interrupt",
            },
            "workflow_path": {
                "type": "string",
                "description": "API Format JSON from ComfyUI (required for queue).",
            },
            "prompt": {
                "type": "string",
                "description": "Overwrite the first positive CLIPTextEncode text.",
            },
            "base": {
                "type": "string",
                "description": "ComfyUI origin, default configured or :8188.",
            },
            "dest_dir": {
                "type": "string",
                "description": "Where to save outputs.",
            },
        },
        "required": ["action"],
    }
    risk_level = RiskLevel.WRITE

    def risk_for(self, arguments: dict[str, Any]) -> RiskLevel:
        if str(arguments.get("action") or "").strip().lower() == "status":
            return RiskLevel.READ_ONLY
        return RiskLevel.WRITE

    async def execute(
        self,
        action: str,
        workflow_path: str = "",
        prompt: str = "",
        base: str = "",
        dest_dir: str = "",
        **_: Any,
    ) -> str:
        from codeagent.videoops.comfy import (
            interrupt_comfy,
            load_workflow_file,
            patch_workflow_prompt,
            probe_comfy,
            queue_comfy_workflow,
            resolve_comfy_base,
        )

        action = (action or "").strip().lower()
        root = resolve_comfy_base(base)
        if action == "status":
            info = await probe_comfy(root)
            if info is None:
                return INSTALL_HINT + f"\n当前地址：{root}"
            return f"在线 {info['base']}。用 queue + workflow_path 跑 API 工作流。"
        if action == "interrupt":
            result = await interrupt_comfy(root)
            if not result.get("ok"):
                return f"取消失败：{result.get('error')}"
            return "已请求 ComfyUI 中断当前任务"
        if action != "queue":
            return "未知 action。可用：status / queue / interrupt"
        if not (workflow_path or "").strip():
            return (
                "queue 需要 workflow_path：在 ComfyUI 菜单 Save (API Format) "
                "后把 JSON 路径传进来。"
            )
        try:
            wf = load_workflow_file(workflow_path)
        except (OSError, ValueError) as exc:
            return f"读工作流失败：{exc}"
        if prompt.strip():
            patched = patch_workflow_prompt(wf, prompt.strip())
            if not patched:
                return "工作流里找不到可改的 text 节点（CLIPTextEncode）。"
        dest = Path(dest_dir).expanduser() if dest_dir.strip() else self._default_dest()
        result = await queue_comfy_workflow(root, wf, dest)
        if not result.get("ok"):
            err = str(result.get("error") or "")
            if "未配置" in err or "connect" in err.lower():
                return INSTALL_HINT + f"\n{err}"
            return f"排队失败：{err}"
        files = result.get("files") or [result.get("path")]
        return "已出图/成片：\n" + "\n".join(str(p) for p in files if p)

    @staticmethod
    def _default_dest() -> Path:
        try:
            from codeagent.videoops import VideoOpsConfig

            root = VideoOpsConfig.load().workspace()
            if root.exists():
                dest = root / "02-generate"
                dest.mkdir(parents=True, exist_ok=True)
                return dest
        except OSError:
            pass
        dest = Path("~/.codeagent/comfy-out").expanduser()
        dest.mkdir(parents=True, exist_ok=True)
        return dest


def comfy_tools() -> list[Tool]:
    return [ComfyTool()]
