# Changelog

## v0.6 NAV + Portfolio Valuation Engine

- Added `MutualFundNAV` history model and APIs under `/api/navs` with role-based access (`SUPER_ADMIN` mutate, `ADVISOR`/`COMPLIANCE` read).
- Added Alembic migration `0008_create_nav_history` with NAV uniqueness and positive-value constraints plus NAV indexes.
- Added NAV create/update/read/list schemas and repository/service layers.
- Added portfolio holdings valuation recalculation route at `/api/portfolio-holdings/recalculate-valuations` using latest scheme NAV.
- Updated portfolio valuation outputs so customer portfolio summary and advisor dashboard AUM use recalculated holding current values.
- Added v0.6 test coverage for NAV validation, duplication, RBAC, latest NAV usage in valuation recalculation, and Swagger route exposure.

## v0.5 Transactions Module

- Added investment transaction model, schemas, repository, service, and API routes under `/api/transactions`.
- Added customer transaction summary at `/api/customers/{customer_id}/transaction-summary`.
- Added Alembic migration `0007_create_transactions`.
- Added completed transaction holding sync for buy, SIP installment, switch-in, sell, and switch-out flows.
- Updated advisor dashboard recent transactions to return real completed investment transactions.
- Added transaction ownership, role, validation, filtering, soft-delete, summary, dashboard, and Swagger coverage.

## v0.4 SIP Module

- Added SIP model, schemas, repository, service, and API routes under `/api/sips`.
- Added customer SIP summary at `/api/customers/{customer_id}/sip-summary`.
- Added Alembic migration `0006_create_sips`.
- Updated advisor dashboard SIP metrics to use active monthly SIP data.
- Added SIP ownership, role, validation, soft-delete, summary, dashboard, and Swagger coverage.

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
