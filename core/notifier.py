"""Telegram + console notifier. Silently no-ops if Telegram not configured."""
import os
import re
import urllib.request
import urllib.parse
import urllib.error          
from dotenv import load_dotenv
load_dotenv()

class Notifier:
    def __init__(self, bot_token=None, chat_id=None):
        self.bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
        self.enabled = bool(self.bot_token and self.chat_id)

    def _send(self, message: str, level: str = "INFO"):
        emoji = {"INFO": "ℹ️", "SUCCESS": "✅", "WARN": "⚠️", "ERROR": "🚨"}.get(level, "")
        header = f"{emoji} [{level}]"
        # Always print to console
        print(f"{header} {message}")
        if not self.enabled:
            return
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            data = urllib.parse.urlencode({
                "chat_id": self.chat_id,
                "text": f"{header}\n\n{message}",
            }).encode()
            urllib.request.urlopen(url, data=data, timeout=10)
        except Exception as e:
            print(f"[WARN] Telegram delivery failed: {e}")

    def info(self, m):    self._send(m, "INFO")
    def success(self, m): self._send(m, "SUCCESS")
    def warn(self, m):    self._send(m, "WARN")
    def error(self, m):   self._send(m, "ERROR")

    def run_summary(self, portal: str, new: int, skipped: int,
                    errors: int, duration_sec: float):
        status = "SUCCESS" if errors == 0 else ("WARN" if new > 0 else "ERROR")
        msg = (
            f"*{portal}* — {status}\n"
            f"New jobs: {new}\n"
            f"Skipped (known): {skipped}\n"
            f"Errors: {errors}\n"
            f"Duration: {duration_sec:.1f}s"
        )
        self._send(msg, status)
