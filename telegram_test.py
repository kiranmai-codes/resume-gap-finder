from dotenv import load_dotenv
load_dotenv()
import os, urllib.request, urllib.error, urllib.parse

token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
chat = os.environ.get("TELEGRAM_CHAT_ID", "")

print("Token length:", len(token))
print("Token first 12:", token[:12])
print("Chat ID length:", len(chat))
print()

print("--- getMe ---")
try:
    r = urllib.request.urlopen(f"https://api.telegram.org/bot{token}/getMe", timeout=10)
    print(r.read().decode())
except urllib.error.HTTPError as e:
    print(f"HTTP {e.code}: {e.read().decode()}")
except Exception as e:
    print(f"{type(e).__name__}: {e}")

print()
print("--- sendMessage ---")
try:
    data = urllib.parse.urlencode({"chat_id": chat, "text": "Python test OK"}).encode()
    r = urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", data=data, timeout=10)
    print(r.read().decode())
except urllib.error.HTTPError as e:
    print(f"HTTP {e.code}: {e.read().decode()}")
except Exception as e:
    print(f"{type(e).__name__}: {e}")
