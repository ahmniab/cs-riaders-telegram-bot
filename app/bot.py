from __future__ import annotations

import logging

from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from .config import Settings
from .database import PaymentRepository
from .services import format_payment, resolve_receipt_path

LOGGER = logging.getLogger(__name__)


class PaymentBot:
    def __init__(self, settings: Settings, repository: PaymentRepository) -> None:
        self.settings = settings
        self.repository = repository

    def reviewer(self, update: Update):
        user = update.effective_user
        chat = update.effective_chat
        if not user or not chat:
            return None
        return self.settings.reviewer_for(user.id, chat.id)

    async def payments(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        reviewer = self.reviewer(update)
        if reviewer is None:
            LOGGER.warning("Unauthorized payment request user=%s chat=%s", update.effective_user.id if update.effective_user else None, update.effective_chat.id if update.effective_chat else None)
            return
        requested_id = context.args[0] if context.args else None
        if requested_id:
            payment = self.repository.get_pending_request(reviewer, requested_id)
            if not payment:
                await update.effective_message.reply_text("No pending payment request was found.")
                return
            await self.send_payment(update.effective_message, payment)
            return
        await self.send_page(update.effective_message, reviewer, 0)

    async def send_page(self, message, reviewer, page: int) -> None:
        skip = page * self.settings.page_size
        payments, total = self.repository.pending_requests(reviewer, skip, self.settings.page_size)
        if not payments:
            await message.reply_text("No pending payment requests for your assigned payment numbers.")
            return
        await message.reply_text(f"Pending requests {skip + 1}-{skip + len(payments)} of {total}:")
        for payment in payments:
            await self.send_payment(message, payment)
        buttons = []
        if page > 0:
            buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"payments:{page - 1}"))
        if skip + len(payments) < total:
            buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"payments:{page + 1}"))
        if buttons:
            await message.reply_text("Navigate:", reply_markup=InlineKeyboardMarkup([buttons]))

    async def send_payment(self, message, payment: dict) -> None:
        text = format_payment(payment)
        receipt = resolve_receipt_path(payment, self.settings.receipt_storage_root)
        if receipt:
            with receipt.open("rb") as image:
                await message.reply_photo(
                    photo=image,
                    caption=text,
                    parse_mode=ParseMode.HTML,
                )
            return
        await message.reply_text(text, parse_mode=ParseMode.HTML)

    async def pagination(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        reviewer = self.reviewer(update)
        if reviewer is None:
            return
        page = int(query.data.split(":", 1)[1])
        await self.send_page(query.message, reviewer, page)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if self.reviewer(update) is not None:
            await update.effective_message.reply_text("Use /payments to view pending payment requests.")

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if self.reviewer(update) is not None:
            await update.effective_message.reply_text(
                "Available commands:\n"
                "/payments - View pending payment requests\n"
                "/payment - Same as /payments\n"
                "/pay - Short alias for /payments\n"
                "/help - Show this help message"
            )

    async def set_commands(self, application: Application) -> None:
        await application.bot.set_my_commands([
            BotCommand("payments", "View pending payment requests"),
            BotCommand("payment", "View pending payment requests"),
            BotCommand("pay", "View pending payment requests"),
            BotCommand("help", "Show available commands"),
        ])

    def application(self) -> Application:
        application = (
            Application.builder()
            .token(self.settings.telegram_bot_token)
            .post_init(self.set_commands)
            .build()
        )
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CommandHandler("payments", self.payments))
        application.add_handler(CommandHandler("payment", self.payments))
        application.add_handler(CommandHandler("pay", self.payments))
        application.add_handler(CommandHandler("help", self.help))
        application.add_handler(CallbackQueryHandler(self.pagination, pattern=r"^payments:\d+$"))
        return application
