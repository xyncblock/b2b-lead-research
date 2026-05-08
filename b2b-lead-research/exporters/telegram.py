"""
Telegram delivery for reports.
"""
import asyncio
import logging
from typing import Optional
from pathlib import Path

from telegram import Bot
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)


class TelegramDelivery:
    """Send Excel reports via Telegram bot."""
    
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.bot = Bot(token=bot_token)
    
    async def send_batch(
        self,
        file_path: str,
        country: str,
        batch_number: int,
        total_records: int,
        hot_count: int,
        warm_count: int,
        cold_count: int,
    ) -> bool:
        """
        Send batch report to Telegram.
        
        Caption: 📊 Batch #{n} | {country} | 500 records | {hot} HOT | {warm} WARM | LIA-compliant
        """
        try:
            caption = (
                f"📊 <b>Batch #{batch_number}</b> | {country}\n"
                f"📈 {total_records} records\n"
                f"🔥 {hot_count} HOT\n"
                f"⚡ {warm_count} WARM\n"
                f"❄️ {cold_count} COLD\n"
                f"✅ LIA-compliant"
            )
            
            file_path = Path(file_path)
            if not file_path.exists():
                logger.error(f"File not found: {file_path}")
                return False
            
            with open(file_path, "rb") as f:
                await self.bot.send_document(
                    chat_id=self.chat_id,
                    document=f,
                    filename=file_path.name,
                    caption=caption,
                    parse_mode=ParseMode.HTML,
                )
            
            logger.info(f"Sent batch #{batch_number} to Telegram")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send Telegram report: {e}")
            return False
    
    def send_batch_sync(
        self,
        file_path: str,
        country: str,
        batch_number: int,
        total_records: int,
        hot_count: int,
        warm_count: int,
        cold_count: int,
    ) -> bool:
        """Synchronous wrapper."""
        return asyncio.run(self.send_batch(
            file_path, country, batch_number, total_records,
            hot_count, warm_count, cold_count
        ))
    
    async def send_notification(self, message: str) -> bool:
        """Send a simple notification."""
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=ParseMode.HTML,
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
            return False
    
    def send_notification_sync(self, message: str) -> bool:
        """Synchronous wrapper for notifications."""
        return asyncio.run(self.send_notification(message))