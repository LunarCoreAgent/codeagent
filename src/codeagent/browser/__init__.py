"""Built-in browser the agent can drive without BrowserSkill / ego-lite."""

from codeagent.browser.engine import InternalBrowser
from codeagent.browser.snapshot import format_observe, snapshot_html

__all__ = ["InternalBrowser", "format_observe", "snapshot_html"]
