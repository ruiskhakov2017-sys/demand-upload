# Развёртывание

## Development

```bash
cp .env.example .env
docker compose up --build
docker compose run --rm api alembic upgrade head
```

## Production

1. Настроить домен и HTTPS.
2. Использовать сильные значения `APP_ENCRYPTION_KEY`, `SETUP_TOKEN`, `POSTGRES_PASSWORD`.
3. Не публиковать PostgreSQL и Redis наружу.
4. Запускать:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

