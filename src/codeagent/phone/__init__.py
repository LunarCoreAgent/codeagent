"""Phone / tablet device bridge: install apps and run basic device tests.

Uses Harmony ``hdc`` and Android ``adb`` when present on the host. The agent
drives this through the ``phone`` tool — no DevEco GUI required for install
and smoke tests.
"""

from codeagent.phone.bridge import (
    Device,
    PhoneBridge,
    detect_adb,
    detect_hdc,
    find_bridge,
)

__all__ = [
    "Device",
    "PhoneBridge",
    "detect_adb",
    "detect_hdc",
    "find_bridge",
]
