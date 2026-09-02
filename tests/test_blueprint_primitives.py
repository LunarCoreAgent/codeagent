"""HomeRail-style primitives: join quorum, loop, while, command, YAML, scorecard."""

import pytest

from codeagent import (
    Blueprint,
    BlueprintRunner,
    BlueprintSpecError,
    Edge,
    Node,
    NodeKind,
    load_blueprint_yaml,
    parse_blueprint,
)
from codeagent.core.types import LLMResponse
from codeagent.llm.base import LLMProvider


class ScriptedProvider(LLMProvider):
    name = "scripted"

    def __init__(self, responses: list[str]):
        super().__init__(model="scripted")
        self._responses = list(responses)

    async def complete(self, messages, tools=None, system=None, **kwargs):
        content = self._responses.pop(0) if self._responses else "ok"
        return LLMResponse(content=content)


def agent(node_id: str) -> Node:
    return Node(id=node_id, kind=NodeKind.AGENT)


# ---------------------------------------------------------------------------
# JOIN quorum
# ---------------------------------------------------------------------------


async def test_join_all_requires_every_upstream():
    """join mode=all skips when any upstream was rejected."""
    bp = Blueprint(
        [
            Node("gate", NodeKind.APPROVAL),
            agent("work"),
            Node("join", NodeKind.JOIN, config={"mode": "all"}),
        ],
        [Edge("gate", "join"), Edge("work", "join")],
    )
    provider = ScriptedProvider(["work output"])
    runner = BlueprintRunner(
        provider, bp, approval_handler=lambda n, o: _reject()
    )
    report = await runner.run("task")
    assert report.results["join"].status == "skipped"  # gate rejected → quorum fails


async def test_join_any_admits_with_one_done():
    bp = Blueprint(
        [
            Node("gate", NodeKind.APPROVAL),
            agent("work"),
            Node("join", NodeKind.JOIN, config={"mode": "any"}),
        ],
        [Edge("gate", "join"), Edge("work", "join")],
    )
    provider = ScriptedProvider(["work output"])
    runner = BlueprintRunner(provider, bp, approval_handler=lambda n, o: _reject())
    report = await runner.run("task")
    assert report.results["join"].status == "done"
    assert "work output" in report.results["join"].output


async def test_join_n_of_m_quorum():
    nodes = [agent("a"), agent("b"), agent("c")]
    nodes.append(Node("join", NodeKind.JOIN, config={"mode": "n_of_m", "threshold": 2}))
    bp = Blueprint(nodes, [Edge("a", "join"), Edge("b", "join"), Edge("c", "join")])
    provider = ScriptedProvider(["ra", "rb", "rc"])
    report = await BlueprintRunner(provider, bp).run("task")
    assert report.results["join"].status == "done"
    assert report.scorecard(bp)["nodes_done"] == 4


def _reject():
    from codeagent import ApprovalResult

    return ApprovalResult(approved=False)


# ---------------------------------------------------------------------------
# LOOP / WHILE
# ---------------------------------------------------------------------------


async def test_loop_collects_every_iteration():
    bp = Blueprint(
        [Node("refine", NodeKind.LOOP, prompt="Improve: {inputs}", config={"max_iterations": 3})],
        [],
    )
    provider = ScriptedProvider(["v1", "v2", "v3"])
    report = await BlueprintRunner(provider, bp).run("draft")
    out = report.results["refine"].output
    assert "[iteration 1]" in out and "[iteration 3]" in out
    assert "v1" in out and "v3" in out
    assert report.attempts["refine"] == 3


async def test_while_stops_when_llm_says_done():
    bp = Blueprint(
        [Node("polish", NodeKind.WHILE, prompt="Polish: {inputs}", config={"max_iterations": 5})],
        [],
    )
    # iteration 1 → CONTINUE, iteration 2 → DONE
    provider = ScriptedProvider(["p1", "CONTINUE", "p2", "DONE"])
    report = await BlueprintRunner(provider, bp).run("text")
    assert report.attempts["polish"] == 2
    assert "p2" in report.results["polish"].output


# ---------------------------------------------------------------------------
# COMMAND
# ---------------------------------------------------------------------------


async def test_command_runs_allowlisted_argv():
    bp = Blueprint(
        [Node("check", NodeKind.COMMAND, config={"argv": ["echo", "hello-blueprint"]})],
        [],
    )
    runner = BlueprintRunner(ScriptedProvider([]), bp, command_allowlist=["echo"])
    report = await runner.run("task")
    assert report.results["check"].status == "done"
    assert "hello-blueprint" in report.results["check"].output


async def test_command_denied_when_not_allowlisted():
    bp = Blueprint(
        [Node("evil", NodeKind.COMMAND, config={"argv": ["rm", "-rf", "/"]})],
        [],
    )
    runner = BlueprintRunner(ScriptedProvider([]), bp)  # empty allowlist
    report = await runner.run("task")
    assert report.results["evil"].status == "rejected"
    assert "not in allowlist" in report.results["evil"].output


# ---------------------------------------------------------------------------
# per-node providers
# ---------------------------------------------------------------------------


async def test_per_node_provider_mapping():
    class SpyProvider(ScriptedProvider):
        def __init__(self, tag, responses):
            super().__init__(responses)
            self.tag = tag
            self.calls = 0

        async def complete(self, messages, tools=None, system=None, **kwargs):
            self.calls += 1
            return await super().complete(messages, tools, system, **kwargs)

    bp = Blueprint([agent("planner"), agent("worker")], [Edge("planner", "worker")])
    brain = SpyProvider("brain", ["plan"])
    hands = SpyProvider("hands", ["result"])
    default = SpyProvider("default", ["unused"])
    runner = BlueprintRunner(
        default, bp, providers={"planner": brain, "*": hands}
    )
    report = await runner.run("task")
    assert brain.calls == 1 and hands.calls == 1 and default.calls == 0
    assert report.results["worker"].output == "result"


# ---------------------------------------------------------------------------
# scorecard
# ---------------------------------------------------------------------------


async def test_scorecard_contents():
    bp = Blueprint([agent("a"), agent("b")], [Edge("a", "b")])
    report = await BlueprintRunner(ScriptedProvider(["1", "2"]), bp).run("task")
    card = report.scorecard(bp)
    assert card["nodes_total"] == 2
    assert card["nodes_done"] == 2
    assert card["success_rate"] == 1.0
    assert card["nodes"]["a"]["kind"] == "agent"
    assert "tokens" in card


# ---------------------------------------------------------------------------
# YAML loader (strict)
# ---------------------------------------------------------------------------


def test_yaml_loader_roundtrip():
    text = """
name: release-flow
nodes:
  - id: plan
    kind: agent
    label: 规划
    prompt: "规划：{task}"
  - id: gate
    kind: approval
  - id: ship
    kind: command
    config:
      argv: ["echo", "shipped"]
edges:
  - source: plan
    target: gate
  - source: gate
    target: ship
"""
    bp = load_blueprint_yaml(text)
    assert bp.name == "release-flow"
    assert bp.nodes["ship"].kind == NodeKind.COMMAND
    assert bp.nodes["ship"].config["argv"] == ["echo", "shipped"]
    assert bp.downstream("gate") == ["ship"]


def test_yaml_loader_rejects_unknown_top_level_field():
    with pytest.raises(BlueprintSpecError, match="unknown field"):
        parse_blueprint({"name": "x", "nodse": [], "nodes": [{"id": "a"}]})


def test_yaml_loader_rejects_unknown_node_field():
    with pytest.raises(BlueprintSpecError, match="unknown field"):
        parse_blueprint({"nodes": [{"id": "a", "kind": "agent", "promt": "typo"}]})


def test_yaml_loader_rejects_unknown_kind():
    with pytest.raises(BlueprintSpecError, match="unknown kind"):
        parse_blueprint({"nodes": [{"id": "a", "kind": "magic"}]})


def test_yaml_loader_rejects_cycle():
    with pytest.raises(BlueprintSpecError, match="cycle"):
        parse_blueprint(
            {
                "nodes": [{"id": "a"}, {"id": "b"}],
                "edges": [{"source": "a", "target": "b"}, {"source": "b", "target": "a"}],
            }
        )
