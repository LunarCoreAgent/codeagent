"""Memory system tests: long-term store, tools, compaction, agent integration."""

from codeagent import (
    Agent,
    CompactionConfig,
    ConversationCompactor,
    LocalMemoryStore,
    memory_tools,
)
from codeagent.core.types import LLMResponse, Message, ToolCall, Usage
from codeagent.llm.base import LLMProvider


# ---------------------------------------------------------------------------
# LocalMemoryStore
# ---------------------------------------------------------------------------

async def test_store_add_search_list_delete(tmp_path):
    store = LocalMemoryStore(tmp_path / "mem.json")
    await store.add("用户偏好用 pytest 而不是 unittest")
    await store.add("the API base URL is https://api.example.com")
    await store.add("项目使用 src layout 结构")

    results = await store.search("pytest 偏好")
    assert results and "pytest" in results[0].content

    results = await store.search("API URL")
    assert results[0].content.startswith("the API base URL")

    all_memories = await store.list()
    assert len(all_memories) == 3

    deleted = await store.delete(results[0].id)
    assert deleted
    assert len(await store.list()) == 2
    assert not await store.delete("nonexistent")


async def test_store_list_filters_kinds(tmp_path):
    store = LocalMemoryStore(tmp_path / "mem.json")
    await store.add("用户：hi\n助手：hello", {"kind": "turn"})
    await store.add("手动事实", {"kind": "fact"})
    turns = await store.list(limit=10, kinds=("turn",))
    assert len(turns) == 1
    assert "hi" in turns[0].content


async def test_store_persists_across_instances(tmp_path):
    path = tmp_path / "mem.json"
    store = LocalMemoryStore(path)
    await store.add("persistent fact", {"tags": ["test"]})

    reloaded = LocalMemoryStore(path)
    memories = await reloaded.list()
    assert len(memories) == 1
    assert memories[0].content == "persistent fact"
    assert memories[0].metadata["tags"] == ["test"]


async def test_store_search_no_overlap_returns_empty(tmp_path):
    store = LocalMemoryStore(tmp_path / "mem.json")
    await store.add("something about databases")
    assert await store.search("zzzzz") == []


# ---------------------------------------------------------------------------
# Memory tools
# ---------------------------------------------------------------------------

async def test_memory_tools_roundtrip(tmp_path):
    store = LocalMemoryStore(tmp_path / "mem.json")
    save, search, list_ = memory_tools(store)

    out = await save.execute(content="remember this fact", tags="demo, test")
    assert "已保存记忆" in out

    found = await search.execute(query="fact")
    assert "remember this fact" in found

    listed = await list_.execute()
    assert "remember this fact" in listed

    empty = await search.execute(query="qqqqq")
    assert "没有匹配的记忆" in empty


# ---------------------------------------------------------------------------
# ConversationCompactor
# ---------------------------------------------------------------------------

class FakeProvider(LLMProvider):
    name = "fake"

    def __init__(self, responses):
        super().__init__(model="fake")
        self._responses = list(responses)
        self.requests: list[list[Message]] = []
        self.seen_system_prompts: list[str] = []

    async def complete(self, messages, tools=None, system=None, **kwargs):
        self.requests.append(list(messages))
        self.seen_system_prompts.append(system or "")
        if not self._responses:
            return LLMResponse(content="done")
        return self._responses.pop(0)


def _make_history(n: int) -> list[Message]:
    return [Message.user(f"message {i}") for i in range(n)]


async def test_compactor_leaves_short_history_untouched():
    provider = FakeProvider([])
    compactor = ConversationCompactor(provider, CompactionConfig(max_messages=10, keep_recent=3))
    history = _make_history(5)
    assert await compactor.maybe_compact(history) is history


async def test_compactor_summarizes_old_messages():
    provider = FakeProvider([LLMResponse(content="用户在做代码重构，已完成 A 模块")])
    compactor = ConversationCompactor(provider, CompactionConfig(max_messages=6, keep_recent=2))
    history = _make_history(10)

    compacted = await compactor.maybe_compact(history)

    assert len(compacted) == 3  # 1 summary + 2 recent
    assert compacted[0].content.startswith("[Summary of earlier conversation")
    assert "代码重构" in compacted[0].content
    assert compacted[-1].content == "message 9"
    # the summarization call received the old transcript
    summary_request = provider.requests[0]
    assert "message 0" in summary_request[0].content
    assert "message 7" in summary_request[0].content


# ---------------------------------------------------------------------------
# Agent integration
# ---------------------------------------------------------------------------

async def test_agent_injects_recalled_memories(tmp_path):
    store = LocalMemoryStore(tmp_path / "mem.json")
    await store.add("用户偏好简洁的回答风格")

    provider = FakeProvider([LLMResponse(content="ok")])
    agent = Agent(provider=provider, memory=store)
    await agent.run("告诉我关于偏好的设置")

    system_prompt = provider.seen_system_prompts[0]
    assert "[相关记忆" in system_prompt
    assert "用户偏好简洁的回答风格" in system_prompt


async def test_agent_injects_recent_turns_first(tmp_path):
    store = LocalMemoryStore(tmp_path / "mem.json")
    await store.add("用户：上一轮在做什么\n助手：在改记忆", {"kind": "turn", "source": "auto"})
    provider = FakeProvider([LLMResponse(content="ok")])
    agent = Agent(provider=provider, memory=store, system_prompt="BASE")
    await agent.run("zzzzz")
    prompt = provider.seen_system_prompts[0]
    assert "最近 5 条对话记忆" in prompt
    assert "上一轮在做什么" in prompt


async def test_agent_without_matching_memories_injects_nothing(tmp_path):
    store = LocalMemoryStore(tmp_path / "mem.json")
    await store.add("databases use connection pooling")

    provider = FakeProvider([LLMResponse(content="ok")])
    agent = Agent(provider=provider, memory=store, system_prompt="BASE")
    await agent.run("zzzzz")

    assert provider.seen_system_prompts[0] == "BASE"


async def test_agent_clears_stale_memory_context(tmp_path):
    store = LocalMemoryStore(tmp_path / "mem.json")
    await store.add("用户偏好简洁的回答风格")
    provider = FakeProvider([LLMResponse(content="ok"), LLMResponse(content="ok")])
    agent = Agent(provider=provider, memory=store, system_prompt="BASE")
    await agent.run("告诉我关于偏好的设置")
    assert "用户偏好简洁的回答风格" in provider.seen_system_prompts[0]
    await agent.run("zzzzz")
    assert "相关记忆" not in provider.seen_system_prompts[1]


async def test_agent_run_memory_query_overrides_task(tmp_path):
    store = LocalMemoryStore(tmp_path / "mem.json")
    await store.add("用户偏好 pytest")
    provider = FakeProvider([LLMResponse(content="ok")])
    agent = Agent(provider=provider, memory=store, system_prompt="BASE")
    await agent.run("zzzzz unrelated", memory_query="偏好")
    assert "pytest" in provider.seen_system_prompts[0]


async def test_store_search_matches_tags(tmp_path):
    store = LocalMemoryStore(tmp_path / "mem.json")
    await store.add("一条无关内容", {"tags": ["pytest偏好"]})
    found = await store.search("pytest")
    assert found and found[0].content == "一条无关内容"


def test_memory_save_is_readonly_risk():
    from codeagent.memory.tools import MemorySaveTool
    from codeagent.security.policy import RiskLevel

    assert MemorySaveTool.risk_level == RiskLevel.READ_ONLY


async def test_agent_memory_query_ignores_conversation_seed(tmp_path):
    store = LocalMemoryStore(tmp_path / "mem.json")
    await store.add("用户偏好 pytest")
    provider = FakeProvider([LLMResponse(content="ok")])
    agent = Agent(provider=provider, memory=store, system_prompt="BASE")
    seeded = "（本会话之前的对话记录）\n用户: 讲数据库\n\n（用户新消息）\n偏好怎么配"
    await agent.run(seeded)
    assert "pytest" in provider.seen_system_prompts[0]


async def test_store_update_and_consolidate(tmp_path):
    store = LocalMemoryStore(tmp_path / "mem.json")
    first = await store.add("用户喜欢用 pytest 写测试")
    await store.add("用户喜欢用 pytest 写测试。")
    updated = await store.update(first.id, "用户喜欢用 pytest 和 tmp_path")
    assert updated is not None
    assert updated.content.endswith("tmp_path")
    result = await store.consolidate(threshold=0.5)
    assert result["remaining"] >= 1
    assert result["merged"] >= 0


async def test_store_reload_sees_other_instance_writes(tmp_path):
    path = tmp_path / "mem.json"
    a = LocalMemoryStore(path)
    b = LocalMemoryStore(path)
    await a.add("从另一实例写入的事实")
    found = await b.search("另一实例")
    assert found and "另一实例" in found[0].content


async def test_agent_compacts_during_run():
    responses = [LLMResponse(content=f"turn {i}") for i in range(5)]
    provider = FakeProvider(responses)
    compactor = ConversationCompactor(provider, CompactionConfig(max_messages=4, keep_recent=1))
    agent = Agent(provider=provider, compactor=compactor)

    await agent.run("task one")
    # after several runs the history would exceed max_messages; compaction
    # replaces old turns with a single summary message
    await agent.run("task two")
    await agent.run("task three")

    summary_messages = [
        m for m in agent.messages if m.content.startswith("[Summary of earlier conversation")
    ]
    assert summary_messages, "history was never compacted"
