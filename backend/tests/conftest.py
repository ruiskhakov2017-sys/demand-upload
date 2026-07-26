import os

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("APP_ENCRYPTION_KEY", "test-encryption-key-for-unit-tests-only")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://dgu:dgu@postgres:5432/dgu")
os.environ.setdefault("REDIS_URL", "redis://redis:6379/0")
os.environ.setdefault("SESSION_COOKIE_SECURE", "false")

