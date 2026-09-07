from __future__ import annotations

import logging

from app.bot import PaymentBot
from app.config import Settings
from app.database import PaymentRepository


class SecretRedactionFilter(logging.Filter):
    def __init__(self, secret: str) -> None:
        super().__init__()
        self.secret = secret

    def filter(self, record: logging.LogRecord) -> bool:
        if self.secret:
            message = record.getMessage()
            if self.secret in message:
                record.msg = message.replace(self.secret, "<redacted-token>")
                record.args = ()
        return True


def main() -> None:
    settings = Settings.load()
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    for handler in logging.getLogger().handlers:
        handler.addFilter(SecretRedactionFilter(settings.telegram_bot_token))
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    repository = PaymentRepository(settings.mongo_uri, settings.mongo_db_name)
    repository.client.admin.command("ping")
    logging.getLogger(__name__).info(
        "Starting read-only payment bot against %s/%s with %d configured reviewers",
        settings.mongo_uri,
        settings.mongo_db_name,
        len(settings.reviewers),
    )
    PaymentBot(settings, repository).application().run_polling(
        allowed_updates=["message", "callback_query", "message_reaction"]
    )


if __name__ == "__main__":
    main()
