"""Xiaozhi client: connect codeagent to xiaozhi.me's free voice server."""

from codeagent.xiaozhi.audio import OpusCodec
from codeagent.xiaozhi.client import ConversationEvents, XiaozhiClient
from codeagent.xiaozhi.config import XiaozhiConfig
from codeagent.xiaozhi.ota import (
    ActivationRequiredError,
    OtaClient,
    OtaResult,
)
from codeagent.xiaozhi.protocol import XiaozhiMessage, XiaozhiProtocol

__all__ = [
    "ActivationRequiredError",
    "ConversationEvents",
    "OpusCodec",
    "OtaClient",
    "OtaResult",
    "XiaozhiClient",
    "XiaozhiConfig",
    "XiaozhiMessage",
    "XiaozhiProtocol",
]
