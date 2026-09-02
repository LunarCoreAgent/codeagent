"""OTA check-in: the entry point to xiaozhi.me's free server.

POSTing device info to the OTA endpoint returns either:
- ``websocket`` section (url + token) → device is activated, ready to connect;
- ``activation`` section (code + message) → the user must register this
  device in the xiaozhi.me console with the shown code, then check in again.
"""

from __future__ import annotations

from dataclasses import dataclass

from codeagent.xiaozhi.config import XiaozhiConfig


@dataclass
class OtaResult:
    websocket_url: str | None = None
    websocket_token: str | None = None
    activation_code: str | None = None
    activation_message: str | None = None
    firmware_version: str | None = None

    @property
    def activated(self) -> bool:
        return bool(self.websocket_url and self.websocket_token)


class ActivationRequiredError(RuntimeError):
    """Device not yet activated; user must register the code at xiaozhi.me."""

    def __init__(self, result: OtaResult) -> None:
        self.result = result
        super().__init__(
            f"设备未激活。请前往 xiaozhi.me 控制台添加设备，"
            f"验证码：{result.activation_code}。"
            f"{result.activation_message or ''}"
        )


class OtaClient:
    def __init__(self, config: XiaozhiConfig) -> None:
        self.config = config

    async def check_in(self) -> OtaResult:
        try:
            import httpx
        except ImportError as exc:
            raise RuntimeError(
                "httpx is required for xiaozhi OTA: pip install codeagent[xiaozhi]"
            ) from exc

        headers = {
            "Device-Id": self.config.device_id,
            "Client-Id": self.config.client_id,
            "Activation-Version": "1",
            "Content-Type": "application/json",
            "User-Agent": "codeagent/0.11",
            "Accept-Language": "zh-CN",
        }
        payload = {
            "application": {"version": "0.11.0", "elf_sha256": ""},
            "board": {"type": "codeagent", "name": "codeagent-desktop"},
        }
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(self.config.ota_url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        result = OtaResult()
        firmware = data.get("firmware") or {}
        result.firmware_version = firmware.get("version")
        websocket = data.get("websocket") or {}
        result.websocket_url = websocket.get("url")
        result.websocket_token = websocket.get("token")
        activation = data.get("activation") or {}
        result.activation_code = activation.get("code")
        result.activation_message = activation.get("message")
        return result
