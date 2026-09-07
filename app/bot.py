from __future__ import annotations

import logging

from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageReactionHandler,
)

from .config import Settings
from .database import PaymentRepository
from .services import format_payment, resolve_receipt_path

LOGGER = logging.getLogger(__name__)
UNAUTHORIZED_MESSAGE = "You are not authorized to use this bot. Please contact an administrator."
THUMBS_UP = "👍"


class PaymentBot:
    def __init__(self, settings: Settings, repository: PaymentRepository) -> None:
        self.settings = settings
        self.repository = repository

    @staticmethod
    def _has_thumbs_up(reactions) -> bool:
        return any(getattr(reaction, "emoji", None) == THUMBS_UP for reaction in reactions)

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
            await update.effective_message.reply_text(UNAUTHORIZED_MESSAGE)
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
                sent_message = await message.reply_photo(
                    photo=image,
                    caption=text,
                    parse_mode=ParseMode.HTML,
                )
        else:
            sent_message = await message.reply_text(text, parse_mode=ParseMode.HTML)

        if payment.get("_payment_type") == "order" and sent_message:
            self.repository.record_order_message(
                sent_message.chat_id,
                sent_message.message_id,
                str(payment["order_id"]),
            )
            LOGGER.info(
                "Recorded order message mapping order=%s chat=%s message=%s",
                payment["order_id"],
                sent_message.chat_id,
                sent_message.message_id,
            )

    async def reaction(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        reaction_update = update.message_reaction
        reviewer = self.reviewer(update)
        if reaction_update is None:
            return

        LOGGER.info(
            "Received message reaction chat=%s message=%s user=%s old=%s new=%s",
            reaction_update.chat.id,
            reaction_update.message_id,
            reaction_update.user.id if reaction_update.user else None,
            reaction_update.old_reaction,
            reaction_update.new_reaction,
        )
        if reviewer is None:
            LOGGER.warning(
                "Ignoring reaction from unauthorized user=%s chat=%s",
                reaction_update.user.id if reaction_update.user else None,
                reaction_update.chat.id,
            )
            return

        had_thumbs_up = self._has_thumbs_up(reaction_update.old_reaction)
        has_thumbs_up = self._has_thumbs_up(reaction_update.new_reaction)
        if had_thumbs_up == has_thumbs_up:
            return

        verified = has_thumbs_up
        order_id = self.repository.verify_order_for_message(
            reaction_update.chat.id,
            reaction_update.message_id,
            verified,
        )
        if not order_id:
            LOGGER.warning(
                "No order mapping found for reacted message chat=%s message=%s",
                reaction_update.chat.id,
                reaction_update.message_id,
            )
            return
        LOGGER.info(
            "Order %s marked verified_by_cs_raider_bot=%s by user=%s chat=%s",
            order_id,
            verified,
            reviewer.telegram_user_id,
            reaction_update.chat.id,
        )

    async def pagination(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        reviewer = self.reviewer(update)
        if reviewer is None:
            await query.message.reply_text(UNAUTHORIZED_MESSAGE)
            return
        page = int(query.data.split(":", 1)[1])
        await self.send_page(query.message, reviewer, page)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if self.reviewer(update) is not None:
            await update.effective_message.reply_text("Use /payments to view pending payment requests.")
        else:
            await update.effective_message.reply_text(UNAUTHORIZED_MESSAGE)

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if self.reviewer(update) is not None:
            await update.effective_message.reply_text(
                "Available commands:\n"
                "/payments - View pending payment requests\n"
                "/payment - Same as /payments\n"
                "/pay - Short alias for /payments\n"
                "/help - Show this help message"
            )
        else:
            await update.effective_message.reply_text(UNAUTHORIZED_MESSAGE)

    async def set_commands(self, application: Application) -> None:
        await application.bot.set_my_commands([
            BotCommand("payments", "View pending payment requests"),
            BotCommand("payment", "View pending payment requests"),
            BotCommand("pay", "View pending payment requests"),
            BotCommand("help", "Show available commands"),
        ])

        bot = await application.bot.get_me()
        LOGGER.info("Telegram bot identity id=%s username=%s", bot.id, bot.username)
        chat_ids = sorted({
            chat_id
            for reviewer in self.settings.reviewers
            for chat_id in reviewer.allowed_chat_ids
        })
        for chat_id in chat_ids:
            try:
                chat = await application.bot.get_chat(chat_id)
                administrators = await application.bot.get_chat_administrators(chat_id)
            except Exception:
                LOGGER.exception("Could not inspect bot administrator status in chat=%s", chat_id)
                continue
            admin_summary = [
                f"{admin.user.id}:{admin.user.username or admin.user.full_name}:{admin.status}"
                for admin in administrators
            ]
            bot_admin = next((admin for admin in administrators if admin.user.id == bot.id), None)
            LOGGER.info(
                "Telegram chat id=%s title=%s type=%s bot_status=%s administrators=%s",
                chat.id,
                chat.title or chat.username or "",
                chat.type,
                bot_admin.status if bot_admin else "not listed",
                admin_summary,
            )
            if bot_admin is None or bot_admin.status not in {"administrator", "creator"}:
                LOGGER.warning(
                    "Telegram does not report bot id=%s as an administrator in chat=%s; reaction updates will not arrive",
                    bot.id,
                    chat_id,
                )

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
        application.add_handler(
            MessageReactionHandler(
                self.reaction,
                message_reaction_types=MessageReactionHandler.MESSAGE_REACTION_UPDATED,
            )
        )
        return application
