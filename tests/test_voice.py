"""Voice & emotion: emotion parsing, voice styles, continuous chat loop."""

from pathlib import Path

from codeagent import Agent, Emotion, VoiceChatLoop, parse_emotion
from codeagent.core.types import LLMResponse
from codeagent.llm.base import LLMProvider
from codeagent.voice import EMOTION_VOICE_MAP, VoiceStyle, style_for
from codeagent.voice.emotion import EMOTION_PROMPT_SUFFIX
from codeagent.voice.tts import TTSProvider


class ScriptedProvider(LLMProvider):
    name = "scripted"

    def __init__(self, responses: list[str]):
        super().__init__(model="scripted")
        self._responses = list(responses)
        self.systems: list[str | None] = []

    async def complete(self, messages, tools=None, system=None, **kwargs):
        self.systems.append(system)
        content = self._responses.pop(0) if self._responses else "[emotion:neutral] ..."
        return LLMResponse(content=content)


class FakeTTS(TTSProvider):
    def __init__(self):
        self.calls: list[tuple[str, VoiceStyle | None]] = []

    async def synthesize(self, text: str, style: VoiceStyle | None = None) -> Path:
        self.calls.append((text, style))
        return Path("/tmp/fake.mp3")


# ---------------------------------------------------------------------------
# parse_emotion
# ---------------------------------------------------------------------------

def test_parse_emotion_english_tag():
    emotion, text = parse_emotion("[emotion:happy]\n太好了，搞定了！")
    assert emotion is Emotion.HAPPY
    assert text == "太好了，搞定了！"


def test_parse_emotion_chinese_alias():
    emotion, text = parse_emotion("[emotion:温柔] 我会一直陪着你")
    assert emotion is Emotion.LOVING
    assert text == "我会一直陪着你"


def test_parse_emotion_missing_or_unknown():
    assert parse_emotion("没有标签的回复") == (Emotion.NEUTRAL, "没有标签的回复")
    emotion, text = parse_emotion("[emotion:dancing] 未知情绪被剥离")
    assert emotion is Emotion.NEUTRAL
    assert text == "未知情绪被剥离"


def test_every_emotion_has_voice_style():
    for emotion in Emotion:
        assert style_for(emotion) is EMOTION_VOICE_MAP[emotion]


# ---------------------------------------------------------------------------
# VoiceChatLoop
# ---------------------------------------------------------------------------

async def test_continuous_chat_with_emotion_and_tts():
    provider = ScriptedProvider([
        "[emotion:happy] 你好呀，很高兴见到你！",
        "[emotion:thinking] 让我想想……",
        "[emotion:loving] 晚安，做个好梦",
    ])
    agent = Agent(provider=provider)
    agent.system_prompt += EMOTION_PROMPT_SUFFIX
    tts = FakeTTS()
    loop = VoiceChatLoop(agent, tts=tts, auto_play=False)

    t1 = await loop.turn("你好")
    t2 = await loop.turn("1+1 等于几")
    t3 = await loop.turn("我要睡了")

    assert [t.emotion for t in (t1, t2, t3)] == [
        Emotion.HAPPY, Emotion.THINKING, Emotion.LOVING,
    ]
    # TTS receives clean text (tag stripped) with the mapped voice style
    assert tts.calls[0][0] == "你好呀，很高兴见到你！"
    assert tts.calls[0][1] == EMOTION_VOICE_MAP[Emotion.HAPPY]
    assert tts.calls[2][1].voice == "zh-CN-XiaoyiNeural"
    # history accumulates across turns: 3 user + 3 assistant messages
    assert len(agent.messages) == 6
    assert len(loop.turns) == 3


async def test_exit_words_end_conversation():
    agent = Agent(provider=ScriptedProvider([]))
    loop = VoiceChatLoop(agent)
    for word in ("exit", "quit", "bye", "退出", "再见", "拜拜", " EXIT "):
        assert await loop.turn(word) is None
    assert loop.turns == []


async def test_loop_without_tts_still_parses_emotion():
    provider = ScriptedProvider(["[emotion:sad] 这确实让人难过"])
    loop = VoiceChatLoop(Agent(provider=provider), tts=None)
    turn = await loop.turn("我考试没过")
    assert turn.emotion is Emotion.SAD
    assert turn.audio_path is None
    assert turn.reply_text == "这确实让人难过"


async def test_emotion_prompt_reaches_model():
    provider = ScriptedProvider(["[emotion:neutral] 好"])
    agent = Agent(provider=provider)
    agent.system_prompt += EMOTION_PROMPT_SUFFIX
    loop = VoiceChatLoop(agent)
    await loop.turn("hi")
    assert "[emotion:happy]" in provider.systems[0]


# ---------------------------------------------------------------------------
# ASR (voice input)
# ---------------------------------------------------------------------------

async def test_asr_full_voice_turn(tmp_path):
    """ASR text feeds the loop; the reply is spoken back — full duplex."""
    from codeagent.voice import ASRProvider

    class FakeASR(ASRProvider):
        async def transcribe(self, audio_path) -> str:
            return "今天天气怎么样"

    provider = ScriptedProvider(["[emotion:happy] 今天是大晴天！"])
    tts = FakeTTS()
    loop = VoiceChatLoop(Agent(provider=provider), tts=tts, auto_play=False)

    heard = await FakeASR().transcribe(tmp_path / "rec.wav")
    turn = await loop.turn(heard)

    assert turn.user_text == "今天天气怎么样"
    assert turn.emotion is Emotion.HAPPY
    assert tts.calls[0][0] == "今天是大晴天！"


async def test_whisper_asr_reports_missing_dependency():
    from codeagent.voice import WhisperASRProvider

    asr = WhisperASRProvider()
    try:
        import faster_whisper  # noqa: F401
        return  # dependency installed; nothing to test here
    except ImportError:
        pass
    try:
        await asr.transcribe("/tmp/nonexistent.wav")
        assert False, "should have raised"
    except RuntimeError as exc:
        assert "voice-full" in str(exc)


async def test_recorder_reports_missing_dependency():
    try:
        import sounddevice  # noqa: F401
        import soundfile  # noqa: F401
        return  # dependencies installed; nothing to test here
    except ImportError:
        pass
    from codeagent.voice import record_until_enter

    try:
        await record_until_enter()
        assert False, "should have raised"
    except RuntimeError as exc:
        assert "voice-full" in str(exc)


# ---------------------------------------------------------------------------
# Voice presets (free voice pack incl. Taiwanese voices)
# ---------------------------------------------------------------------------

def test_voice_presets_resolve_aliases():
    from codeagent.voice import resolve_voice
    from codeagent.voice.tts import VOICE_PRESETS

    assert resolve_voice("hsiaochen") == "zh-TW-HsiaoChenNeural"  # 台湾晓晨
    assert resolve_voice("HsiaoYu") == "zh-TW-HsiaoYuNeural"      # 大小写不敏感
    assert resolve_voice("yunjhe") == "zh-TW-YunJheNeural"
    assert resolve_voice("zh-CN-XiaoxiaoNeural") == "zh-CN-XiaoxiaoNeural"  # 原样透传
    assert "hsiaochen" in VOICE_PRESETS
    assert resolve_voice("edge-tw") == "zh-TW-HsiaoChenNeural"
    assert resolve_voice("xiaozhi") == "zh-TW-HsiaoChenNeural"


def test_to_speech_text_and_cute_style():
    from codeagent.voice.speech import cute_style, to_speech_text

    assert "略去代码" in to_speech_text("见 ```print(1)``` 后涨 3%")
    assert "print" not in to_speech_text("见 `print(1)` 后涨 3%")
    style = cute_style(-10, -5, True)
    assert style.pitch == "-10Hz"
    assert style.rate == "-5%"
    assert cute_style(enabled=False).pitch == "+0Hz"


def test_edge_tts_voice_pinning():
    """Explicit voice choice pins the voice; emotions only tune rate/pitch."""
    from codeagent.voice import EdgeTTSProvider

    pinned = EdgeTTSProvider(voice="hsiaochen", emotion_voices=False)
    assert pinned.voice == "zh-TW-HsiaoChenNeural"
    assert pinned.emotion_voices is False

    default = EdgeTTSProvider()
    assert default.voice == "zh-CN-XiaoxiaoNeural"
    assert default.emotion_voices is True

