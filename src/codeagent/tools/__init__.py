from pathlib import Path

from codeagent.tools.base import Tool, ToolRegistry
from codeagent.tools.delegate import DelegateTool
from codeagent.tools.filesystem import (
    EditFileTool,
    ListDirTool,
    ReadFileTool,
    WriteFileTool,
)
from codeagent.tools.search import GlobTool, GrepTool
from codeagent.tools.shell import BashTool
from codeagent.tools.web import WebFetchTool, WebScrapeTool, web_tools

__all__ = [
    "BashTool",
    "DelegateTool",
    "EditFileTool",
    "GlobTool",
    "GrepTool",
    "ListDirTool",
    "ReadFileTool",
    "Tool",
    "ToolRegistry",
    "WebFetchTool",
    "WebScrapeTool",
    "WriteFileTool",
    "default_tools",
    "web_tools",
]


def default_tools(
    root_dir: str | Path = ".",
    restrict_to_root: bool = True,
    shell_timeout: int = 120,
) -> ToolRegistry:
    """A registry pre-loaded with the built-in coding tools."""
    return ToolRegistry(
        [
            ReadFileTool(root_dir, restrict_to_root),
            WriteFileTool(root_dir, restrict_to_root),
            EditFileTool(root_dir, restrict_to_root),
            ListDirTool(root_dir, restrict_to_root),
            GrepTool(root_dir),
            GlobTool(root_dir),
            BashTool(root_dir, shell_timeout),
        ]
    )
