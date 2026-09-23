"""Post-write code audit by a second model (different from the writer)."""

from __future__ import annotations

AUDIT_CLEAN_MARKERS = (
    "未发现错误",
    "未发现明显错误",
    "没有发现错误",
    "无明显问题",
    "通过审计",
    "审计通过",
    "no issues found",
    "looks good",
    "lgtm",
)

AUDIT_ISSUE_MARKERS = (
    "错误",
    "bug",
    "缺陷",
    "漏洞",
    "必须修复",
    "需要修复",
    "严重",
    "syntax",
    "exception",
    "crash",
    "fail",
)


def build_audit_prompt(paths: list[str], task: str = "") -> str:
    """Prompt for a read-only auditor model after project code was written."""
    listed = "\n".join(f"- {p}" for p in paths[:40])
    context = (task or "").strip()
    if len(context) > 600:
        context = context[:600] + "…"
    return (
        "你是代码审计员，不是原作者。请只读检查刚写入/修改的项目代码，找出真实错误。\n"
        "重点：语法错误、明显逻辑 bug、路径/导入错误、空指针/未定义、安全问题、"
        "与任务不符的破坏性改动。\n"
        "不要重写整文件；不要夸大风格偏好。\n"
        "请用工具读取下列文件（必要时再读相关依赖），然后给出结论。\n\n"
        f"本轮用户任务摘要：{context or '（无）'}\n\n"
        f"变更文件：\n{listed}\n\n"
        "输出格式：\n"
        "1) 若无明显错误：第一行写「审计通过：未发现错误」，可附一句说明。\n"
        "2) 若有问题：先列「发现问题」，每条含文件路径、问题、为何错、建议改法；"
        "最后给出「必须修复」清单。"
    )


def build_repair_prompt(audit: str, paths: list[str]) -> str:
    listed = "、".join(paths[:20])
    return (
        "另一个模型已完成代码审计，发现需要修复的问题。"
        "请只修改相关文件，修好后用简短中文说明改了什么。\n"
        f"涉及文件：{listed}\n\n"
        f"审计报告：\n{audit.strip()}"
    )


def audit_needs_repair(report: str) -> bool:
    """Heuristic: does the auditor report say we must fix something?"""
    text = (report or "").strip()
    if not text:
        return False
    low = text.lower()
    head = text[:80]
    if any(m in head for m in AUDIT_CLEAN_MARKERS) or any(
        m in low[:120] for m in ("no issues found", "looks good", "lgtm")
    ):
        return False
    if "审计通过" in head or "未发现错误" in head or "未发现明显错误" in head:
        return False
    if "必须修复" in text or "发现问题" in text[:200]:
        return True
    return any(m in text for m in ("错误：", "Bug", "bug：", "缺陷："))


def clip_audit_report(report: str, limit: int = 4000) -> str:
    text = (report or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def pick_auditor_ref(
    preferred_model: str,
    *,
    audit_ref: str = "",
    mixture_members: list[str] | None = None,
    mixture_fallback: str = "",
    api_ids: list[str] | None = None,
    local_refs: list[str] | None = None,
) -> str:
    """Choose a model ref different from the writer when possible."""
    pinned = (audit_ref or "").strip()
    if pinned:
        return pinned
    preferred = (preferred_model or "").strip().lower()
    candidates: list[str] = []
    for ref in mixture_members or []:
        if ref:
            candidates.append(ref)
    if mixture_fallback:
        candidates.append(mixture_fallback)
    for aid in api_ids or []:
        candidates.append(f"api:{aid}")
    for ref in local_refs or []:
        if ref:
            candidates.append(ref)

    def model_of(ref: str) -> str:
        if ref.startswith("local:") and "@" in ref:
            return ref[6:].rsplit("@", 1)[0].lower()
        if ref.startswith("api:"):
            return ref.lower()
        return ref.lower()

    for ref in candidates:
        if preferred and preferred in model_of(ref):
            continue
        if preferred and model_of(ref) == preferred:
            continue
        return ref
    return candidates[0] if candidates else ""


def format_audit_block(report: str, auditor_label: str = "") -> str:
    label = auditor_label or "另一模型"
    body = clip_audit_report(report)
    return f"【代码审计 · {label}】\n{body}"
