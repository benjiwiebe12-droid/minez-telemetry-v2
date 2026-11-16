import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://minez:minez@localhost:5435/minez")
REDIS_URL    = os.getenv("REDIS_URL",    "redis://localhost:6380")
STREAM       = os.getenv("STREAM",       "minez:events")
