# Telegram payment review bot

Read-only Telegram bot for the CS Raiders MongoDB payment data. It shows only pending payment requests assigned to the authenticated reviewer’s configured payment numbers. It does not approve, reject, edit, or delete payments.

## Setup

1. Create a BotFather bot and put its token in `.env` as `TELEGRAM_BOT_TOKEN`.
2. Copy the relevant IDs and payment numbers into `reviewers.yaml`.
3. Install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

4. Ensure MongoDB is running at `localhost:27017`.
5. Start the bot:

```bash
python main.py
```

Use `/payments` or `/payment` in an allowed group. Use `/payments ORD-ABC123` or `/payments RCH-ABC123` to request one pending record.

The database stores receipt images as paths such as `/static/uploads/receipts/...`, not as binary data. `RECEIPT_STORAGE_ROOT` must point to the shared or mounted directory containing those files. For local development it may point to the existing application’s uploads directory; in deployment it should point to a shared uploads volume or another explicit receipt source. The bot does not depend on the reference project code.

