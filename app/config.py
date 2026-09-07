from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _csv_ints(value: str) -> frozenset[int]:
    result: set[int] = set()
    for item in value.split(","):
        item = item.strip()
        if item:
            result.add(int(item))
    return frozenset(result)


def normalize_payment_number(value: object) -> str:
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("20"):
        digits = "0" + digits[2:]
    return digits


def payment_number_variants(value: object) -> frozenset[str]:
    canonical = normalize_payment_number(value)
    if not canonical:
        return frozenset()
    local_without_zero = canonical[1:] if canonical.startswith("0") else canonical
    return frozenset({canonical, f"+20{local_without_zero}", f"20{local_without_zero}"})


@dataclass(frozen=True)
class Reviewer:
    telegram_user_id: int
    name: str
    allowed_chat_ids: frozenset[int]
    allowed_payment_numbers: frozenset[str]


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    mongo_uri: str
    mongo_db_name: str
    reviewers_config: Path
    receipt_storage_root: Path
    page_size: int
    log_level: str
    reviewers: tuple[Reviewer, ...]

    @classmethod
    def load(cls) -> "Settings":
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        if not token or token == "replace-with-botfather-token":
            raise RuntimeError("TELEGRAM_BOT_TOKEN must be configured in .env")

        config_path = Path(os.getenv("REVIEWERS_CONFIG", "reviewers.yaml"))
        if not config_path.is_absolute():
            config_path = ROOT / config_path
        with config_path.open("r", encoding="utf-8") as handle:
            raw = yaml.safe_load(handle) or {}

        reviewers: list[Reviewer] = []
        for entry in raw.get("authorized_users", []):
            reviewers.append(
                Reviewer(
                    telegram_user_id=int(entry["telegram_user_id"]),
                    name=str(entry.get("name", "Reviewer")),
                    allowed_chat_ids=frozenset(int(x) for x in entry.get("allowed_chat_ids", [])),
                    allowed_payment_numbers=frozenset(
                        normalize_payment_number(x) for x in entry.get("allowed_payment_numbers", [])
                    ),
                )
            )

        return cls(
            telegram_bot_token=token,
            mongo_uri=os.getenv("MONGO_URI", "mongodb://localhost:27017/"),
            mongo_db_name=os.getenv("MONGO_DB_NAME", "cs_raiders_db"),
            reviewers_config=config_path,
            receipt_storage_root=Path(os.getenv("RECEIPT_STORAGE_ROOT", "/mnt/projects/python/CS_raiders")),
            page_size=max(1, min(int(os.getenv("PAGE_SIZE", "5")), 20)),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            reviewers=tuple(reviewers),
        )

    def reviewer_for(self, user_id: int, chat_id: int) -> Reviewer | None:
        for reviewer in self.reviewers:
            if reviewer.telegram_user_id == user_id and chat_id in reviewer.allowed_chat_ids:
                return reviewer
        return None
