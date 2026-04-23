# Changes

## 2026-04-22

- Removed the `monitoring/` directory to avoid confusion.
- Kept a single dedicated database data directory: `data/db/`.
- Updated `docker-compose.yml`:
  - PostgreSQL now uses `./data/db:/var/lib/postgresql/data`.
  - Removed log bind mounts for PostgreSQL and bot.
- Removed `quickstart.sh`.
- Standardized startup flow to a single command:
  - `docker compose up -d`
- Updated documentation to reflect the new startup and storage layout.
