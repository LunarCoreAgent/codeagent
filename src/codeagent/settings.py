"""Personalization: host-wide extra instructions & context for every chat.

Stored at ``~/.codeagent/settings.json``; loaded once and injected into the
system prompt of every agent on this host — chat, run, lead, workers, voice.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

DEFAULT_SETTINGS_PATH = Path("~/.codeagent/settings.json")


@dataclass
class Settings:
    """Host-wide personalization applied to all agent conversations.

    - ``nickname``: how the agent should address the user.
    - ``language``: preferred reply language (e.g. "中文").
    - ``instructions``: behavioral guidance ("回答要简洁", "先给结论").
    - ``context``: facts about the user/host ("M4 Mac", "项目在 ~/code").
    """

    nickname: str = ""
    language: str = ""
    instructions: str = ""
    context: str = ""

    # ------------------------------------------------------------------
    # persistence
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, path: str | Path | None = None) -> "Settings":
        path = Path(path or DEFAULT_SETTINGS_PATH).expanduser()
        if not path.is_file():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return cls()
        if not isinstance(data, dict):
            return cls()
        known = {"nickname", "language", "instructions", "context"}
        return cls(**{k: str(v) for k, v in data.items() if k in known})

    def save(self, path: str | Path | None = None) -> Path:
        path = Path(path or DEFAULT_SETTINGS_PATH).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "nickname": self.nickname,
                    "language": self.language,
                    "instructions": self.instructions,
                    "context": self.context,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return path

    @classmethod
    def clear(cls, path: str | Path | None = None) -> bool:
        path = Path(path or DEFAULT_SETTINGS_PATH).expanduser()
        if path.is_file():
            path.unlink()
            return True
        return False

    def is_empty(self) -> bool:
        return not (self.nickname or self.language or self.instructions or self.context)

    # ------------------------------------------------------------------
    # prompt injection
    # ------------------------------------------------------------------

    def prompt_block(self) -> str:
        """Render as a system-prompt section; empty string when unset."""
        if self.is_empty():
            return ""
        lines = ["[Personalization — applies to this user on this host]"]
        if self.nickname:
            lines.append(f"- 称呼用户为：{self.nickname}")
        if self.language:
            lines.append(f"- 首选回复语言：{self.language}")
        if self.instructions:
            lines.append(f"- 额外说明：{self.instructions}")
        if self.context:
            lines.append(f"- 用户与主机上下文：{self.context}")
        return "\n".join(lines)
