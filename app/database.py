from __future__ import annotations

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

    def pending_requests(self, reviewer: Reviewer, skip: int, limit: int) -> tuple[list[dict], int]:
        numbers = sorted({variant for number in reviewer.allowed_payment_numbers for variant in payment_number_variants(number)})
        order_query = {
            "status": "pending",
            "deleted_by_admin": {"$ne": True},
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
