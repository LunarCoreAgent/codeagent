"""Permission policy and command risk classification.

Inspired by Codex's Guardian: every tool call carries a risk level, calls
above the auto-approval threshold go to an approval handler (e.g. an
interactive prompt), and risky calls fail closed when no handler is set.
"""

from __future__ import annotations

import inspect
import re
from enum import Enum, IntEnum
from typing import Awaitable, Callable

from codeagent.core.types import ToolCall


class RiskLevel(IntEnum):
    """Ordered risk classification for tool calls."""

    READ_ONLY = 0
    WRITE = 1
    EXECUTE = 2
    DESTRUCTIVE = 3


class ApprovalDecision(str, Enum):
    APPROVE = "approve"
    DENY = "deny"
    ALWAYS_ALLOW = "always_allow"  # approve and remember for this session


ApprovalHandler = Callable[
    [ToolCall, RiskLevel], "ApprovalDecision | Awaitable[ApprovalDecision]"
]


class PermissionPolicy:
    """Decides whether a tool call may proceed.

    - Tools listed in ``always_deny`` are rejected outright.
    - Tools listed in ``always_allow`` skip further checks.
    - Calls at or below ``auto_approve_up_to`` are approved silently.
    - Anything riskier goes to ``handler``; without a handler it is denied
      (fail closed).
    """

    def __init__(
        self,
        auto_approve_up_to: RiskLevel = RiskLevel.READ_ONLY,
        handler: ApprovalHandler | None = None,
        always_allow: set[str] | None = None,
        always_deny: set[str] | None = None,
    ) -> None:
        self.auto_approve_up_to = auto_approve_up_to
        self.handler = handler
        self.always_allow = set(always_allow or ())
        self.always_deny = set(always_deny or ())

    @classmethod
    def permissive(cls) -> PermissionPolicy:
        """Approve everything, including destructive calls. Use with care."""
        return cls(auto_approve_up_to=RiskLevel.DESTRUCTIVE)

    @classmethod
    def strict(cls) -> PermissionPolicy:
        """Auto-approve read-only calls only; deny the rest (no handler)."""
        return cls(auto_approve_up_to=RiskLevel.READ_ONLY)

    async def authorize(self, call: ToolCall, risk: RiskLevel) -> ApprovalDecision:
        if call.name in self.always_deny:
            return ApprovalDecision.DENY
        if call.name in self.always_allow:
            return ApprovalDecision.APPROVE
        if risk <= self.auto_approve_up_to:
            return ApprovalDecision.APPROVE
        if self.handler is None:
            return ApprovalDecision.DENY
        decision = self.handler(call, risk)
        if inspect.isawaitable(decision):
            decision = await decision
        if decision == ApprovalDecision.ALWAYS_ALLOW:
            self.always_allow.add(call.name)
            return ApprovalDecision.APPROVE
        return decision


# ---------------------------------------------------------------------------
# Shell command classification
# ---------------------------------------------------------------------------

_DESTRUCTIVE_PATTERNS = [
    r"\brm\s+[^\n]*-[a-zA-Z]*[rf]",        # rm -rf / rm -r / rm -f
    r"\bgit\s+push\b[^\n]*--force",        # force push
    r"\bgit\s+reset\s+--hard",
    r"\bgit\s+clean\s+-[a-zA-Z]*f",
    r"\bmkfs\b",
    r"\bdd\b[^\n]*\bof=/dev/",
    r">\s*/dev/sd",
    r"\bshutdown\b",
    r"\breboot\b",
    r"\bchmod\s+-R\s+777\b",
    r"\bchown\s+-R\b[^\n]*/\s*$",          # recursive chown on /
]

_READ_ONLY_BINARIES = {
    "ls", "cat", "pwd", "echo", "head", "tail", "less", "more", "grep",
    "rg", "find", "which", "whoami", "date", "env", "printenv", "wc",
    "file", "stat", "du", "df", "tree", "sed", "awk", "sort", "uniq",
    "diff", "basename", "dirname", "realpath", "readlink", "true", "uname",
}

_READ_ONLY_GIT_SUBCOMMANDS = {
    "status", "diff", "log", "show", "branch", "remote", "rev-parse",
    "ls-files", "blame", "stash", "tag", "describe", "shortlog",
}

_WRITE_PATTERNS = [
    r">>?",                                 # redirection
    r"\btee\b",
    r"\bmv\b", r"\bcp\b", r"\bmkdir\b", r"\btouch\b", r"\bln\b",
    r"\bgit\s+(add|commit|checkout|switch|merge|pull|rebase|restore)\b",
    r"\b(npm|pnpm|yarn|pip|pip3|uv)\s+(install|add|remove|uninstall)\b",
]


def _is_read_only_segment(segment: str) -> bool:
    tokens = segment.strip().split()
    if not tokens:
        return True
    binary = tokens[0].rsplit("/", 1)[-1]
    if binary in _READ_ONLY_BINARIES:
        # sed/awk can write with -i; treat flags conservatively
        if binary in {"sed", "awk"} and any("-i" in t for t in tokens[1:]):
            return False
        return True
    if binary == "git":
        return len(tokens) > 1 and tokens[1] in _READ_ONLY_GIT_SUBCOMMANDS
    return False


def classify_command(command: str) -> RiskLevel:
    """Heuristic risk classification for a shell command string."""
    for pattern in _DESTRUCTIVE_PATTERNS:
        if re.search(pattern, command):
            return RiskLevel.DESTRUCTIVE

    # redirection or package/git mutations make even read-only binaries a write
    for pattern in _WRITE_PATTERNS:
        if re.search(pattern, command):
            return RiskLevel.WRITE

    segments = re.split(r"\|\||&&|\||;", command)
    if all(_is_read_only_segment(seg) for seg in segments):
        return RiskLevel.READ_ONLY

    return RiskLevel.EXECUTE
