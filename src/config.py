import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_USED = os.getenv("DATABASE_USED")

DATABASE_URL = os.getenv("DATABASE_URL")
SECRET = os.getenv("SECRET")
REDIS_URL = os.getenv("REDIS_URL")

LINK_NO_USE_DAYS = 30
