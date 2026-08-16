import logging
from typing import List, Tuple, Dict, Any
from telegram import Bot, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.error import TelegramError
import database

logger = logging.getLogger(__name__)

# Statuses that indicate a user has joined the chat
JOINED_STATUSES = {"creator", "administrator", "member", "restricted"}

async def check_user_membership(bot: Bot, user_id: int) -> Tuple[bool, List[Dict[str, Any]]]:
    """
    Checks if a user is a member of all required channels/groups.
    Returns:
        (is_fully_joined: bool, unjoined_channels: list)
    """
    channels = database.get_all_channels()
    if not channels:
        return True, []

    unjoined = []
    for channel in channels:
        chat_id = channel["chat_id"]
        # Convert numeric chat_ids if saved as integer string
        parsed_chat_id = int(chat_id) if (chat_id.startswith("-") or chat_id.isdigit()) else chat_id
        
        try:
            member = await bot.get_chat_member(chat_id=parsed_chat_id, user_id=user_id)
            if member.status not in JOINED_STATUSES:
                unjoined.append(channel)
        except TelegramError as e:
            logger.warning(f"Error checking membership for user {user_id} in {chat_id}: {e}")
            # If the bot cannot check or user is not found, treat as unjoined
            unjoined.append(channel)
        except Exception as e:
            logger.error(f"Unexpected error checking {chat_id}: {e}")
            unjoined.append(channel)

    return (len(unjoined) == 0, unjoined)


def build_join_keyboard(channels: List[Dict[str, Any]], verify_callback: str = "check_join") -> InlineKeyboardMarkup:
    """
    Builds an inline keyboard with channel links and a verify button.
    """
    keyboard = []
    for idx, ch in enumerate(channels, 1):
        title = ch.get("title", f"Channel {idx}")
        link = ch.get("invite_link", "")
        if link:
            keyboard.append([InlineKeyboardButton(f"📢 Join {title}", url=link)])
    
    # Verification action button
    keyboard.append([InlineKeyboardButton("✅ I Have Joined / Verify", callback_data=verify_callback)])
    return InlineKeyboardMarkup(keyboard)
