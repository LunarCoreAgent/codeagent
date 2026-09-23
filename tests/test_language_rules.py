"""Language detection and built-in runtime rules."""

from codeagent.skills.language import (
    detect_language,
    ensure_runtime,
    language_skill_names,
)


def test_detects_simplified_chinese():
    hit = detect_language("请把这个函数改成可读的")
    assert hit is not None
    assert hit.code == "zh"
    assert language_skill_names("请把这个函数改成可读的") == ["lang-zh"]


def test_detects_traditional_chinese():
    hit = detect_language("請把這個軟體改成繁體介面")
    assert hit is not None
    assert hit.code == "zh-Hant"


def test_detects_english_japanese_korean():
    assert detect_language("Please rename this function").code == "en"
    assert detect_language("この関数を直してください").code == "ja"
    assert detect_language("이 함수를 고쳐 주세요").code == "ko"


def test_ignores_code_fence_when_prose_is_chinese():
    text = "请解释下面的代码\n```python\nprint('hello')\n```"
    assert detect_language(text).code == "zh"


def test_python_and_browser_stay_builtin(monkeypatch):
    assert "本体 Python" in ensure_runtime("python")
    assert "本体浏览器" in ensure_runtime("browser")
    assert "本体终端" in ensure_runtime("terminal")


def test_node_installs_only_when_missing(monkeypatch, tmp_path):
    monkeypatch.setattr("codeagent.node_runtime.node_exe", lambda: None)

    def _install(dest=None, timeout=180):
        return tmp_path

    monkeypatch.setattr("codeagent.node_runtime.ensure_installed", _install)
    monkeypatch.setattr("codeagent.node_runtime.node_exe", lambda: None)
    text = ensure_runtime("node")
    assert "nodejs.org" in text
    assert str(tmp_path) in text
