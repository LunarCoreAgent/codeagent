"""Blueprint: DAG validation, parallel execution, routing, approval gates."""

import pytest

from codeagent import (
    ApprovalResult,
    Blueprint,
    BlueprintRunner,
    CycleError,
    Edge,
    Node,
    NodeKind,
)
from codeagent.core.types import LLMResponse
from codeagent.llm.base import LLMProvider


class ScriptedProvider(LLMProvider):
    name = "scripted"

    def __init__(self, responses: list[str]):
        super().__init__(model="scripted")
        self._responses = list(responses)
        self.prompts: list[str] = []

    async def complete(self, messages, tools=None, system=None, **kwargs):
        self.prompts.append(messages[-1].content)
        content = self._responses.pop(0) if self._responses else "ok"
        return LLMResponse(content=content)


def agent_node(node_id: str, label: str = "") -> Node:
    return Node(id=node_id, kind=NodeKind.AGENT, label=label or node_id)


# ---------------------------------------------------------------------------
# graph validation
# ---------------------------------------------------------------------------


def test_blueprint_rejects_duplicate_node_ids():
    with pytest.raises(ValueError, match="duplicate node id"):
        Blueprint([agent_node("a"), agent_node("a")], [])


def test_blueprint_rejects_dangling_edge():
    with pytest.raises(ValueError, match="not a node"):
        Blueprint([agent_node("a")], [Edge("a", "ghost")])


def test_blueprint_rejects_cycles():
    nodes = [agent_node("a"), agent_node("b")]
    edges = [Edge("a", "b"), Edge("b", "a")]
    with pytest.raises(CycleError):
        Blueprint(nodes, edges)


def test_topo_levels_group_parallel_nodes():
    bp = Blueprint(
        [agent_node("root"), agent_node("x"), agent_node("y"), agent_node("join")],
        [Edge("root", "x"), Edge("root", "y"), Edge("x", "join"), Edge("y", "join")],
    )
    levels = bp.topo_levels()
    assert levels[0] == ["root"]
    assert sorted(levels[1]) == ["x", "y"]
    assert levels[2] == ["join"]
    assert bp.roots() == ["root"]
    assert bp.leaves() == ["join"]


# ---------------------------------------------------------------------------
# execution
# ---------------------------------------------------------------------------


async def test_linear_flow_passes_output_downstream():
    bp = Blueprint(
        [agent_node("a"), agent_node("b")],
        [Edge("a", "b")],
    )
    provider = ScriptedProvider(["draft", "final"])
    report = await BlueprintRunner(provider, bp).run("write something")
    assert report.results["a"].output == "draft"
    assert report.results["b"].output == "final"
    # node b received node a's output as input
    assert "[a]" in provider.prompts[1]
    assert "draft" in provider.prompts[1]
    assert report.final_output(bp) == "final"


async def test_parallel_slots_and_aggregate():
    bp = Blueprint(
        [
            agent_node("root"),
            Node(id="s1", kind=NodeKind.SLOT, label="slot1"),
            Node(id="s2", kind=NodeKind.SLOT, label="slot2"),
            Node(id="agg", kind=NodeKind.AGGREGATE),
        ],
        [Edge("root", "s1"), Edge("root", "s2"), Edge("s1", "agg"), Edge("s2", "agg")],
    )
    provider = ScriptedProvider(["plan", "result-1", "result-2"])
    report = await BlueprintRunner(provider, bp).run("task")
    assert report.results["s1"].status == "done"
    assert report.results["s2"].status == "done"
    # aggregate without prompt joins upstream outputs directly (no LLM call)
    assert "result-1" in report.results["agg"].output
    assert "result-2" in report.results["agg"].output


async def test_condition_routes_to_one_branch():
    bp = Blueprint(
        [
            agent_node("start"),
            Node(id="cond", kind=NodeKind.CONDITION),
            agent_node("simple"),
            agent_node("hard"),
        ],
        [
            Edge("start", "cond"),
            Edge("cond", "simple", label="simple"),
            Edge("cond", "hard", label="hard"),
        ],
    )
    provider = ScriptedProvider(["analysis", "simple", "handled simply"])
    report = await BlueprintRunner(provider, bp).run("fix typo")
    assert report.results["simple"].status == "done"
    assert report.results["hard"].status == "skipped"
    assert report.results["cond"].branches == ["simple"]


async def test_condition_garbage_reply_keeps_flow_alive():
    bp = Blueprint(
        [Node(id="cond", kind=NodeKind.CONDITION), agent_node("a"), agent_node("b")],
        [Edge("cond", "a", label="A"), Edge("cond", "b", label="B")],
    )
    provider = ScriptedProvider(["I have no idea"])
    report = await BlueprintRunner(provider, bp).run("task")
    assert report.results["a"].status == "done"  # falls back to first branch
    assert report.results["b"].status == "skipped"


async def test_manager_activates_multiple_branches():
    bp = Blueprint(
        [
            agent_node("start"),
            Node(id="mgr", kind=NodeKind.MANAGER),
            agent_node("x"),
            agent_node("y"),
            agent_node("z"),
        ],
        [
            Edge("start", "mgr"),
            Edge("mgr", "x", label="x"),
            Edge("mgr", "y", label="y"),
            Edge("mgr", "z", label="z"),
        ],
    )
    provider = ScriptedProvider(["brief", "x\ny", "out-x", "out-y"])
    report = await BlueprintRunner(provider, bp).run("task")
    assert report.results["x"].status == "done"
    assert report.results["y"].status == "done"
    assert report.results["z"].status == "skipped"


# ---------------------------------------------------------------------------
# approval gates
# ---------------------------------------------------------------------------


async def test_approval_reject_skips_downstream():
    bp = Blueprint(
        [agent_node("work"), Node(id="gate", kind=NodeKind.APPROVAL), agent_node("ship")],
        [Edge("work", "gate"), Edge("gate", "ship")],
    )
    provider = ScriptedProvider(["risky change"])
    runner = BlueprintRunner(
        provider, bp, approval_handler=lambda node, out: ApprovalResult(approved=False)
    )
    report = await runner.run("deploy")
    assert report.results["gate"].status == "rejected"
    assert report.results["ship"].status == "skipped"


async def test_approval_reply_replaces_output():
    bp = Blueprint(
        [agent_node("work"), Node(id="gate", kind=NodeKind.APPROVAL), agent_node("ship")],
        [Edge("work", "gate"), Edge("gate", "ship")],
    )
    provider = ScriptedProvider(["draft plan", "shipped"])
    runner = BlueprintRunner(
        provider,
        bp,
        approval_handler=lambda node, out: ApprovalResult(approved=True, reply="human-edited plan"),
    )
    report = await runner.run("deploy")
    assert report.results["gate"].output == "human-edited plan"
    assert "human-edited plan" in provider.prompts[-1]


async def test_approval_auto_approves_without_handler():
    bp = Blueprint(
        [Node(id="gate", kind=NodeKind.APPROVAL), agent_node("next")],
        [Edge("gate", "next")],
    )
    provider = ScriptedProvider(["continued"])
    report = await BlueprintRunner(provider, bp).run("task")
    assert report.results["gate"].status == "done"
    assert report.results["next"].status == "done"


# ---------------------------------------------------------------------------
# misc
# ---------------------------------------------------------------------------


async def test_usage_is_tracked():
    bp = Blueprint([agent_node("a"), agent_node("b")], [Edge("a", "b")])
    provider = ScriptedProvider(["one", "two"])
    report = await BlueprintRunner(provider, bp).run("task")
    assert report.usage.output_tokens >= 0  # ScriptedProvider reports zero; just assert plumbing


async def test_audit_log_receives_events(tmp_path):
    from codeagent.court.audit import AuditLog

    log = AuditLog(tmp_path / "audit.jsonl")
    bp = Blueprint([agent_node("a")], [])
    provider = ScriptedProvider(["done"])
    await BlueprintRunner(provider, bp, audit=log).run("task")
    lines = (tmp_path / "audit.jsonl").read_text().strip().splitlines()
    kinds = [line for line in lines]
    assert any("blueprint_start" in k for k in kinds)
    assert any("node_done" in k for k in kinds)
    assert any("blueprint_done" in k for k in kinds)
