"""Device identity for the xiaozhi protocol.

Mirrors xiaozhi-esp32: ``device_id`` is a MAC address, ``client_id`` a
persistent UUID. Both are stored locally so the device stays registered
across restarts.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_OTA_URL = "https://api.tenclass.net/xiaozhi/ota/"
DEFAULT_CONFIG_PATH = "~/.codeagent/xiaozhi.json"


def _generate_device_id() -> str:
    """A locally-administered MAC-style id (xiaozhi expects MAC format)."""
    mac = uuid.getnode() | (1 << 40)  # set locally-administered bit
    return ":".join(f"{(mac >> (8 * i)) & 0xFF:02x}" for i in reversed(range(6)))


@dataclass
class XiaozhiConfig:
    ota_url: str = DEFAULT_OTA_URL
    device_id: str = ""
    client_id: str = ""

    @classmethod
    def load(cls, path: str | Path = DEFAULT_CONFIG_PATH) -> "XiaozhiConfig":
        p = Path(path).expanduser()
        if p.exists():
            data = json.loads(p.read_text())
            return cls(
                ota_url=data.get("ota_url", DEFAULT_OTA_URL),
                device_id=data.get("device_id", ""),
                client_id=data.get("client_id", ""),
            )
        config = cls(device_id=_generate_device_id(), client_id=uuid.uuid4().hex)
        config.save(p)
        return config

    def save(self, path: str | Path = DEFAULT_CONFIG_PATH) -> None:
        p = Path(path).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({
            "ota_url": self.ota_url,
            "device_id": self.device_id,
            "client_id": self.client_id,
        }, indent=2))
