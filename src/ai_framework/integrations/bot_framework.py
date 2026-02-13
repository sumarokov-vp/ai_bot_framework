from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from ai_framework.application import AIApplication

type GetUserMessage = Callable[[Any], str | None]


class IMessageSender(Protocol):
    def send(
        self,
        chat_id: int,
        text: str,
        parse_mode: str = "HTML",
        keyboard: Any = None,
        flow_name: str | None = None,
    ) -> Any: ...


class IUser(Protocol):
    @property
    def id(self) -> int: ...


class AIStep:
    name: str = "ai"

    def __init__(
        self,
        ai_application: AIApplication,
        message_sender: IMessageSender,
        get_user_message: GetUserMessage | None = None,
    ) -> None:
        self._ai_application = ai_application
        self._message_sender = message_sender
        self._get_user_message = get_user_message or _default_get_user_message

    def execute(self, user: IUser, state: Any) -> bool:
        text = self._get_user_message(state)
        if not text:
            return True

        thread_id = str(user.id)
        response = self._ai_application.process_message(thread_id, text)
        if response.content:
            self._message_sender.send(user.id, response.content)
        return False


def _default_get_user_message(state: Any) -> str | None:
    if hasattr(state, "source_message"):
        msg = state.source_message
        if hasattr(msg, "text"):
            return msg.text  # type: ignore[no-any-return]
    return None
