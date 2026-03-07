from datetime import datetime

from pydantic import BaseModel


class Session(BaseModel):
    thread_id: str
    language: str | None = None
    last_message_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"frozen": True}
