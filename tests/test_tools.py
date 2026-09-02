import pytest

from codeagent.tools import (
    BashTool,
    EditFileTool,
    GlobTool,
    GrepTool,
    ListDirTool,
    ReadFileTool,
    WriteFileTool,
)


@pytest.fixture
def workspace(tmp_path):
    (tmp_path / "hello.py").write_text("def hello():\n    return 'world'\n")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "notes.txt").write_text("hello agent\nsecond line\n")
    return tmp_path


async def test_read_file(workspace):
    tool = ReadFileTool(workspace)
    out = await tool.execute("hello.py")
    assert "def hello():" in out
    assert "1|" in out


async def test_read_file_with_offset_and_limit(workspace):
    tool = ReadFileTool(workspace)
    out = await tool.execute("docs/notes.txt", offset=2, limit=1)
    assert "second line" in out
    assert "hello agent" not in out


async def test_read_missing_file(workspace):
    tool = ReadFileTool(workspace)
    with pytest.raises(FileNotFoundError):
        await tool.execute("nope.txt")


async def test_write_and_read_back(workspace):
    writer = WriteFileTool(workspace)
    await writer.execute("new/out.py", "x = 1\n")
    reader = ReadFileTool(workspace)
    assert "x = 1" in await reader.execute("new/out.py")


async def test_edit_file(workspace):
    tool = EditFileTool(workspace)
    result = await tool.execute("hello.py", "'world'", "'agent'")
    assert "1 occurrence" in result
    assert "'agent'" in (workspace / "hello.py").read_text()


async def test_edit_file_requires_unique_match(workspace):
    (workspace / "dup.txt").write_text("foo foo")
    tool = EditFileTool(workspace)
    with pytest.raises(ValueError, match="occurs 2 times"):
        await tool.execute("dup.txt", "foo", "bar")
    await tool.execute("dup.txt", "foo", "bar", replace_all=True)
    assert (workspace / "dup.txt").read_text() == "bar bar"


async def test_path_escape_blocked(workspace):
    tool = ReadFileTool(workspace, restrict_to_root=True)
    with pytest.raises(PermissionError):
        await tool.execute("../outside.txt")


async def test_list_dir(workspace):
    tool = ListDirTool(workspace)
    out = await tool.execute(".")
    assert "hello.py" in out
    assert "docs/" in out


async def test_grep(workspace):
    tool = GrepTool(workspace)
    out = await tool.execute("hello")
    assert "hello.py:1:" in out
    assert "docs/notes.txt:1:" in out


async def test_grep_with_include_filter(workspace):
    tool = GrepTool(workspace)
    out = await tool.execute("hello", include="*.txt")
    assert "notes.txt" in out
    assert "hello.py" not in out


async def test_glob(workspace):
    tool = GlobTool(workspace)
    out = await tool.execute("**/*.py")
    assert "hello.py" in out
    assert "notes.txt" not in out


async def test_bash(workspace):
    tool = BashTool(workspace)
    out = await tool.execute("echo hello && pwd")
    assert "exit code: 0" in out
    assert "hello" in out


async def test_bash_nonzero_exit(workspace):
    tool = BashTool(workspace)
    out = await tool.execute("exit 3")
    assert "exit code: 3" in out
