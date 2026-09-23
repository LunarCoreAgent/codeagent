"""Host rules: reply in the user's language, and prefer built-in runtimes.

Language skills are activated from the script of the user's text.
Browser, shell, Python, and Node.js are used from the app itself.
Only Node.js is downloaded, and only from the official nodejs.org build,
into ``~/.codeagent/runtime``.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

HOST_RULES = """\
[本体优先]
1. 先判断用户这段文字的语言，调用对应语言技能，并用该语言回复。语言技能只管用语和标点，不盖过当前任务技能。
2. 需要浏览器、终端、Python、Node.js 时，先用本体已有能力：browser 工具、bash 工具、当前解释器、已融合的 node/npx。
3. 本体没有时，调用 ensure_runtime。Node.js 只从 nodejs.org 官方包安装到 ~/.codeagent/runtime。不要让用户先自己安装，也不要执行来路不明的安装脚本。
"""

# name, description, triggers, body
LANGUAGE_SKILLS: dict[str, tuple[str, str, str, str]] = {
    "lang-zh": (
        "按简体中文回复",
        "简体,中文,语言,zh",
        "codeagent host language rule",
        """# 简体中文
用户文字是简体中文。用简体中文回复。
中文句子用全角标点；代码、路径、命令、API 用半角。
不要把回复改成英文，除非用户明确要求。
""",
    ),
    "lang-zh-hant": (
        "按繁体中文回复",
        "繁体,繁體,中文,语言,zh-Hant",
        "codeagent host language rule",
        """# 繁體中文
用戶文字是繁體中文。用繁體中文回覆。
中文句子用全形標點；程式碼、路徑、命令、API 用半形。
不要改成簡體或英文，除非用戶明確要求。
""",
    ),
    "lang-en": (
        "Reply in English",
        "english,语言,en",
        "codeagent host language rule",
        """# English
The user's text is English. Reply in English.
Keep code, paths, and commands unchanged. Do not switch to Chinese unless asked.
""",
    ),
    "lang-ja": (
        "日本語で返答する",
        "日本語,语言,ja",
        "codeagent host language rule",
        """# 日本語
ユーザーの文は日本語。日本語で返答する。
コード、パス、コマンドはそのまま。頼まれない限り中国語や英語にしない。
""",
    ),
    "lang-ko": (
        "한국어로 답한다",
        "한국어,语言,ko",
        "codeagent host language rule",
        """# 한국어
사용자 문장은 한국어다. 한국어로 답한다.
코드, 경로, 명령은 그대로 둔다. 요청 없이 다른 언어로 바꾸지 않는다.
""",
    ),
    "lang-fr": (
        "Répondre en français",
        "français,语言,fr",
        "codeagent host language rule",
        """# Français
Le texte de l'utilisateur est en français. Répondre en français.
Laisser le code, les chemins et les commandes tels quels.
""",
    ),
    "lang-es": (
        "Responder en español",
        "español,语言,es",
        "codeagent host language rule",
        """# Español
El texto del usuario está en español. Responder en español.
Dejar el código, las rutas y los comandos como están.
""",
    ),
}

_LANG_LABEL = {
    "zh": "简体中文",
    "zh-Hant": "繁体中文",
    "en": "英文",
    "ja": "日语",
    "ko": "韩语",
    "fr": "法语",
    "es": "西班牙语",
}

_HANT_ONLY = set("們這過還說國門東書無發麼後從裡體臺萬軟體請復顯開關")
_HANS_ONLY = set("们这过还说国门东书无发么后从里体台万软体请复显开关")


@dataclass(frozen=True)
class LanguageHit:
    code: str
    label: str
    skill: str


def detect_language(text: str) -> LanguageHit | None:
    """Pick a reply language from the user's own words, ignoring code fences."""
    sample = _prose(text)
    if not sample.strip():
        return None
    han = kana = hangul = latin = 0
    hant = hans = 0
    for ch in sample:
        o = ord(ch)
        if 0x4E00 <= o <= 0x9FFF:
            han += 1
            if ch in _HANT_ONLY:
                hant += 1
            elif ch in _HANS_ONLY:
                hans += 1
        elif 0x3040 <= o <= 0x30FF:
            kana += 1
        elif 0xAC00 <= o <= 0xD7AF:
            hangul += 1
        elif ("A" <= ch <= "Z") or ("a" <= ch <= "z"):
            latin += 1
    if kana >= 2 or (kana >= 1 and kana >= han):
        return _hit("ja")
    if hangul >= 2 or (hangul >= 1 and hangul >= han and hangul >= latin):
        return _hit("ko")
    if han >= 2 or (han >= 1 and han >= latin):
        return _hit("zh-Hant" if hant > hans else "zh")
    low = sample.lower()
    if any(w in low for w in (" le ", " la ", " les ", " est ", " une ", " pas ")):
        return _hit("fr")
    if any(w in low for w in (" el ", " la ", " los ", " una ", " que ", " para ")):
        return _hit("es")
    if latin >= 3:
        return _hit("en")
    return None


def language_directive(text: str) -> str:
    hit = detect_language(text)
    if hit is None:
        return ""
    return (
        f"[语言] 用户文字为{hit.label}。用{hit.label}回复。"
        f"调用技能 {hit.skill}。语言技能不盖过任务技能。\n"
        + HOST_RULES
    )


def language_skill_names(text: str) -> list[str]:
    hit = detect_language(text)
    if hit is None:
        return []
    return [hit.skill]


def _hit(code: str) -> LanguageHit:
    skill = {
        "zh": "lang-zh",
        "zh-Hant": "lang-zh-hant",
        "en": "lang-en",
        "ja": "lang-ja",
        "ko": "lang-ko",
        "fr": "lang-fr",
        "es": "lang-es",
    }[code]
    return LanguageHit(code, _LANG_LABEL[code], skill)


def _prose(text: str) -> str:
    lines = []
    fence = False
    for line in (text or "").splitlines():
        if line.strip().startswith("```"):
            fence = not fence
            continue
        if not fence:
            lines.append(line)
    return "\n".join(lines) if lines else (text or "")


def runtime_status() -> dict[str, str]:
    """Where the built-in browser, shell, Python, and Node.js live."""
    from codeagent.node_runtime import NODE_VERSION, node_exe

    node = node_exe()
    return {
        "browser": "builtin",
        "terminal": "bash",
        "python": sys.executable,
        "node": str(node) if node else "",
        "node_version": NODE_VERSION if node else "",
    }


def ensure_runtime(kind: str) -> str:
    """Use a built-in runtime, or install official Node.js into the app data dir."""
    name = (kind or "").strip().lower().replace(".", "")
    if name in {"browser", "浏览器", "web"}:
        return "本体浏览器已可用：调用 browser 工具（action=navigate / click / type）。不要另外下载浏览器。"
    if name in {"terminal", "shell", "bash", "终端", "命令行"}:
        return "本体终端已可用：调用 bash 工具执行命令。不要另外安装终端。"
    if name in {"python", "py", "python3"}:
        return f"本体 Python 已可用：{sys.executable}。不要另外下载解释器。"
    if name in {"node", "nodejs", "npx", "npm"}:
        from codeagent.node_runtime import NODE_VERSION, ensure_installed, node_exe

        if node_exe() is not None:
            return f"本体 Node.js 已可用：{node_exe()}（{NODE_VERSION}）。"
        dest = ensure_installed()
        exe = node_exe()
        return f"已从 nodejs.org 安装 Node.js {NODE_VERSION} 到本体：{exe or dest}"
    return (
        f"本体没有运行时 {kind!r}。先用 browser / bash / Python / Node。"
        "其他软件只在确认官方发布页后，安装到 ~/.codeagent/runtime，不要执行来路不明的脚本。"
    )
