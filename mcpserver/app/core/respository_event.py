from abc import ABC, abstractmethod
from uuid import UUID

from result import Err, Ok, Result

from app.errors import ErrorCatalog, ErrorDetail

from .entities import Event


class EventRepository(ABC):
    @abstractmethod
    async def delete(self, event: Event, hard: bool = False) -> Result[bool, ErrorDetail]:
        """Deletes an event from the repository.

        Args:
            event (Event): The event to be deleted.

        Returns:
            Result[bool, ErrorDetail]: The result of the delete operation.
            A boolean indicating success if successful, or an ErrorDetail if an error occurs.
            True if the event was deleted, False otherwise (e.g., if the event was not found).
        """
        pass

    async def getOne(self, id: UUID) -> Result[Event, ErrorDetail]:
        """Retrieves an event by its ID.

        Args:
            id (UUID): The unique identifier of the event.

        Returns:
            Result[Event, ErrorDetail]: The result of the get operation.
            An event instance if found, or an ErrorDetail if not found or an error occurs.
        """
        # Call getMany and propagate Err if it failed
        result: Result[list[Event], ErrorDetail] = await self.getMany([id])
        match result:
            case Err(e):
                return Err(e)
        # Explicitly type the unpacked result for linters/readers
        list_of_events: list[Event] = result.unwrap()

        # Behavior contract (explicit):
        # - If no events -> return Err(NOT_FOUND) with detail "Event with id {id} not found."
        # - If exactly one -> return Ok(event)
        # - If more than one -> return Err(VALIDATION_FAILED) with detail
        #   "Found {n} events for id {id}, please check schema definition."

        if len(list_of_events) == 0:
            return Err(
                ErrorDetail(
                    error=ErrorCatalog.NOT_FOUND.value,
                    detail=f"Event with id {id} not found.",
                )
            )

        if len(list_of_events) > 1:
            return Err(
                ErrorDetail(
                    error=ErrorCatalog.VALIDATION_FAILED.value,
                    detail=f"Found {len(list_of_events)} events for id {id}, please check schema definition.",
                )
            )

        return Ok(list_of_events[0])

    @abstractmethod
    async def get_by_external_uuid(
        self, external_uuid: UUID
    ) -> Result[Event, ErrorDetail]:
        """Retrieves an event by its external UUID.

        Args:
            external_uuid (UUID): The external unique identifier of the event.

        Returns:
            Result[Event, ErrorDetail]: The result of the get operation.
            An event instance if found, or an ErrorDetail if not found or an error occurs.
        """
        pass

    @abstractmethod
    async def getMany(self, ids: list[UUID]) -> Result[list[Event], ErrorDetail]:
        """Retrieves multiple events by their IDs.

        Args:
            ids (list[UUID]): A list of unique identifiers for the events.

        Returns:
            Result[list[Event], ErrorDetail]: The result of the getMany operation.
            A list of event instances if found, or an ErrorDetail if an error occurs.
        """
        pass

    @abstractmethod
    async def saveMany(self, events: list[Event]) -> Result[list[Event], ErrorDetail]:
        """Inserts multiple events in the repository.

        This is the basic insert operation. It will FAIL on integrity errors
        (e.g., duplicate unique keys) without attempting to resolve conflicts.
        Use this when you want strict insert-only semantics.

        Args:
            events (list[Event]): The events to be saved.
        Returns:
            Result[list[Event], ErrorDetail]: The result of the save operation.
            A list of event instances if successful, or an ErrorDetail if an error occurs.
        """
        pass

    @abstractmethod
    async def save_or_resolve(
        self, events: list[Event]
    ) -> Result[list[Event], ErrorDetail]:
        """Inserts events or resolves to existing ones on conflict.

        This method uses SAVEPOINTs to isolate each insert attempt. If an
        IntegrityError occurs (e.g., duplicate unique key), only the savepoint
        is rolled back, NOT the entire transaction. The existing canonical
        row is then fetched and returned.

        Use this for idempotent operations where conflicts should resolve
        gracefully without breaking the parent transaction.

        Args:
            events (list[Event]): The events to be saved or resolved.
        Returns:
            Result[list[Event], ErrorDetail]: A list of event instances
            (either newly inserted or existing canonical rows).
        """
        pass

    async def save(self, event: Event) -> Result[Event, ErrorDetail]:
        """Inserts a single event in the repository.

        Delegates to saveMany(). This is a strict insert operation that will
        FAIL on integrity errors. For idempotent save-or-resolve semantics,
        use save_or_resolve() instead.

        Args:
            event (Event): The event to be saved.

        Returns:
            Result[Event, ErrorDetail]: The result of the save operation.
            An event instance if successful, or an ErrorDetail if an error occurs.
        """
        result: Result[list[Event], ErrorDetail] = await self.saveMany([event])
        match result:
            case Err(e):
                return Err(e)

        list_of_events = result.unwrap()
        if len(list_of_events) != 1:
            return Err(
                ErrorDetail(
                    error=ErrorCatalog.VALIDATION_FAILED.value,
                    detail=f"Event {event} could not be saved",
                )
            )
        return Ok(list_of_events[0])
