from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path

from .config import Reviewer, normalize_payment_number


def payment_id(payment: dict) -> str:
    return str(payment.get("order_id") or payment.get("request_id") or "unknown")


def payment_type_label(payment: dict) -> str:
    return "Website order" if payment.get("_payment_type") == "order" else "Wallet recharge"


def format_datetime(value: object) -> str:
    if not isinstance(value, datetime):
        return str(value or "Unknown")
    return value.strftime("%Y-%m-%d %H:%M UTC")


def format_payment(payment: dict) -> str:
    amount = payment.get("total", payment.get("amount", "Unknown"))
    reference = payment.get("vf_cash_ref") or payment.get("sender_phone") or "Unknown"
    student = payment.get("student_name") or payment.get("student_id") or "Unknown"
    lines = [
        "<b>💳 Payment request</b>",
        f"<b>Type:</b> {html.escape(payment_type_label(payment))}",
        f"<b>ID:</b> <code>{html.escape(payment_id(payment))}</code>",
        f"<b>Student:</b> {html.escape(str(student))}",
        f"<b>Amount:</b> {html.escape(str(amount))} EGP",
        f"<b>Payment number:</b> {html.escape(str(payment.get('transferred_to') or 'Unknown'))}",
        f"<b>Reference/sender:</b> {html.escape(str(reference))}",
        f"<b>Created:</b> {html.escape(format_datetime(payment.get('created_at')))}",
        "<b>Status:</b> Pending review",
    ]
    if payment.get("package_name"):
        lines.insert(4, f"<b>Package:</b> {html.escape(str(payment['package_name']))}")
    return "\n".join(lines)


def resolve_receipt_path(payment: dict, reference_root: Path) -> Path | None:
    raw = payment.get("receipt_image")
    if not raw:
        return None
    value = str(raw)
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = reference_root / value.lstrip("/")
    if value.startswith("/static/"):
        candidate = reference_root / value.lstrip("/")
    try:
        candidate = candidate.resolve()
        root = reference_root.resolve()
        if root not in candidate.parents and candidate != root:
            return None
    except OSError:
        return None
    return candidate if candidate.is_file() else None

