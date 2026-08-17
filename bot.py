import logging
import sys
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes
)

import config
import database
from handlers.user import (
    start_handler,
    check_join_callback_handler,
    user_main_menu_callback,
    user_ref_link_callback,
    user_balance_callback,
    user_method_details_callback
)
from handlers.admin import (
    admin_command_handler,
    admin_menu_callback_handler,
    add_channel_start,
    add_channel_id_received,
    set_reward_start,
    set_reward_received,
    broadcast_start,
    broadcast_received,
    admin_add_method_start,
    admin_add_m_title_received,
    admin_add_m_content_received,
    admin_add_m_refs_received,
    admin_add_m_price_received,
    admin_edit_m_content_start,
    admin_edit_m_content_received,
    admin_edit_m_refs_start,
    admin_edit_m_refs_received,
    admin_edit_m_price_start,
    admin_edit_m_price_received,
    cancel_handler,
    STATE_ADD_CHANNEL_ID,
    STATE_SET_REWARD,
    STATE_BROADCAST,
    STATE_ADD_M_TITLE,
    STATE_ADD_M_CONTENT,
    STATE_ADD_M_REFS,
    STATE_ADD_M_PRICE,
    STATE_EDIT_M_CONTENT,
    STATE_EDIT_M_REFS,
    STATE_EDIT_M_PRICE
)

# Set UTF-8 encoding for Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write(b"Telegram Bot is Active 24/7!")

    def log_message(self, format, *args):
        pass


def run_health_server():
    port = int(os.getenv("PORT", "10000"))
    try:
        server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
        logger.info(f"Health check HTTP server is listening on port {port}")
        server.serve_forever()
    except Exception as e:
        logger.warning(f"Could not start HTTP health server on port {port}: {e}")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error without terminating the bot."""
    if "Conflict" in str(context.error):
        logger.warning("Another bot instance is running. Terminating conflicts...")
        return
    logger.error("Exception while handling an update:", exc_info=context.error)


def main():
    # Start Keep-Alive HTTP server on a separate daemon thread
    threading.Thread(target=run_health_server, daemon=True).start()

    # Initialize SQLite Database & Firebase Cloud Sync
    database.init_db()

    if not config.BOT_TOKEN or config.BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        logger.error("Error: BOT_TOKEN is missing or not configured in .env file!")
        sys.exit(1)

    # Build Application with high concurrency for fast multi-user performance
    app = (
        ApplicationBuilder()
        .token(config.BOT_TOKEN)
        .concurrent_updates(32)
        .build()
    )

    # --- ADMIN CONVERSATIONS ---

    # 1. Add Channel Conversation (Single & Bulk)
    add_channel_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_channel_start, pattern="^add_channel$")],
        states={
            STATE_ADD_CHANNEL_ID: [
                MessageHandler(filters.ALL & ~filters.COMMAND, add_channel_id_received)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_handler),
            CallbackQueryHandler(cancel_handler, pattern="^admin_channels$")
        ],
        per_chat=True,
        per_user=True,
        per_message=False,
        allow_reentry=True
    )

    # 2. Set Reward Conversation
    set_reward_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(set_reward_start, pattern="^admin_reward$")],
        states={
            STATE_SET_REWARD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, set_reward_received)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_handler),
            CallbackQueryHandler(cancel_handler, pattern="^admin_main$")
        ],
        per_chat=True,
        per_user=True,
        per_message=False,
        allow_reentry=True
    )

    # 3. Broadcast Conversation
    broadcast_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(broadcast_start, pattern="^admin_broadcast$")],
        states={
            STATE_BROADCAST: [
                MessageHandler(filters.ALL & ~filters.COMMAND, broadcast_received)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_handler),
            CallbackQueryHandler(cancel_handler, pattern="^admin_main$")
        ],
        per_chat=True,
        per_user=True,
        per_message=False,
        allow_reentry=True
    )

    # 4. Add Method Conversation (Supports Title, Text, Photo, Required Referrals, and Price)
    add_method_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_add_method_start, pattern="^admin_add_method$")],
        states={
            STATE_ADD_M_TITLE: [
                MessageHandler(filters.ALL & ~filters.COMMAND, admin_add_m_title_received)
            ],
            STATE_ADD_M_CONTENT: [
                MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, admin_add_m_content_received)
            ],
            STATE_ADD_M_REFS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_m_refs_received)
            ],
            STATE_ADD_M_PRICE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_m_price_received)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_handler),
            CallbackQueryHandler(cancel_handler, pattern="^admin_methods$")
        ],
        per_chat=True,
        per_user=True,
        per_message=False,
        allow_reentry=True
    )

    # 5. Edit Method Content & Photo Conversation
    edit_m_content_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_edit_m_content_start, pattern="^edit_m_content_")],
        states={
            STATE_EDIT_M_CONTENT: [
                MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, admin_edit_m_content_received)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_handler),
            CallbackQueryHandler(cancel_handler, pattern="^manage_method_")
        ],
        per_chat=True,
        per_user=True,
        per_message=False,
        allow_reentry=True
    )

    # 6. Edit Method Required Referrals Conversation
    edit_m_refs_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_edit_m_refs_start, pattern="^edit_m_refs_")],
        states={
            STATE_EDIT_M_REFS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_edit_m_refs_received)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_handler),
            CallbackQueryHandler(cancel_handler, pattern="^manage_method_")
        ],
        per_chat=True,
        per_user=True,
        per_message=False,
        allow_reentry=True
    )

    # 7. Edit Method Price Conversation
    edit_m_price_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_edit_m_price_start, pattern="^edit_m_price_")],
        states={
            STATE_EDIT_M_PRICE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_edit_m_price_received)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_handler),
            CallbackQueryHandler(cancel_handler, pattern="^manage_method_")
        ],
        per_chat=True,
        per_user=True,
        per_message=False,
        allow_reentry=True
    )

    # Register admin conversations first
    app.add_handler(add_channel_conv)
    app.add_handler(set_reward_conv)
    app.add_handler(broadcast_conv)
    app.add_handler(add_method_conv)
    app.add_handler(edit_m_content_conv)
    app.add_handler(edit_m_refs_conv)
    app.add_handler(edit_m_price_conv)

    # Admin command & callbacks
    app.add_handler(CommandHandler("admin", admin_command_handler))
    app.add_handler(CallbackQueryHandler(admin_menu_callback_handler, pattern="^admin_"))
    app.add_handler(CallbackQueryHandler(admin_menu_callback_handler, pattern="^manage_method_"))
    app.add_handler(CallbackQueryHandler(admin_menu_callback_handler, pattern="^del_method_"))
    app.add_handler(CallbackQueryHandler(admin_menu_callback_handler, pattern="^del_channel_"))

    # --- USER HANDLERS (Inside Message Displays) ---
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CallbackQueryHandler(check_join_callback_handler, pattern="^check_join$"))
    app.add_handler(CallbackQueryHandler(user_main_menu_callback, pattern="^user_main_menu$"))
    app.add_handler(CallbackQueryHandler(user_method_details_callback, pattern="^user_method_"))
    app.add_handler(CallbackQueryHandler(user_ref_link_callback, pattern="^user_ref_link$"))
    app.add_handler(CallbackQueryHandler(user_balance_callback, pattern="^user_balance$"))

    # Error handling
    app.add_error_handler(error_handler)

    logger.info("Bot is starting polling...")
    print("==================================================")
    print(">> Telegram Referral & Methods Bot is Running!")
    print("==================================================")
    
    app.run_polling(
        drop_pending_updates=True,
        bootstrap_retries=-1,
        poll_interval=1.0,
        timeout=20
    )


if __name__ == "__main__":
    main()
