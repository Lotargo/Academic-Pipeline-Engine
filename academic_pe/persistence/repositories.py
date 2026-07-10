from __future__ import annotations

from typing import Generic, Protocol, Sequence, TypeVar
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from academic_pe.persistence.base import Base


ModelT = TypeVar("ModelT", bound=Base)


class Repository(Protocol[ModelT]):
    def add(self, entity: ModelT) -> None: ...

    def get(self, entity_id: UUID) -> ModelT | None: ...


class AsyncRepository(Protocol[ModelT]):
    async def add(self, entity: ModelT) -> None: ...

    async def get(self, entity_id: UUID) -> ModelT | None: ...


class TenantRepository(Protocol[ModelT]):
    def add(self, entity: ModelT) -> None: ...

    def get_for_workspace(self, workspace_id: UUID, entity_id: UUID) -> ModelT | None: ...

    def list_for_workspace(self, workspace_id: UUID) -> Sequence[ModelT]: ...


class AsyncTenantRepository(Protocol[ModelT]):
    async def add(self, entity: ModelT) -> None: ...

    async def get_for_workspace(
        self, workspace_id: UUID, entity_id: UUID
    ) -> ModelT | None: ...

    async def list_for_workspace(self, workspace_id: UUID) -> Sequence[ModelT]: ...


class SqlAlchemyTenantRepository(Generic[ModelT]):
    def __init__(self, session: Session, model: type[ModelT]):
        self.session = session
        self.model = model

    def add(self, entity: ModelT) -> None:
        self.session.add(entity)

    def _workspace_statement(self, workspace_id: UUID) -> Select:
        return select(self.model).where(self.model.workspace_id == workspace_id)

    def get_for_workspace(self, workspace_id: UUID, entity_id: UUID) -> ModelT | None:
        statement = self._workspace_statement(workspace_id).where(self.model.id == entity_id)
        return self.session.scalar(statement)

    def list_for_workspace(self, workspace_id: UUID) -> Sequence[ModelT]:
        return self.session.scalars(self._workspace_statement(workspace_id)).all()


class AsyncSqlAlchemyTenantRepository(Generic[ModelT]):
    def __init__(self, session: AsyncSession, model: type[ModelT]):
        self.session = session
        self.model = model

    async def add(self, entity: ModelT) -> None:
        self.session.add(entity)

    def _workspace_statement(self, workspace_id: UUID) -> Select:
        return select(self.model).where(self.model.workspace_id == workspace_id)

    async def get_for_workspace(
        self, workspace_id: UUID, entity_id: UUID
    ) -> ModelT | None:
        statement = self._workspace_statement(workspace_id).where(self.model.id == entity_id)
        return await self.session.scalar(statement)

    async def list_for_workspace(self, workspace_id: UUID) -> Sequence[ModelT]:
        result = await self.session.scalars(self._workspace_statement(workspace_id))
        return result.all()
