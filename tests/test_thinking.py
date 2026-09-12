"""Unit tests for thinking / answer split."""

from codeagent.core.thinking import split_thinking


def test_split_think_tags():
    visible, thinking = split_thinking(
        "<think>先分析一下</think>\n\n结论：修好了。"
    )
    assert thinking == "先分析一下"
    assert visible == "结论：修好了。"


def test_split_thinking_alias_and_reasoning_field():
    visible, thinking = split_thinking(
        "正文答案",
        reasoning="字段里的推理",
    )
    assert "字段里的推理" in thinking
    assert visible == "正文答案"


def test_split_only_reasoning_keeps_visible_empty():
    visible, thinking = split_thinking("", reasoning="只有推理")
    assert visible == ""
    assert thinking == "只有推理"


def test_split_no_thinking():
    visible, thinking = split_thinking("直接回答")
    assert visible == "直接回答"
    assert thinking == ""
