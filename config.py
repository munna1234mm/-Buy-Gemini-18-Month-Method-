import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "8617211126:AAEQoT7QzYx31pidbajzW5i2jF5pr6jFS28").strip()

# Admin IDs list parsed from comma-separated string
admin_ids_str = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(i.strip()) for i in admin_ids_str.split(",") if i.strip().isdigit()]

DEFAULT_REFERRAL_REWARD = float(os.getenv("DEFAULT_REFERRAL_REWARD", "0.5"))
CURRENCY_NAME = os.getenv("CURRENCY_NAME", "USDT")
DATABASE_PATH = os.getenv("DATABASE_PATH", "bot_database.db")
GEMINI_METHOD_LINK = os.getenv("GEMINI_METHOD_LINK", "https://t.me/SARKAR_COMPUTER")

