# Changelog

## v0.3 Portfolio + Folio Module

- Added mutual fund schemes, customer folios, and portfolio holdings.
- Added soft-delete repository and service flows with advisor ownership checks.
- Added customer portfolio summary and advisor dashboard AUM from active holdings.
- Added Alembic migration `0005_create_portfolio_folio`.
- Added API routes for `/api/schemes`, `/api/folios`, `/api/portfolio-holdings`, and customer portfolio summary.

## v0.2 Customer + KYC

- Added customer records, KYC status, risk profile, customer APIs, and advisor dashboard customer counts.

## v0.1 Foundation

- Added FastAPI foundation, async SQLAlchemy, PostgreSQL migrations, JWT auth, role checks, and Docker Compose.
