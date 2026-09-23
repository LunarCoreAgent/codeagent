"""Second-model code audit helpers."""

from __future__ import annotations

from codeagent.code_audit import (
    audit_needs_repair,
    build_audit_prompt,
    build_repair_prompt,
    pick_auditor_ref,
)


def test_pick_auditor_prefers_other_model():
    ref = pick_auditor_ref(
        "gpt-oss:120b",
        mixture_members=[
            "local:gpt-oss:120b@ep1",
            "local:deepseek-v4-flash@ep2",
        ],
        api_ids=["cloud1"],
    )
    assert "deepseek" in ref or ref.startswith("api:")


def test_pick_auditor_honors_explicit_ref():
    assert pick_auditor_ref("x", audit_ref="api:abc") == "api:abc"


def test_audit_needs_repair_detects_issues():
    assert not audit_needs_repair("审计通过：未发现错误。风格可选优化略过。")
    assert audit_needs_repair(
        "发现问题\n- a.py：NameError\n必须修复：补上导入"
    )


def test_build_prompts_include_paths():
    audit = build_audit_prompt(["src/a.py", "src/b.py"], "实现登录")
    assert "src/a.py" in audit and "登录" in audit
    fix = build_repair_prompt("必须修复：缺导入", ["src/a.py"])
    assert "缺导入" in fix and "src/a.py" in fix
