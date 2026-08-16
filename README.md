# 🚀 Telegram Referral & Force-Join Verification Bot

A complete Telegram Referral Bot built with Python (`python-telegram-bot` v20+) featuring dynamic Force-Subscription (FSUB) channel and group checks, referral tracking, rewards, and a full-featured Admin Panel.

---

## 🌟 Key Features

1. **Mandatory Channel/Group Join (Force Join / FSUB)**:
   - Dynamic management of channels and groups directly from the Telegram Admin UI.
   - Users are prompted to join all required channels before they can access the bot or claim rewards.
   - Automatic real-time verification using Telegram's `get_chat_member` API when users click **"✅ I Have Joined / Verify"**.

2. **Referral Program**:
   - Unique referral link for every user: `https://t.me/YourBot?start=USER_ID`.
   - Rewards are given to the referrer automatically once the invited friend verifies channel membership.
   - Daily bonus claim with cooldown timer.
   - Top 10 Referrers Leaderboard with medals.
   - Balance tracking and withdrawal threshold calculation.

3. **Admin Control Panel (`/admin`)**:
   - **📢 Manage Channels/Groups**: Add/Remove channels by @username or Chat ID.
   - **📊 Bot Statistics**: View total users, verified members, active channels, and total referrals.
   - **✉️ Broadcast Message**: Broadcast text, formatted messages, or photos to all registered users.
   - **⚙️ Set Referral Reward**: Adjust points/currency given per valid referral.
   - **👤 User Manager**: Search any user by Telegram ID, view balance/referral stats, credit/deduct balance, or ban/unban.

---

## 🛠 Setup & Installation

### 1. Requirements
Ensure Python 3.10+ is installed on your system.

Install dependencies:
```bash
pip install -r requirements.txt
```

### 2. Configuration (`.env`)
The `.env` file contains your configuration:
```env
BOT_TOKEN=8617211126:AAEQoT7QzYx31pidbajzW5i2jF5pr6jFS28
ADMIN_IDS=YOUR_TELEGRAM_USER_ID
DEFAULT_REFERRAL_REWARD=10
CURRENCY_NAME=Points
DATABASE_PATH=bot_database.db
```

> **Note:** If `ADMIN_IDS` is left empty, the first user who opens `/admin` will automatically be granted Admin access.

---

## ▶️ Running the Bot

Run the bot using:
```bash
python bot.py
```

---

## 📢 How to Add Channels/Groups for Force Join

1. **Add the Bot as an Admin in your Channel or Group**:
   - Open your Telegram Channel or Group -> Settings -> Administrators -> Add Admin -> search for your bot.
   - Grant admin permissions (at minimum: *Invite Users via Link* / *Manage Chat*).
2. **Open the Bot**:
   - Send `/admin` to the bot.
   - Click **"📢 Manage Channels/Groups"** -> **"➕ Add Channel / Group"**.
   - Send the channel's username (e.g. `@MyChannel`) or Chat ID (e.g. `-1001234567890`).
   - Send the invite link (or reply `default` to use the public link).
3. That's it! All new users will now be required to join this channel before using the bot.
