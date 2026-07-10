from __future__ import annotations

from dataclasses import dataclass
import os

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker


@dataclass(frozen=True, slots=True)
class DatabaseSettings:
    async_url: str
    sync_url: str
    echo: bool = False
    pool_pre_ping: bool = True

    @classmethod
    def from_env(cls) -> "DatabaseSettings":
        async_url = os.getenv("APE_DATABASE_ASYNC_URL")
        sync_url = os.getenv("APE_DATABASE_SYNC_URL")
        if not async_url or not sync_url:
            raise RuntimeError(
                "APE_DATABASE_ASYNC_URL and APE_DATABASE_SYNC_URL are required"
            )
        return cls(
            async_url=async_url,
            sync_url=sync_url,
            echo=os.getenv("APE_DATABASE_ECHO", "").lower() in {"1", "true", "yes"},
        )

    def safe_async_url(self) -> str:
        return make_url(self.async_url).render_as_string(hide_password=True)

    def safe_sync_url(self) -> str:
        return make_url(self.sync_url).render_as_string(hide_password=True)


def create_api_engine(settings: DatabaseSettings) -> AsyncEngine:
    return create_async_engine(
        settings.async_url,
        echo=settings.echo,
        pool_pre_ping=settings.pool_pre_ping,
    )


def create_worker_engine(settings: DatabaseSettings) -> Engine:
    return create_engine(
        settings.sync_url,
        echo=settings.echo,
        pool_pre_ping=settings.pool_pre_ping,
    )


def create_api_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker:
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


def create_worker_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False, autoflush=False)
