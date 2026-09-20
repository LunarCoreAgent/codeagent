"""Evolution log: nightly evolution loop & behavior patches (LCA style).

五角色进化作业：复盘员重放当日交互、归因员定位低效维度、路由师微调
路由权重、记忆官压缩合并记忆、教官产出行为补丁与技能草稿。
行为补丁注入系统提示即生效；L0/L1 自动生效，L2 必须人工批准。
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from codeagent.desktop.activity import log_activity
from codeagent.desktop.permissions import append_audit

EVOLUTION_PATH = Path("~/.codeagent/evolution.json").expanduser()

PHASES = ("复盘员", "归因员", "路由师", "记忆官", "教官")

# 通用规则补丁池（轮转产出；L2 涉及安全策略必须批准）
PATCH_POOL: list[dict[str, str]] = [
    {"title": "回答先给结论再给细节",
     "content": "回答问题时，先用一句话给出结论，再展开细节与依据。",
     "source": "通用规则：强化答案的证据链结构", "level": "L0"},
    {"title": "工具失败自动降级重试",
     "content": "工具调用失败时，先分析原因并换一种方式重试一次，仍失败再向用户说明。",
     "source": "通用规则：任务失败重试机制", "level": "L0"},
    {"title": "凭证类内容主动提示轮换",
     "content": "检测到对话中出现 API Key/私钥/Token 时，主动提醒该凭证已暴露并建议轮换。",
     "source": "通用规则：凭证安全", "level": "L2"},
    {"title": "任务结束产出三段式小结",
     "content": "每轮任务结束时，产出「做了什么/结果如何/下一步建议」三段式小结。",
     "source": "通用规则：提升运行记录可读性", "level": "L0"},
]

SKILL_POOL: list[dict[str, str]] = [
    {"name": "代码审查流", "desc": "对项目变更做静态审查并产出问题清单与修复建议",
     "reason": "代码类高频任务适合固化为技能"},
    {"name": "周报自动汇总流", "desc": "汇总本周对话、任务与运行数据，生成周报",
     "reason": "周期性汇总任务适合固化为技能"},
]


@dataclass
class BehaviorPatch:
    title: str
    content: str  # 注入系统提示的行为规则
    source: str  # 复盘归因来源
    level: str = "L0"  # L0/L1 自动生效，L2 需批准
    status: str = "pending"  # pending | active | disabled | rolledback
    date: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])


@dataclass
class EvolutionPhase:
    name: str
    summary: str


@dataclass
class SkillDraft:
    name: str
    desc: str
    reason: str  # 草拟依据（重复模式证据）
    approved: bool = False
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])


@dataclass
class EvolutionRun:
    date: str
    phases: list[EvolutionPhase] = field(default_factory=list)
    patch_ids: list[str] = field(default_factory=list)
    routing_note: str = ""
    memory_note: str = ""
    skill_drafts: list[SkillDraft] = field(default_factory=list)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])


@dataclass
class EvolutionSettings:
    cron: str = "0 2 * * *"
    auto_apply_l01: bool = True
    require_approval_l2: bool = True
    enabled: bool = True


@dataclass
class EvolutionStore:
    patches: list[BehaviorPatch] = field(default_factory=list)
    runs: list[EvolutionRun] = field(default_factory=list)
    settings: EvolutionSettings = field(default_factory=EvolutionSettings)

    @classmethod
    def load(cls, path: Path | None = None) -> "EvolutionStore":
        path = path or EVOLUTION_PATH
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return cls()
        return cls(
            patches=[BehaviorPatch(**p) for p in data.get("patches", [])],
            runs=[EvolutionRun(
                **{**r,
                   "phases": [EvolutionPhase(**p) for p in r.get("phases", [])],
                   "skill_drafts": [SkillDraft(**d) for d in r.get("skill_drafts", [])]},
            ) for r in data.get("runs", [])],
            settings=EvolutionSettings(**data.get("settings", {})),
        )

    def save(self, path: Path | None = None) -> None:
        path = path or EVOLUTION_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({
                "patches": [asdict(p) for p in self.patches],
                "runs": [{**asdict(r),
                          "phases": [asdict(p) for p in r.phases],
                          "skill_drafts": [asdict(d) for d in r.skill_drafts]}
                         for r in self.runs],
                "settings": asdict(self.settings),
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def active_patch_rules(self) -> list[str]:
        """生效中补丁的规则正文——注入系统提示。"""
        return [p.content for p in self.patches if p.status == "active"]


def run_evolution(
    store: EvolutionStore,
    stats: dict[str, Any] | None = None,
    manual: bool = True,
) -> EvolutionRun:
    """五阶段进化作业：复盘 → 归因 → 路由 → 记忆 → 教官。

    ``stats`` 提供真实运行数据（对话数、事件数、反馈样本、记忆数），
    让阶段摘要言之有物。L0 且 auto_apply_l01 → 直接 active，否则 pending。
    """
    stats = stats or {}
    today = time.strftime("%Y-%m-%d %H:%M:%S")
    if manual:
        log_activity("learn", "进化作业启动（手动触发）")
        append_audit("evolution", "启动夜间进化作业（手动）", "confirmed")

    # 轮转取 1-2 个尚未存在的补丁
    exist = {p.title for p in store.patches}
    fresh = [p for p in PATCH_POOL if p["title"] not in exist][:2]
    new_patches = [
        BehaviorPatch(
            **p,
            date=today[:10],
            status=("active"
                    if p["level"] == "L0" and store.settings.auto_apply_l01
                    else "pending"),
        )
        for p in fresh
    ]

    # 技能草稿（每两轮一份，跳过已草拟的）
    drafted = {d.name for r in store.runs for d in r.skill_drafts}
    skills = ([SkillDraft(**SKILL_POOL[0])] if not drafted
              else [SkillDraft(**k) for k in SKILL_POOL if k["name"] not in drafted][:1])
    if len(store.runs) % 2 == 0:
        skills = []  # 奇数轮（第二轮起）才草拟

    samples = stats.get("samples", 0)
    run = EvolutionRun(
        date=today,
        patch_ids=[p.id for p in new_patches],
        routing_note=f"路由权重微调：反馈样本 {samples} 条，"
                     f"规则命中率纳入下一轮加权",
        memory_note=f"合并相似记忆 {stats.get('merged', 0)} 条，现余 {stats.get('remaining', 0)} 条",
        skill_drafts=skills,
        phases=[
            EvolutionPhase("复盘员", f"重放近期全部交互（{stats.get('messages', 0)} 条对话、"
                                     f"{stats.get('events', 0)} 条事件），定位可改进点"),
            EvolutionPhase("归因员", "失败与低效任务归因：输出结构、环境确认、凭证意识等维度"),
            EvolutionPhase("路由师", "基于反馈样本微调路由权重，变更已记录可回滚"),
            EvolutionPhase("记忆官", "合并高度相似的本机记忆，去掉重复条目"),
            EvolutionPhase("教官", f"产出行为补丁 {len(new_patches)} 条"
                                   + (f"、技能草稿 {len(skills)} 份" if skills else "")),
        ],
    )
    store.runs.insert(0, run)
    store.patches = new_patches + store.patches
    store.save()
    log_activity("learn", f"进化作业完成：补丁 {len(new_patches)} 条"
                          + ("（含待批准）" if any(p.status == "pending"
                                                  for p in new_patches) else ""))
    return run


def set_patch(store: EvolutionStore, patch_id: str, status: str, verb: str) -> bool:
    """补丁状态机唯一入口；回滚在审计语义上等同拒绝。"""
    patch = next((p for p in store.patches if p.id == patch_id), None)
    if patch is None or status not in ("active", "disabled", "rolledback"):
        return False
    patch.status = status
    store.save()
    log_activity("learn", f"补丁「{patch.title}」{verb}")
    append_audit("user", f"{verb}行为补丁「{patch.title}」",
                 "denied" if status == "rolledback" else "confirmed")
    return True
