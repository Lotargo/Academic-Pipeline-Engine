from __future__ import annotations

from types import TracebackType
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Session, sessionmaker


class UnitOfWork(Protocol):
    session: Session

    def __enter__(self) -> "UnitOfWork": ...
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...


class AsyncUnitOfWork(Protocol):
    session: AsyncSession

    async def __aenter__(self) -> "AsyncUnitOfWork": ...
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...
    async def commit(self) -> None: ...
    async def rollback(self) -> None: ...


class SqlAlchemyUnitOfWork:
    def __init__(self, session_factory: sessionmaker[Session]):
        self._session_factory = session_factory

    def __enter__(self) -> "SqlAlchemyUnitOfWork":
        self.session = self._session_factory()
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        try:
            if exc_type is not None:
                self.rollback()
        finally:
            self.session.close()

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()


class AsyncSqlAlchemyUnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory

    async def __aenter__(self) -> "AsyncSqlAlchemyUnitOfWork":
        self.session = self._session_factory()
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        try:
            if exc_type is not None:
                await self.rollback()
        finally:
            await self.session.close()

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()
