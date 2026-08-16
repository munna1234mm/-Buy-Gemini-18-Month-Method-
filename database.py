import sqlite3
import logging
from typing import List, Dict, Optional, Any, Tuple
import config

logger = logging.getLogger(__name__)

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DATABASE_PATH, timeout=20.0)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the database tables and default settings."""
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

        # Digital Services table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS services (
                service_key TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                price REAL DEFAULT 0.0,
                is_enabled INTEGER DEFAULT 1
            )
        """)

        # Payment Methods & Ref-Pay table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS payment_methods (
                method_key TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                fee REAL DEFAULT 0.0,
                is_enabled INTEGER DEFAULT 1,
                details TEXT DEFAULT ''
            )
        """)

        # Dynamic Custom UI Buttons table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS custom_buttons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                button_type TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Seed default services if not present
        default_services = [
            ("chatgpt_3m", "ChatGPT 3M", 50.0, 1),
            ("canva_pro", "Canva Pro", 30.0, 1),
            ("canva_free", "Canva Free", 0.0, 1),
            ("lovable_ai", "Lovable AI", 40.0, 1),
            ("lovable_1d_free", "Lovable 1D Free", 0.0, 1),
            ("lovable_auto_order", "Lovable Auto Order", 0.0, 1)
        ]
        for sk, sname, sprice, senabled in default_services:
            cursor.execute("""
                INSERT OR IGNORE INTO services (service_key, name, price, is_enabled)
                VALUES (?, ?, ?, ?)
            """, (sk, sname, sprice, senabled))

        # Seed default payment methods if not present
        default_payments = [
            ("pix", "Pix", 0.0, 1),
            ("upi", "UPI", 0.0, 1),
            ("kakao", "Kakao", 0.0, 1),
            ("ideal", "Ideal", 2.5, 1),
            ("upi_qr", "UPI QR", 1.0, 1),
            ("ideal_ref_pay", "Ideal Ref-Pay", 0.0, 1),
            ("upi_ref_pay", "UPI Ref-Pay", 0.0, 1),
            ("upi_qr_ref_pay", "UPI QR Ref-Pay", 0.0, 1),
            ("auto_deposit", "Auto Deposit", 0.0, 1)
        ]
        for mk, mname, mfee, menabled in default_payments:
            cursor.execute("""
                INSERT OR IGNORE INTO payment_methods (method_key, name, fee, is_enabled)
                VALUES (?, ?, ?, ?)
            """, (mk, mname, mfee, menabled))

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
        logger.info("Database initialized successfully.")

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
            # Update username/first_name if changed
            cursor.execute("""
                UPDATE users SET username = ?, first_name = ? WHERE user_id = ?
            """, (username, first_name, user_id))
            conn.commit()
            return dict(row), False
        
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
            
        conn.commit()
        
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        new_row = cursor.fetchone()
        return dict(new_row), True

def get_user(user_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def set_user_verified(user_id: int, verified: bool = True) -> bool:
    """Sets user verification status."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET is_verified = ? WHERE user_id = ?", (1 if verified else 0, user_id))
        conn.commit()
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
        return (referrer_id, reward)

def update_balance(user_id: int, amount: float) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        conn.commit()
        return cursor.rowcount > 0

def set_balance(user_id: int, amount: float) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (amount, user_id))
        conn.commit()
        return cursor.rowcount > 0

def set_user_ban(user_id: int, is_banned: bool) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET is_banned = ? WHERE user_id = ?", (1 if is_banned else 0, user_id))
        conn.commit()
        return cursor.rowcount > 0

def get_leaderboard(limit: int = 10) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT user_id, username, first_name, referral_count, balance
            FROM users
            WHERE is_banned = 0
            ORDER BY referral_count DESC, balance DESC
            LIMIT ?
        """, (limit,))
        return [dict(r) for r in cursor.fetchall()]

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
            return True
        except sqlite3.IntegrityError:
            cursor.execute("""
                UPDATE channels SET title = ?, invite_link = ? WHERE chat_id = ?
            """, (title, invite_link, chat_id))
            conn.commit()
            return True

def remove_channel(channel_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM channels WHERE id = ?", (channel_id,))
        conn.commit()
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
        return cursor.rowcount > 0

def remove_admin(user_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
        conn.commit()
        return cursor.rowcount > 0

def get_all_admins() -> List[int]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM admins")
        db_admins = [r["user_id"] for r in cursor.fetchall()]
        return list(set(config.ADMIN_IDS + db_admins))

# --- DIGITAL SERVICES OPERATIONS ---

def get_all_services() -> Dict[str, Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM services")
        return {r["service_key"]: dict(r) for r in cursor.fetchall()}

def get_service(service_key: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM services WHERE service_key = ?", (service_key,))
        row = cursor.fetchone()
        return dict(row) if row else None

def set_service_price(service_key: str, price: float) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE services SET price = ? WHERE service_key = ?", (price, service_key))
        conn.commit()
        return cursor.rowcount > 0

def toggle_service(service_key: str) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT is_enabled FROM services WHERE service_key = ?", (service_key,))
        row = cursor.fetchone()
        if not row:
            return False
        new_val = 0 if row["is_enabled"] else 1
        cursor.execute("UPDATE services SET is_enabled = ? WHERE service_key = ?", (new_val, service_key))
        conn.commit()
        return bool(new_val)

# --- PAYMENT METHODS OPERATIONS ---

def get_all_payment_methods() -> Dict[str, Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM payment_methods")
        return {r["method_key"]: dict(r) for r in cursor.fetchall()}

def get_payment_method(method_key: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM payment_methods WHERE method_key = ?", (method_key,))
        row = cursor.fetchone()
        return dict(row) if row else None

def set_payment_fee(method_key: str, fee: float) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE payment_methods SET fee = ? WHERE method_key = ?", (fee, method_key))
        conn.commit()
        return cursor.rowcount > 0

def toggle_payment_method(method_key: str) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT is_enabled FROM payment_methods WHERE method_key = ?", (method_key,))
        row = cursor.fetchone()
        if not row:
            return False
        new_val = 0 if row["is_enabled"] else 1
        cursor.execute("UPDATE payment_methods SET is_enabled = ? WHERE method_key = ?", (new_val, method_key))
        conn.commit()
        return bool(new_val)

# --- CUSTOM BUTTONS OPERATIONS ---

def add_custom_button(name: str, button_type: str, content: str) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO custom_buttons (name, button_type, content)
            VALUES (?, ?, ?)
        """, (name, button_type, content))
        conn.commit()
        return True

def remove_custom_button(button_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM custom_buttons WHERE id = ?", (button_id,))
        conn.commit()
        return cursor.rowcount > 0

def get_all_custom_buttons() -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM custom_buttons ORDER BY id ASC")
        return [dict(r) for r in cursor.fetchall()]

def get_custom_button_by_name(name: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM custom_buttons WHERE name = ?", (name,))
        row = cursor.fetchone()
        return dict(row) if row else None

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
