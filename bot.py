import logging
import sys
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
    user_gemini_method_callback
)
from handlers.admin import (
    admin_command_handler,
    admin_menu_callback_handler,
    add_channel_start,
    add_channel_id_received,
    add_channel_link_received,
    set_reward_start,
    set_reward_received,
    broadcast_start,
    broadcast_received,
    set_gemini_content_start,
    set_gemini_content_received,
    set_gemini_refs_start,
    set_gemini_refs_received,
    set_gemini_price_start,
    set_gemini_price_received,
    cancel_handler,
    STATE_ADD_CHANNEL_ID,
    STATE_ADD_CHANNEL_LINK,
    STATE_SET_REWARD,
    STATE_BROADCAST,
    STATE_SET_GEMINI_CONTENT,
    STATE_SET_GEMINI_REFS,
    STATE_SET_GEMINI_PRICE
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


import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write(b"Telegram Bot is Active 24/7!")

    def log_message(self, format, *args):
        pass

def run_health_server():
    port = int(os.getenv("PORT", "8080"))
    try:
        server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
        server.serve_forever()
    except Exception as e:
        logger.warning(f"Could not start HTTP health server on port {port}: {e}")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error without terminating the bot."""
    logger.error("Exception while handling an update:", exc_info=context.error)


def main():
    # Start Keep-Alive HTTP server on a separate daemon thread
    threading.Thread(target=run_health_server, daemon=True).start()

    # Initialize SQLite Database
    database.init_db()

    if not config.BOT_TOKEN or config.BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        logger.error("Error: BOT_TOKEN is missing or not configured in .env file!")
        sys.exit(1)

    # Build Application
    app = ApplicationBuilder().token(config.BOT_TOKEN).build()

    # --- ADMIN CONVERSATIONS ---

    # 1. Add Channel Conversation
    add_channel_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_channel_start, pattern="^add_channel$")],
        states={
            STATE_ADD_CHANNEL_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_channel_id_received)
            ],
            STATE_ADD_CHANNEL_LINK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_channel_link_received)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_handler),
            CallbackQueryHandler(cancel_handler, pattern="^admin_channels$")
        ],
        per_chat=True,
        per_user=True,
        per_message=False
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
        per_message=False
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
        per_message=False
    )

    # 4. Set Gemini Method Content Conversation
    set_gemini_content_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(set_gemini_content_start, pattern="^admin_set_gemini_content$")],
        states={
            STATE_SET_GEMINI_CONTENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, set_gemini_content_received)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_handler),
            CallbackQueryHandler(cancel_handler, pattern="^admin_gemini_settings$")
        ],
        per_chat=True,
        per_user=True,
        per_message=False
    )

    # 5. Set Gemini Method Required Referrals Conversation
    set_gemini_refs_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(set_gemini_refs_start, pattern="^admin_set_gemini_refs$")],
        states={
            STATE_SET_GEMINI_REFS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, set_gemini_refs_received)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_handler),
            CallbackQueryHandler(cancel_handler, pattern="^admin_gemini_settings$")
        ],
        per_chat=True,
        per_user=True,
        per_message=False
    )

    # 6. Set Gemini Method Price Conversation
    set_gemini_price_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(set_gemini_price_start, pattern="^admin_set_gemini_price$")],
        states={
            STATE_SET_GEMINI_PRICE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, set_gemini_price_received)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_handler),
            CallbackQueryHandler(cancel_handler, pattern="^admin_gemini_settings$")
        ],
        per_chat=True,
        per_user=True,
        per_message=False
    )

    # Register admin conversations first
    app.add_handler(add_channel_conv)
    app.add_handler(set_reward_conv)
    app.add_handler(broadcast_conv)
    app.add_handler(set_gemini_content_conv)
    app.add_handler(set_gemini_refs_conv)
    app.add_handler(set_gemini_price_conv)

    # Admin command & callbacks
    app.add_handler(CommandHandler("admin", admin_command_handler))
    app.add_handler(CallbackQueryHandler(admin_menu_callback_handler, pattern="^admin_"))
    app.add_handler(CallbackQueryHandler(admin_menu_callback_handler, pattern="^del_channel_"))

    # --- USER HANDLERS (Inside Message Displays) ---
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CallbackQueryHandler(check_join_callback_handler, pattern="^check_join$"))
    app.add_handler(CallbackQueryHandler(user_main_menu_callback, pattern="^user_main_menu$"))
    app.add_handler(CallbackQueryHandler(user_gemini_method_callback, pattern="^user_gemini_method$"))
    app.add_handler(CallbackQueryHandler(user_ref_link_callback, pattern="^user_ref_link$"))
    app.add_handler(CallbackQueryHandler(user_balance_callback, pattern="^user_balance$"))

    # Error handling
    app.add_error_handler(error_handler)

    logger.info("Bot is starting polling...")
    print("==================================================")
    print(">> Telegram Referral & Force Join Bot is Running!")
    print("==================================================")
    
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
