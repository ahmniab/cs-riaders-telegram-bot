from __future__ import annotations

from datetime import datetime, timezone

from pymongo import ASCENDING, DESCENDING, MongoClient

from .config import Reviewer, payment_number_variants


class PaymentRepository:
    def __init__(self, uri: str, db_name: str) -> None:
        self.client = MongoClient(
            uri,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
            socketTimeoutMS=15000,
            retryReads=True,
            maxPoolSize=10,
        )
        self.db = self.client[db_name]
        self.db.orders.create_index([
            ("status", ASCENDING), ("transferred_to", ASCENDING), ("created_at", DESCENDING)
        ])
        self.db.wallet_recharge_requests.create_index([
            ("status", ASCENDING), ("transferred_to", ASCENDING), ("created_at", DESCENDING)
        ])
        self.db.telegram_order_messages.create_index(
            [("chat_id", ASCENDING), ("message_id", ASCENDING)], unique=True
        )

    def pending_requests(self, reviewer: Reviewer, skip: int, limit: int) -> tuple[list[dict], int]:
        numbers = sorted({variant for number in reviewer.allowed_payment_numbers for variant in payment_number_variants(number)})
        order_query = {
            "status": "pending",
            "deleted_by_admin": {"$ne": True},
            "verified_by_cs_raider_bot": {"$nin": ["verified", True, "disproved"]},
            "transferred_to": {"$in": numbers},
        }
        recharge_query = {
            "status": "pending",
            "transferred_to": {"$in": numbers},
        }
        orders = [dict(doc, _payment_type="order") for doc in self.db.orders.find(order_query)]
        recharges = [dict(doc, _payment_type="wallet_recharge") for doc in self.db.wallet_recharge_requests.find(recharge_query)]
        combined = sorted(
            orders + recharges,
            key=lambda item: item.get("created_at") or 0,
            reverse=True,
        )
        total = len(combined)
        return combined[skip : skip + limit], total

    def get_pending_request(self, reviewer: Reviewer, payment_id: str) -> dict | None:
        number_filter = {
            "$in": sorted({variant for number in reviewer.allowed_payment_numbers for variant in payment_number_variants(number)})
        }
        order = self.db.orders.find_one({
            "order_id": payment_id,
            "status": "pending",
            "deleted_by_admin": {"$ne": True},
            "verified_by_cs_raider_bot": {"$nin": ["verified", True]},
            "transferred_to": number_filter,
        })
        if order:
            order["_payment_type"] = "order"
            return order
        recharge = self.db.wallet_recharge_requests.find_one({
            "request_id": payment_id,
            "status": "pending",
            "transferred_to": number_filter,
        })
        if recharge:
            recharge["_payment_type"] = "wallet_recharge"
        return recharge

    def record_order_message(self, chat_id: int, message_id: int, order_id: str) -> None:
        # This link is required because Telegram reaction updates do not include
        # the text or caption of the message being reacted to.
        self.db.telegram_order_messages.update_one(
            {"chat_id": chat_id, "message_id": message_id},
            {
                "$set": {
                    "order_id": order_id,
                    "recorded_at": datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )

    def set_order_verification_status(self, order_id: str, verification_status: str) -> bool:
        if verification_status not in {"pending", "verified", "disproved"}:
            return False
        result = self.db.orders.update_one(
            {"order_id": order_id},
            {"$set": {"verified_by_cs_raider_bot": verification_status}},
        )
        return result.matched_count > 0

    def verify_order_for_message(self, chat_id: int, message_id: int, verification_status: str) -> str | None:
        message = self.db.telegram_order_messages.find_one(
            {"chat_id": chat_id, "message_id": message_id},
            {"order_id": 1},
        )
        if not message or not message.get("order_id"):
            return None
        order_id = str(message["order_id"])
        if not self.set_order_verification_status(order_id, verification_status):
            return None
        return order_id
