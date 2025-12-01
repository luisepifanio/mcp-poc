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
        result: Result[list[Event], ErrorDetail] = await self.getMany([id])
        match result:
            case Err(e):
                return Err(e)

        list_of_events = result.unwrap()
        if len(list_of_events) != 1:
            return Err(
                ErrorDetail(
                    error=ErrorCatalog.VALIDATION_FAILED.value,
                    detail=f"Found {len(list_of_events)} events for id {id}, please check schema definition.",
                )
            )
        return Ok(list_of_events[0])

    @abstractmethod
    async def getByExternalUUID(self, external_uuid: UUID) -> Result[Event, ErrorDetail]:
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
        """Inserts or updates multiple events in the repository.

        Args:
            events (list[Event]): The events to be saved.
        Returns:
            Result[list[Event], ErrorDetail]: The result of the save operation.
            A list of event instances if successful, or an ErrorDetail if an error occurs.
        """
        pass

    async def save(self, event: Event) -> Result[Event, ErrorDetail]:
        """Inserts or updates an event in the repository.

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
