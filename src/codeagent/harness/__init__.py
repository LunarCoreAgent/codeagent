"""External agent platform adapters: call other CLI agents when stuck."""

from codeagent.harness.adapters import (
    HARNESS_PRESETS,
    CliHarness,
    HarnessResult,
    discover_harnesses,
)
from codeagent.harness.tool import AskHarnessTool

__all__ = [
    "AskHarnessTool",
    "CliHarness",
    "HARNESS_PRESETS",
    "HarnessResult",
    "discover_harnesses",
]
