# MF_MANAGER

Production-ready FastAPI SaaS backend starter with PostgreSQL, SQLAlchemy 2.0, Alembic migrations, JWT authentication, role-based access control, structured JSON logging, centralized error handling, and Docker.

## Features

- FastAPI application with `/health` and `/health/db`
- Async PostgreSQL access through SQLAlchemy 2.0 and `asyncpg`
- Alembic migration setup with an initial `users` table
- JWT access and refresh token authentication
- Bcrypt password hashing
- Role-based access control with `SUPER_ADMIN`, `ADVISOR`, `CUSTOMER`, and `COMPLIANCE`
- CORS middleware
- Request logging middleware with `X-Request-ID`
- Centralized JSON error responses
- Environment-based configuration using `.env`
- Docker Compose with app and PostgreSQL

## Run With Docker

```bash
cp .env.example .env
# edit .env and set JWT_SECRET_KEY and JWT_REFRESH_SECRET_KEY
docker compose up --build
```

The API will be available at:

```text
http://localhost:8010
```

API docs:

```text
http://localhost:8010/docs
```

Health check:

```bash
curl http://localhost:8010/health
```

Set `APP_PORT=8000` or another available port if you want a different host port.

## Local Development

Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create your local environment file:

```bash
cp .env.example .env
```

Set `JWT_SECRET_KEY` and `JWT_REFRESH_SECRET_KEY` in `.env` before starting the app. Each value must be a different random string of at least 32 characters.

Start a PostgreSQL instance reachable from the host and update `DATABASE_URL` in `.env` if needed.

The full Docker stack does not expose PostgreSQL to the host by default; the app reaches it through the Docker network at `postgres:5432`. If you want to run FastAPI on the host while using the Compose PostgreSQL service, add a local port mapping for `postgres` or point `DATABASE_URL` at another PostgreSQL instance.

Run migrations:

```bash
alembic upgrade head
```

Start the app:

```bash
uvicorn app.main:app --reload
```

Run tests:

```bash
pytest
```

## Auth Flow

Register a user:

```bash
curl -X POST http://localhost:8010/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"strongpassword","full_name":"Example User"}'
```

Login:

```bash
curl -X POST http://localhost:8010/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"strongpassword"}'
```

Refresh:

```bash
curl -X POST http://localhost:8010/api/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"<refresh-token>"}'
```

Current user:

```bash
curl http://localhost:8010/api/auth/me \
  -H "Authorization: Bearer <access-token>"
```

Use the returned bearer token for authenticated routes.

To bootstrap a `SUPER_ADMIN` user for `/api/users` routes, set both values before starting the app:

```bash
FIRST_ADMIN_EMAIL=admin@example.com
FIRST_ADMIN_PASSWORD=strongadminpassword
```

## Advisor Module

Advisor routes require a bearer token for a `SUPER_ADMIN` or `ADVISOR` user.

Create advisor profile:

```bash
curl -X POST http://localhost:8010/api/advisors/profile \
  -H "Authorization: Bearer <access-token>" \
  -H "Content-Type: application/json" \
  -d '{"firm_name":"MF Advisory","arn_number":"ARN12345","license_type":"ARN","target_region":"West India","business_address":"123 Finance Street, Mumbai"}'
```

Read and update profile:

```bash
curl http://localhost:8010/api/advisors/profile \
  -H "Authorization: Bearer <access-token>"

curl -X PATCH http://localhost:8010/api/advisors/profile \
  -H "Authorization: Bearer <access-token>" \
  -H "Content-Type: application/json" \
  -d '{"target_region":"South India"}'
```

Dashboard summary:

```bash
curl http://localhost:8010/api/advisors/dashboard-summary \
  -H "Authorization: Bearer <access-token>"
```

## Project Structure

```text
app/
  main.py
  config.py
  database.py
  security.py
  dependencies.py
  exceptions.py
  logging_config.py
  models/
  schemas/
  routes/
  services/
  repositories/
  middleware/
  utils/
alembic/
tests/
.env.example
requirements.txt
Dockerfile
docker-compose.yml
README.md
```
