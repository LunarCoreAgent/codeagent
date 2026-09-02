"""Court: 三省六部 orchestration — plan → review(封驳) → execute → report."""

import json

import pytest

from codeagent import Court, ReviewRejectedError
from codeagent.core.types import LLMResponse
from codeagent.court import (
    DEFAULT_ROLES,
    IllegalTransitionError,
    TaskState,
    TaskStateMachine,
)
from codeagent.llm.base import LLMProvider


class ScriptedProvider(LLMProvider):
    """Returns canned responses in order; records system prompts."""

    name = "scripted"

    def __init__(self, responses: list[str]):
        super().__init__(model="scripted")
        self._responses = list(responses)
        self.systems: list[str] = []

    async def complete(self, messages, tools=None, system=None, **kwargs):
        self.systems.append(system or "")
        content = self._responses.pop(0) if self._responses else "{}"
        return LLMResponse(content=content)


PLAN = json.dumps({
    "subtasks": [
        {"dept": "bingbu", "title": "实现注册 API", "task": "用 FastAPI 实现注册接口"},
        {"dept": "libu", "title": "写文档", "task": "编写 API 文档"},
    ]
})
APPROVE = '{"verdict": "approve"}'
REJECT = '{"verdict": "reject", "feedback": "缺少安全审查环节"}'


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

def test_state_machine_rejects_illegal_transitions():
    sm = TaskStateMachine()
    with pytest.raises(IllegalTransitionError):
        sm.transition(TaskState.DOING)  # RECEIVED → DOING 非法
    sm.transition(TaskState.PLANNING)
    with pytest.raises(IllegalTransitionError):
        sm.transition(TaskState.DONE)  # PLANNING → DONE 跳过审议，非法
    assert sm.state is TaskState.PLANNING


def test_state_machine_legal_flow_with_rejection():
    sm = TaskStateMachine()
    sm.transition(TaskState.PLANNING)
    sm.transition(TaskState.REVIEWING)
    sm.transition(TaskState.REJECTED)      # 封驳
    sm.transition(TaskState.PLANNING)      # 打回重规划
    sm.transition(TaskState.REVIEWING)
    sm.transition(TaskState.DISPATCHED)    # 准奏
    sm.transition(TaskState.DOING)
    sm.transition(TaskState.REPORTING)
    sm.transition(TaskState.DONE)
    assert len(sm.history) == 10  # 初始 RECEIVED + 9 次流转


# ---------------------------------------------------------------------------
# Court workflow
# ---------------------------------------------------------------------------

async def test_court_full_pipeline(tmp_path):
    provider = ScriptedProvider([
        PLAN, APPROVE,              # 规划 → 一次准奏
        "注册接口已实现",            # 兵部
        "API 文档已完成",            # 礼部
        "回奏：全部完成",            # 尚书省汇总
    ])
    court = Court(provider, audit_path=tmp_path / "audit.jsonl")
    report = await court.run("给我做一个用户注册系统")

    assert report.review_rounds == 1
    assert [s.dept for s in report.plan] == ["bingbu", "libu"]
    assert all(r.ok for r in report.results)
    assert report.report == "回奏：全部完成"

    # 审计链完整：edict → plan → review → dispatch → result×2 → report
    kinds = [e.kind for e in report.audit.events]
    assert kinds == ["edict", "plan", "review", "dispatch", "result", "result", "report"]
    # JSONL 已落盘
    assert (tmp_path / "audit.jsonl").read_text().count("\n") == 7


async def test_court_rejection_forces_replan():
    provider = ScriptedProvider([
        PLAN, REJECT,               # 第一轮：封驳
        PLAN, APPROVE,              # 第二轮：重规划后准奏
        "完成 A", "完成 B",
        "回奏：完成",
    ])
    court = Court(provider)
    report = await court.run("做一个系统")

    assert report.review_rounds == 2
    reviews = report.audit.of_kind("review")
    assert reviews[0].detail["verdict"] == "reject"
    assert reviews[1].detail["verdict"] == "approve"
    # 封驳意见传给了中书省（规划两次；门下省 prompt 也提及中书省，需精确匹配）
    zhongshu_calls = [s for s in provider.systems if s.startswith("你是中书省")]
    assert len(zhongshu_calls) == 2


async def test_court_strict_review_raises():
    provider = ScriptedProvider([PLAN, REJECT, PLAN, REJECT])
    court = Court(provider, max_review_rounds=2, strict_review=True)
    with pytest.raises(ReviewRejectedError):
        await court.run("做一个系统")


async def test_court_lenient_override_proceeds():
    provider = ScriptedProvider([PLAN, REJECT, "完成 A", "完成 B", "回奏"])
    court = Court(provider, max_review_rounds=1, strict_review=False)
    report = await court.run("做一个系统")
    assert report.report == "回奏"
    assert report.audit.of_kind("review_override")


async def test_court_subtask_failure_isolated():
    provider = ScriptedProvider([
        PLAN, APPROVE,
        "完成 A",
        "完成 B",
        "回奏：部分完成",
    ])
    court = Court(provider)
    report = await court.run("做一个系统")
    assert len(report.results) == 2
    assert report.report == "回奏：部分完成"


async def test_court_bad_plan_json_falls_back_to_bingbu():
    provider = ScriptedProvider([
        "这不是 JSON", APPROVE, "整旨完成", "回奏",
    ])
    court = Court(provider)
    report = await court.run("随便做点啥")
    assert report.plan[0].dept == "bingbu"  # 兜底部门
    assert report.results[0].ok


def test_default_roles_cover_three_departments_and_six_ministries():
    for name in ("zhongshu", "menxia", "shangshu", "hubu", "libu",
                 "bingbu", "xingbu", "gongbu"):
        assert name in DEFAULT_ROLES
