# Telegram payment review bot

Telegram bot for the CS Raiders MongoDB payment data. It shows pending payment requests assigned to the authenticated reviewer’s configured payment numbers. An authorized reviewer can react with 👍 to set `verified_by_cs_raider_bot="verified"`, 👎 to set it to `"disproved"`, or any other reaction/removal to reset it to `"pending"`. New orders start as `"pending"`.

## Setup

1. Create a BotFather bot and put its token in `.env` as `TELEGRAM_BOT_TOKEN`.
2. Copy the relevant IDs and payment numbers into `reviewers.yaml`.
   Promote the bot to administrator in each configured chat; Telegram requires this for reaction updates.
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

Only order messages sent by this bot can be verified: the bot stores each displayed order message’s Telegram chat/message ID in MongoDB so reactions can be matched to the correct order. Other reactions are ignored, and the reacting user must be authorized for that chat.

The database stores receipt images as paths such as `/static/uploads/receipts/...`, not as binary data. `RECEIPT_STORAGE_ROOT` must point to the shared or mounted directory containing those files. For local development it may point to the existing application’s uploads directory; in deployment it should point to a shared uploads volume or another explicit receipt source. The bot does not depend on the reference project code.
