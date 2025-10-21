# MCP 3-Tier App (Podman Compose)

A simple 3-tier stack using Podman: React frontend (Vite + Tailwind), Flask API, and PostgreSQL. Login with a demo user, view and manage todos.

## Stack
- Frontend: React + Vite + Tailwind, served by Nginx
- Backend: Flask + Gunicorn
- Database: PostgreSQL 15 (seeded with demo user and todos)

## Directory Layout
- `frontend/`: React app and Dockerfile (build + Nginx runtime)
- `backend/`: Flask app, requirements, Dockerfile
- `db/`: PostgreSQL Dockerfile and init SQL to seed schema/data
- `podman-compose.yml`: Orchestration

## Quick Start
Make sure you have Podman and podman-compose installed.

```bash
cd /home/swapnil/mcp
podman-compose build
podman-compose up -d
# App will be available at http://localhost:${FRONTEND_PORT:-8082}
```

To see logs:
```bash
podman logs -f mcp_backend
podman logs -f mcp_frontend
podman logs -f mcp_db
```

## Credentials
- Email: `demo@example.com`
- Password: `demo123`

## Environment
Defaults are set via compose for local dev:
- `DB_HOST=db`, `DB_PORT=5432`, `DB_NAME=appdb`, `DB_USER=appuser`, `DB_PASSWORD=appsecret`
- `JWT_SECRET=supersecretjwtkeychangeme`, `JWT_EXPIRES_IN=86400`

## API
- `POST /api/auth/login` → `{ token }`
- `POST /api/auth/register` → create a user
- `GET /api/todos` → list todos (Bearer token)
- `POST /api/todos` → add todo
- `PATCH /api/todos/:id` → toggle done

## Development Notes
- Frontend dev server: `npm run dev` inside `frontend/` (proxies `/api` to backend)
- Backend runs via Gunicorn in the container. You can also run Flask locally by setting env vars and `flask --app app.main run` (ensure DB reachable).

## Cleanup
```bash
podman-compose down -v
```
