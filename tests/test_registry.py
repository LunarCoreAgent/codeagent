import pytest

from codeagent import Tool, ToolRegistry, create_provider, list_providers
from codeagent.core.types import ToolCall


def test_list_providers():
    providers = list_providers()
    assert "anthropic" in providers
    assert "openai" in providers
    assert "ollama" in providers


def test_create_unknown_provider():
    with pytest.raises(ValueError, match="Unknown provider"):
        create_provider("does-not-exist")


def test_ollama_resolve_model_fallback(monkeypatch):
    """Unpulled configured model falls back to the first installed one."""
    import json as jsonlib

    from codeagent.llm import ollama

    payload = jsonlib.dumps(
        {"models": [{"name": "qwen3:8b"}, {"name": "qwen3:4b"}]}
    ).encode()

    class FakeResp:
        def read(self):
            return payload

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(
        ollama.urllib.request, "urlopen", lambda *a, **k: FakeResp()
    )
    assert ollama._resolve_model("http://x:11434/v1", "missing:7b") == "qwen3:8b"
    assert ollama._resolve_model("http://x:11434/v1", "qwen3:4b") == "qwen3:4b"


def test_ollama_resolve_model_offline(monkeypatch):
    """Server unreachable → configured model kept untouched."""
    from codeagent.llm import ollama

    def boom(*a, **k):
        raise OSError("connection refused")

    monkeypatch.setattr(ollama.urllib.request, "urlopen", boom)
    assert ollama._resolve_model("http://x:11434/v1", "keep:me") == "keep:me"


class EchoTool(Tool):
    name = "echo"
    description = "Echo back the input."
    parameters = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    }

    async def execute(self, text: str, **_):
        return f"echo: {text}"


async def test_registry_dispatch():
    registry = ToolRegistry([EchoTool()])
    result = await registry.execute(ToolCall(name="echo", arguments={"text": "hi"}))
    assert not result.is_error
    assert result.content == "echo: hi"


async def test_registry_unknown_tool():
    registry = ToolRegistry([EchoTool()])
    result = await registry.execute(ToolCall(name="missing", arguments={}))
    assert result.is_error
    assert "Unknown tool" in result.content


async def test_registry_bad_arguments():
    registry = ToolRegistry([EchoTool()])
    result = await registry.execute(ToolCall(name="echo", arguments={"wrong": 1}))
    assert result.is_error
    assert "Invalid arguments" in result.content


async def test_registry_tool_exception_becomes_error_result():
    class BoomTool(Tool):
        name = "boom"
        description = "Always fails."
        parameters = {"type": "object", "properties": {}}

        async def execute(self, **_):
            raise RuntimeError("kaput")

    registry = ToolRegistry([BoomTool()])
    result = await registry.execute(ToolCall(name="boom", arguments={}))
    assert result.is_error
    assert "kaput" in result.content


def test_tool_schema():
    schema = EchoTool().to_schema()
    assert schema["name"] == "echo"
    assert schema["parameters"]["type"] == "object"
