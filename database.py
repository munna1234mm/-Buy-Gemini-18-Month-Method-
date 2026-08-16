import sqlite3
import logging
import threading
import requests
from typing import List, Dict, Optional, Any, Tuple
import config

logger = logging.getLogger(__name__)

# --- FIREBASE CLOUD SYNC UTILITIES ---

def firebase_sync_async(path: str, data: Any, method: str = "PUT"):
    """Performs Firebase sync in a separate thread so Telegram bot operations remain instantaneous."""
    def _task():
        if not config.FIREBASE_DATABASE_URL:
            return
        url = f"{config.FIREBASE_DATABASE_URL}/{path.strip('/')}.json"
        try:
            if method == "PUT":
                requests.put(url, json=data, timeout=5)
            elif method == "PATCH":
                requests.patch(url, json=data, timeout=5)
            elif method == "DELETE":
                requests.delete(url, timeout=5)
        except Exception as e:
            logger.warning(f"Firebase sync warning for {path}: {e}")

    threading.Thread(target=_task, daemon=True).start()


def firebase_fetch(path: str) -> Optional[Any]:
    """Fetches data from Firebase Realtime Database."""
    if not config.FIREBASE_DATABASE_URL:
        return None
    url = f"{config.FIREBASE_DATABASE_URL}/{path.strip('/')}.json"
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        logger.warning(f"Firebase fetch warning for {path}: {e}")
    return None


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DATABASE_PATH, timeout=20.0)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initializes the database tables and pulls all persistent data from Firebase if available."""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                referrer_id INTEGER,
                balance REAL DEFAULT 0.0,
                referral_count INTEGER DEFAULT 0,
                joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_verified INTEGER DEFAULT 0,
                is_banned INTEGER DEFAULT 0
            )
        """)
        
        # Channels / Groups for Force Join
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                invite_link TEXT NOT NULL,
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Dynamic Settings
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        
        # Dynamic Admins table (in addition to config.ADMIN_IDS)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY,
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Referral reward log
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS referral_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER NOT NULL,
                referred_id INTEGER NOT NULL UNIQUE,
                reward REAL NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Set default settings
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", 
                       ("currency_name", config.CURRENCY_NAME))
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", 
                       ("referral_reward", str(config.DEFAULT_REFERRAL_REWARD)))
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", 
                       ("min_withdraw", "5"))
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", 
                       ("gemini_required_referrals", "5"))
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", 
                       ("gemini_method_price", "0.0"))
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", 
                       ("gemini_method_content", "🌟 <b>Gemini 18 Month Method Guide</b>\n\n🎉 <b>Congratulations!</b> You have unlocked the Gemini 18 Month Method.\n\n<b>Details / Steps:</b>\n1. Follow the official setup guide.\n2. Apply the configuration.\n3. Enjoy 18 months access!\n\nFor support, contact admin."))
        
        # Pre-seed initial config admins
        for admin_id in config.ADMIN_IDS:
            cursor.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (admin_id,))
            
        conn.commit()

    # Restore from Firebase Cloud Storage so no data is ever lost across server restarts / redeploys
    restore_from_firebase()
    logger.info("Database initialized & synced with Firebase successfully.")


def restore_from_firebase():
    """Restores users, channels, settings, and logs from Firebase into local SQLite."""
    try:
        fb_data = firebase_fetch("")
        if not fb_data or not isinstance(fb_data, dict):
            return

        with get_connection() as conn:
            cursor = conn.cursor()
            
            # Restore Settings
            fb_settings = fb_data.get("settings", {})
            if isinstance(fb_settings, dict):
                for k, v in fb_settings.items():
                    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (k, str(v)))

            # Restore Users
            fb_users = fb_data.get("users", {})
            if isinstance(fb_users, dict):
                for uid_str, udata in fb_users.items():
                    if isinstance(udata, dict) and "user_id" in udata:
                        cursor.execute("""
                            INSERT OR REPLACE INTO users (user_id, username, first_name, referrer_id, balance, referral_count, is_verified, is_banned)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            udata["user_id"],
                            udata.get("username", ""),
                            udata.get("first_name", ""),
                            udata.get("referrer_id"),
                            udata.get("balance", 0.0),
                            udata.get("referral_count", 0),
                            udata.get("is_verified", 0),
                            udata.get("is_banned", 0)
                        ))

            # Restore Channels
            fb_channels = fb_data.get("channels", {})
            if isinstance(fb_channels, dict):
                for ch_id_str, chdata in fb_channels.items():
                    if isinstance(chdata, dict) and "chat_id" in chdata:
                        cursor.execute("""
                            INSERT OR REPLACE INTO channels (id, chat_id, title, invite_link)
                            VALUES (?, ?, ?, ?)
                        """, (
                            chdata.get("id"),
                            chdata["chat_id"],
                            chdata.get("title", "Channel"),
                            chdata.get("invite_link", "")
                        ))

            # Restore Referral Logs
            fb_logs = fb_data.get("referral_logs", {})
            if isinstance(fb_logs, dict):
                for log_key, logdata in fb_logs.items():
                    if isinstance(logdata, dict) and "referred_id" in logdata:
                        cursor.execute("""
                            INSERT OR REPLACE INTO referral_logs (id, referrer_id, referred_id, reward, status)
                            VALUES (?, ?, ?, ?, ?)
                        """, (
                            logdata.get("id"),
                            logdata.get("referrer_id"),
                            logdata["referred_id"],
                            logdata.get("reward", 0.0),
                            logdata.get("status", "completed")
                        ))

            conn.commit()
            logger.info("Successfully restored and synced cloud data from Firebase.")
    except Exception as e:
        logger.warning(f"Failed to restore cloud data from Firebase: {e}")


# --- USER OPERATIONS ---

def get_or_create_user(user_id: int, username: Optional[str], first_name: Optional[str], referrer_id: Optional[int] = None) -> Tuple[Dict[str, Any], bool]:
    """
    Returns user dict and a boolean `is_new`.
    If new user and referrer_id is provided, stores pending referrer.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        
        if row:
            cursor.execute("""
                UPDATE users SET username = ?, first_name = ? WHERE user_id = ?
            """, (username, first_name, user_id))
            conn.commit()
            user_dict = dict(row)
            user_dict["username"] = username
            user_dict["first_name"] = first_name
            firebase_sync_async(f"users/{user_id}", user_dict, "PATCH")
            return user_dict, False
        
        # Validate referrer (cannot refer oneself)
        valid_referrer = None
        if referrer_id and referrer_id != user_id:
            cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (referrer_id,))
            if cursor.fetchone():
                valid_referrer = referrer_id

        cursor.execute("""
            INSERT INTO users (user_id, username, first_name, referrer_id, balance, referral_count, is_verified, is_banned)
            VALUES (?, ?, ?, ?, 0.0, 0, 0, 0)
        """, (user_id, username, first_name, valid_referrer))
        
        if valid_referrer:
            reward = float(get_setting("referral_reward", str(config.DEFAULT_REFERRAL_REWARD)))
            cursor.execute("""
                INSERT OR IGNORE INTO referral_logs (referrer_id, referred_id, reward, status)
                VALUES (?, ?, ?, 'pending')
            """, (valid_referrer, user_id, reward))
            firebase_sync_async(f"referral_logs/{user_id}", {
                "referrer_id": valid_referrer,
                "referred_id": user_id,
                "reward": reward,
                "status": "pending"
            }, "PUT")
            
        conn.commit()
        
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        new_row = cursor.fetchone()
        user_dict = dict(new_row)
        firebase_sync_async(f"users/{user_id}", user_dict, "PUT")
        return user_dict, True


def get_user(user_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def set_user_verified(user_id: int, verified: bool = True) -> bool:
    """Sets user verification status and syncs to Firebase."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET is_verified = ? WHERE user_id = ?", (1 if verified else 0, user_id))
        conn.commit()
        firebase_sync_async(f"users/{user_id}", {"is_verified": 1 if verified else 0}, "PATCH")
        return cursor.rowcount > 0


def complete_referral_reward(referred_id: int) -> Optional[Tuple[int, float]]:
    """
    When a referred user gets verified, reward their referrer once.
    Returns (referrer_id, reward_amount) if reward was given, or None if already completed/none.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT referrer_id, reward, status FROM referral_logs WHERE referred_id = ?
        """, (referred_id,))
        log = cursor.fetchone()
        
        if not log or log["status"] == "completed":
            return None
        
        referrer_id = log["referrer_id"]
        reward = float(log["reward"])
        
        # Credit referrer
        cursor.execute("""
            UPDATE users
            SET balance = balance + ?,
                referral_count = referral_count + 1
            WHERE user_id = ?
        """, (reward, referrer_id))
        
        # Mark log as completed
        cursor.execute("""
            UPDATE referral_logs
            SET status = 'completed'
            WHERE referred_id = ?
        """, (referred_id,))
        
        conn.commit()

        # Sync updated referrer & log to Firebase
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (referrer_id,))
        ref_row = cursor.fetchone()
        if ref_row:
            firebase_sync_async(f"users/{referrer_id}", dict(ref_row), "PUT")
        firebase_sync_async(f"referral_logs/{referred_id}", {"status": "completed"}, "PATCH")

        return (referrer_id, reward)


def update_balance(user_id: int, amount: float) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        conn.commit()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            firebase_sync_async(f"users/{user_id}", dict(row), "PUT")
        return cursor.rowcount > 0


def set_balance(user_id: int, amount: float) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (amount, user_id))
        conn.commit()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            firebase_sync_async(f"users/{user_id}", dict(row), "PUT")
        return cursor.rowcount > 0


def set_user_ban(user_id: int, is_banned: bool) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET is_banned = ? WHERE user_id = ?", (1 if is_banned else 0, user_id))
        conn.commit()
        firebase_sync_async(f"users/{user_id}", {"is_banned": 1 if is_banned else 0}, "PATCH")
        return cursor.rowcount > 0


def get_all_user_ids() -> List[int]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE is_banned = 0")
        return [r["user_id"] for r in cursor.fetchall()]


# --- CHANNEL / GROUP OPERATIONS ---

def add_channel(chat_id: str, title: str, invite_link: str) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO channels (chat_id, title, invite_link)
                VALUES (?, ?, ?)
            """, (chat_id, title, invite_link))
            conn.commit()
        except sqlite3.IntegrityError:
            cursor.execute("""
                UPDATE channels SET title = ?, invite_link = ? WHERE chat_id = ?
            """, (title, invite_link, chat_id))
            conn.commit()
        
        cursor.execute("SELECT * FROM channels WHERE chat_id = ?", (chat_id,))
        ch = cursor.fetchone()
        if ch:
            ch_dict = dict(ch)
            firebase_sync_async(f"channels/{ch_dict['id']}", ch_dict, "PUT")
        return True


def remove_channel(channel_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM channels WHERE id = ?", (channel_id,))
        conn.commit()
        firebase_sync_async(f"channels/{channel_id}", None, "DELETE")
        return cursor.rowcount > 0


def get_all_channels() -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM channels ORDER BY id ASC")
        return [dict(r) for r in cursor.fetchall()]


def get_channel(channel_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM channels WHERE id = ?", (channel_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


# --- SETTINGS OPERATIONS ---

def get_setting(key: str, default: str = "") -> str:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (key, value))
        conn.commit()
        firebase_sync_async(f"settings/{key}", value, "PUT")


# --- ADMIN PERMISSIONS ---

def is_admin(user_id: int) -> bool:
    if user_id in config.ADMIN_IDS:
        return True
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM admins WHERE user_id = ?", (user_id,))
        return cursor.fetchone() is not None


def add_admin(user_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (user_id,))
        conn.commit()
        firebase_sync_async(f"admins/{user_id}", True, "PUT")
        return cursor.rowcount > 0


def remove_admin(user_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
        conn.commit()
        firebase_sync_async(f"admins/{user_id}", None, "DELETE")
        return cursor.rowcount > 0


def get_all_admins() -> List[int]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM admins")
        db_admins = [r["user_id"] for r in cursor.fetchall()]
        return list(set(config.ADMIN_IDS + db_admins))


# --- STATISTICS ---

def get_stats() -> Dict[str, Any]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as total_users FROM users")
        total_users = cursor.fetchone()["total_users"]
        
        cursor.execute("SELECT COUNT(*) as verified_users FROM users WHERE is_verified = 1")
        verified_users = cursor.fetchone()["verified_users"]
        
        cursor.execute("SELECT COUNT(*) as total_channels FROM channels")
        total_channels = cursor.fetchone()["total_channels"]
        
        cursor.execute("SELECT SUM(referral_count) as total_referrals, SUM(balance) as total_balance FROM users")
        row = cursor.fetchone()
        total_referrals = row["total_referrals"] or 0
        total_balance = row["total_balance"] or 0.0
        
        return {
            "total_users": total_users,
            "verified_users": verified_users,
            "total_channels": total_channels,
            "total_referrals": total_referrals,
            "total_balance": round(total_balance, 2)
        }
