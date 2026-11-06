import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://mismatch_desk:mismatch_desk_dev@localhost:5432/mismatch_desk",
)
