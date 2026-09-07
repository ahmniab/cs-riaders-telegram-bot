from __future__ import annotations

import logging

from app.bot import PaymentBot
from app.config import Settings
from app.database import PaymentRepository


def main() -> None:
    settings = Settings.load()
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    repository = PaymentRepository(settings.mongo_uri, settings.mongo_db_name)
    repository.client.admin.command("ping")
    logging.getLogger(__name__).info(
        "Starting read-only payment bot against %s/%s with %d configured reviewers",
        settings.mongo_uri,
        settings.mongo_db_name,
        len(settings.reviewers),
    )
    PaymentBot(settings, repository).application().run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()

