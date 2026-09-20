"""Smart memory: two-phase writes (fact extraction + reconciliation)."""

import json

from codeagent import Agent, LocalMemoryStore, SmartMemoryStore, memory_tools
from codeagent.core.types import LLMResponse
from codeagent.llm.base import LLMProvider
from codeagent.memory import FactExtractor, MemoryReconciler


class ScriptedProvider(LLMProvider):
    """Returns canned LLM responses in order; records prompts."""

    name = "scripted"

    def __init__(self, responses: list[str]):
        super().__init__(model="scripted")
        self._responses = list(responses)
        self.prompts: list[str] = []

    async def complete(self, messages, tools=None, system=None, **kwargs):
        self.prompts.append(messages[-1].content)
        content = self._responses.pop(0) if self._responses else "{}"
        return LLMResponse(content=content)


# ---------------------------------------------------------------------------
# FactExtractor
# ---------------------------------------------------------------------------

async def test_fact_extraction_parses_json():
    provider = ScriptedProvider(
        ['```json\n{"facts": ["名字叫张三", "在小米工作"]}\n```']
    )
    extractor = FactExtractor(provider)
    facts = await extractor.extract("我的名字叫张三，我在小米工作")
    assert facts == ["名字叫张三", "在小米工作"]


async def test_fact_extraction_handles_garbage():
    provider = ScriptedProvider(["no json here"])
    extractor = FactExtractor(provider)
    assert await extractor.extract("hello") == []


# ---------------------------------------------------------------------------
# MemoryReconciler
# ---------------------------------------------------------------------------

async def test_reconciler_parses_operations(tmp_path):
    store = LocalMemoryStore(tmp_path / "mem.json")
    existing = await store.add("用户使用 unittest 写测试")
    provider = ScriptedProvider(
        [
            json.dumps(
                {
                    "operations": [
                        {"event": "UPDATE", "id": existing.id, "text": "用户使用 pytest 写测试"},
                        {"event": "ADD", "text": "项目使用 src layout"},
                        {"event": "DELETE", "id": "ghost"},
                        {"event": "BOGUS", "text": "ignored"},
                        {"event": "ADD"},  # missing text → skipped
                    ]
                }
            )
        ]
    )
    reconciler = MemoryReconciler(provider)
    ops = await reconciler.reconcile(["用户改用 pytest"], [existing])

    assert [op.event for op in ops] == ["UPDATE", "ADD", "DELETE"]
    assert ops[0].id == existing.id
    assert ops[0].text == "用户使用 pytest 写测试"


# ---------------------------------------------------------------------------
# SmartMemoryStore
# ---------------------------------------------------------------------------

async def test_smart_store_add_flow(tmp_path):
    store = LocalMemoryStore(tmp_path / "mem.json")
    provider = ScriptedProvider(
        [
            '{"facts": ["名字叫张三", "在小米工作"]}',          # extraction
            '{"operations": [{"event": "ADD", "text": "名字叫张三"},'
            ' {"event": "ADD", "text": "在小米工作"}]}',        # reconciliation
        ]
    )
    smart = SmartMemoryStore(store, provider)

    ops = await smart.add_with_operations("我的名字叫张三，我在小米工作")

    assert [op.event for op in ops] == ["ADD", "ADD"]
    contents = [m.content for m in await store.list()]
    assert "名字叫张三" in contents
    assert "在小米工作" in contents


async def test_smart_store_update_resolves_contradiction(tmp_path):
    store = LocalMemoryStore(tmp_path / "mem.json")
    existing = await store.add("用户偏好 unittest")
    provider = ScriptedProvider(
        [
            '{"facts": ["用户改用 pytest"]}',
            json.dumps(
                {"operations": [{"event": "UPDATE", "id": existing.id, "text": "用户偏好 pytest"}]}
            ),
        ]
    )
    smart = SmartMemoryStore(store, provider)

    await smart.add("用户现在改用 pytest 了")

    memories = await store.list()
    assert len(memories) == 1  # updated in place, not duplicated
    assert memories[0].content == "用户偏好 pytest"


async def test_smart_store_delete_flow(tmp_path):
    store = LocalMemoryStore(tmp_path / "mem.json")
    obsolete = await store.add("项目使用 Python 3.8")
    provider = ScriptedProvider(
        [
            '{"facts": ["项目不再支持 Python 3.8"]}',
            json.dumps({"operations": [{"event": "DELETE", "id": obsolete.id}]}),
        ]
    )
    smart = SmartMemoryStore(store, provider)

    await smart.add("项目已经放弃 Python 3.8 支持")

    assert await store.list() == []


async def test_smart_store_fallback_when_no_facts(tmp_path):
    store = LocalMemoryStore(tmp_path / "mem.json")
    provider = ScriptedProvider(['{"facts": []}'])
    smart = SmartMemoryStore(store, provider)

    memory = await smart.add("raw content worth keeping")

    assert memory.content == "raw content worth keeping"
    assert len(await store.list()) == 1


async def test_smart_store_is_drop_in_memory_store(tmp_path):
    """Works with memory_tools and Agent(memory=...) like any MemoryStore."""
    store = LocalMemoryStore(tmp_path / "mem.json")
    provider = ScriptedProvider(
        ['{"facts": ["偏好简洁回答"]}', '{"operations": [{"event": "ADD", "text": "偏好简洁回答"}]}']
    )
    smart = SmartMemoryStore(store, provider)

    save, search, _ = memory_tools(smart)
    out = await save.execute(content="我喜欢简洁的回答")
    assert "已保存记忆" in out
    found = await search.execute(query="简洁")
    assert "偏好简洁回答" in found

    # recall path used by Agent(memory=...)
    recalled = await smart.search("简洁")
    assert recalled and recalled[0].content == "偏好简洁回答"
