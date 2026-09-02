"""Continuous conversation loop with emotion and voice.

Mirrors xiaozhi's auto mode (listen → think → speak → listen again) in a
UI-agnostic form: the caller drives turns with user input; each turn runs
the agent, parses the emotion tag, and speaks the reply through TTS.
Conversation history persists across turns via the agent itself, so this
is continuous dialogue, not one-shot Q&A.
"""

from __future__ import annotations

from dataclasses import dataclass

from codeagent.core.agent import Agent
from codeagent.voice.emotion import Emotion, parse_emotion, style_for
from codeagent.voice.tts import TTSProvider, play_audio

DEFAULT_EXIT_WORDS = ("exit", "quit", "bye", "退出", "再见", "拜拜")


@dataclass
class ChatTurn:
    user_text: str
    emotion: Emotion
    reply_text: str  # emotion tag stripped
    audio_path: str | None = None


class VoiceChatLoop:
    """Drives multi-turn emotional (optionally voiced) conversation."""

    def __init__(
        self,
        agent: Agent,
        tts: TTSProvider | None = None,
        exit_words: tuple[str, ...] = DEFAULT_EXIT_WORDS,
        auto_play: bool = True,
    ) -> None:
        self.agent = agent
        self.tts = tts
        self.exit_words = exit_words
        self.auto_play = auto_play
        self.turns: list[ChatTurn] = []

    def is_exit(self, user_text: str) -> bool:
        return user_text.strip().lower() in self.exit_words

    async def turn(self, user_text: str) -> ChatTurn | None:
        """Run one conversation turn. Returns None when the user exits."""
        if self.is_exit(user_text):
            return None
        raw = await self.agent.run(user_text)
        emotion, reply = parse_emotion(raw)
        turn = ChatTurn(user_text=user_text, emotion=emotion, reply_text=reply)

        if self.tts is not None and reply.strip():
            path = await self.tts.synthesize(reply, style=style_for(emotion))
            turn.audio_path = str(path)
            if self.auto_play:
                await play_audio(path)

        self.turns.append(turn)
        return turn
