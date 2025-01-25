import os
from dotenv import load_dotenv

load_dotenv()

TENOR_API_KEY = os.getenv("TENOR_API_KEY", "LIVDSRZULELA")
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
DATABASE_URL = os.getenv("DATABASE_URL")
DEBUG_MODE = bool(os.getenv("DEBUG")) or False
