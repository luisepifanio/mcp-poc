from abc import ABC, abstractmethod

from .repository_event import EventRepository


class UnitOfWork(ABC):
    """Abstract base class for Unit of Work pattern.

    Provides a transactional boundary for repository operations.
    Implementations must provide concrete repositories (events)
    and transaction management (commit, rollback).
    """

    @property
    @abstractmethod
    def events(self) -> EventRepository:
        """Returns the event repository."""
        pass

    @abstractmethod
    async def __aenter__(self) -> "UnitOfWork":
        """Enter async context manager."""
        pass

    @abstractmethod
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: str | None,
    ) -> None:
        """Exit async context manager, commit or rollback based on exception."""
        pass

    @abstractmethod
    async def commit(self) -> None:
        """Commit the current transaction."""
        pass

    @abstractmethod
    async def rollback(self) -> None:
        """Rollback the current transaction."""
        pass
