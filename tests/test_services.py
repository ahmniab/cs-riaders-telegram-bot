from pathlib import Path

from app.config import normalize_payment_number
from app.services import format_payment, resolve_receipt_path


def test_normalizes_egyptian_payment_numbers():
    assert normalize_payment_number("+20 102 767 4505") == "01027674505"
    assert normalize_payment_number("001027674505") == "01027674505"


def test_formats_order():
    text = format_payment({
        "_payment_type": "order",
        "order_id": "ORD-123",
        "student_name": "A & B",
        "total": 100,
        "transferred_to": "01000000000",
        "status": "pending",
    })
    assert "ORD-123" in text
    assert "A &amp; B" in text
    assert "Pending review" in text


def test_receipt_must_stay_under_reference_root(tmp_path: Path):
    receipt = tmp_path / "static" / "uploads" / "receipts" / "receipt.jpg"
    receipt.parent.mkdir(parents=True)
    receipt.write_bytes(b"image")
    assert resolve_receipt_path({"receipt_image": "/static/uploads/receipts/receipt.jpg"}, tmp_path) == receipt
    assert resolve_receipt_path({"receipt_image": "/etc/passwd"}, tmp_path) is None
