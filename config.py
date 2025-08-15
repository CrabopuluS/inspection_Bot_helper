
import os
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMINS = {int(x) for x in os.getenv("ADMINS","").split(",") if x.strip().isdigit()}
assert BOT_TOKEN, "BOT_TOKEN is required in .env"
