# MF_MANAGER

Production-ready FastAPI SaaS backend starter with PostgreSQL, SQLAlchemy 2.0, Alembic migrations, JWT authentication, role-based access control, structured JSON logging, centralized error handling, and Docker.

## Features

- FastAPI application with `/health` and `/health/db`
- Async PostgreSQL access through SQLAlchemy 2.0 and `asyncpg`
- Alembic migration setup through portfolio and folio tables
- JWT access and refresh token authentication
- Bcrypt password hashing
- Role-based access control with `SUPER_ADMIN`, `ADVISOR`, `CUSTOMER`, and `COMPLIANCE`
- CORS middleware
- Request logging middleware with `X-Request-ID`
- Centralized JSON error responses
- Environment-based configuration using `.env`
- Docker Compose with app and PostgreSQL
- Advisor profiles, customer/KYC records, mutual fund schemes, folios, and portfolio holdings
- Customer portfolio summary and advisor dashboard AUM from active holdings

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

`total_aum` is calculated from active `portfolio_holdings.current_value`. SIP and transaction fields remain placeholders until those modules are added.

## Customer Module

Customer routes require a bearer token. `ADVISOR` users can manage their own customers, `SUPER_ADMIN` can manage all customers, and `COMPLIANCE` can read only.

```bash
curl -X POST http://localhost:8010/api/customers \
  -H "Authorization: Bearer <access-token>" \
  -H "Content-Type: application/json" \
  -d '{"full_name":"Test Customer","email":"customer@example.com","phone":"+15555550123","pan_number":"ABCDE1234F","date_of_birth":"1990-01-01","risk_profile":"MODERATE"}'
```

## Portfolio + Folio Module

v0.3 adds mutual fund schemes, customer folios, portfolio holdings, and customer portfolio summary.

Scheme catalog:

```bash
curl -X POST http://localhost:8010/api/schemes \
  -H "Authorization: Bearer <super-admin-token>" \
  -H "Content-Type: application/json" \
  -d '{"scheme_code":"MF001","scheme_name":"Bluechip Fund","amc_name":"Example AMC","category":"Equity","sub_category":"Large Cap","risk_level":"High"}'

curl http://localhost:8010/api/schemes \
  -H "Authorization: Bearer <access-token>"
```

Folios:

```bash
curl -X POST http://localhost:8010/api/folios \
  -H "Authorization: Bearer <advisor-token>" \
  -H "Content-Type: application/json" \
  -d '{"customer_id":"<customer-id>","folio_number":"FOLIO-123","platform":"RTA"}'
```

Holdings:

```bash
curl -X POST http://localhost:8010/api/portfolio-holdings \
  -H "Authorization: Bearer <advisor-token>" \
  -H "Content-Type: application/json" \
  -d '{"customer_id":"<customer-id>","folio_id":"<folio-id>","scheme_id":"<scheme-id>","invested_amount":"10000.00","current_value":"11250.00","units":"100.0000","average_nav":"100.0000","current_nav":"112.5000","valuation_date":"2026-05-17"}'
```

Portfolio summary:

```bash
curl http://localhost:8010/api/customers/<customer-id>/portfolio-summary \
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
