from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings, log_startup_configuration
from app.database import engine
from app.exceptions import (
    AppException,
    app_exception_handler,
    database_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.logging_config import setup_logging
from app.middleware.request_logging import RequestLoggingMiddleware
from app.routes import advisors, auth, customers, health, navs, portfolio, sips, transactions, users
from app.services.bootstrap_service import bootstrap_first_admin

setup_logging()
settings = get_settings()
log_startup_configuration(settings)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await bootstrap_first_admin(settings)
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    debug=settings.debug,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)

app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(SQLAlchemyError, database_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

app.include_router(health.router)
app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(users.router, prefix=settings.api_prefix)
app.include_router(advisors.router, prefix=settings.api_prefix)
app.include_router(customers.router, prefix=settings.api_prefix)
app.include_router(portfolio.schemes_router, prefix=settings.api_prefix)
app.include_router(portfolio.folios_router, prefix=settings.api_prefix)
app.include_router(portfolio.holdings_router, prefix=settings.api_prefix)
app.include_router(portfolio.summary_router, prefix=settings.api_prefix)
app.include_router(navs.router, prefix=settings.api_prefix)
app.include_router(sips.sips_router, prefix=settings.api_prefix)
app.include_router(sips.customer_sips_router, prefix=settings.api_prefix)
app.include_router(transactions.transactions_router, prefix=settings.api_prefix)
app.include_router(transactions.customer_transactions_router, prefix=settings.api_prefix)
