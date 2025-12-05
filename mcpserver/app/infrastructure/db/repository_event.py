import logging
from collections.abc import Iterable
from typing import TypedDict, cast
from uuid import UUID

from fastcrud import FastCRUD
from fastcrud.types import UpsertMultiResponseDict, UpsertMultiResponseModel
from result import Err, Ok, Result
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.entities import Event, EventTransition
from app.core.respository_event import EventRepository
from app.errors import ErrorCatalog, ErrorDetail

logger = logging.getLogger(__name__)


class DeleteTypedDict(TypedDict):  # All keys are optional by default
    deleted: list
    not_found: list
    total_deleted: int
    total_not_found: int


class GetMultiTypedDict(TypedDict, total=False):
    data: list[Event]
    total_count: int


class AsyncSQLAlchemyEventRepository(EventRepository):
    def __init__(self, session: AsyncSession):
        self.session = session
        self.event_crud = FastCRUD(Event)
        self.transition_crud = FastCRUD(EventTransition)

    async def saveMany(self, events: list[Event]) -> Result[list[Event], ErrorDetail]:
        """Insert or update multiple Events using FastCRUD upsert (fallback to manual save)."""

        try:
            # Persist 1st level events
            list_of_events: list[Event] = []

            for event in events:
                # logger.info(f"🔴 pre poronga {type(event)}")
                result: (
                    UpsertMultiResponseDict | UpsertMultiResponseModel[Event] | None
                ) = await self.event_crud.upsert_multi(
                    self.session,
                    [event],
                    schema_to_select=Event,
                    return_as_model=True,
                    commit=False,
                )
                result = cast(UpsertMultiResponseModel[Event], result)
                created = (
                    result["data"][0]
                    if result and "data" in result and len(result["data"]) == 1
                    else None
                )

                logger.info(f"🔴 created event: {type(created)}")

                if isinstance(created, Event):
                    for transition in event.transitions:
                        transition.event_id = created.id
                        self.session.add(transition)
                    created.transitions = event.transitions or []

                    list_of_events.append(created)
            logger.info(f"🟢 Love is good {list_of_events}")
            return Ok(list_of_events)
        except Exception as exc:  # pragma: no cover - bubble up as Err
            logger.error(f"Error in saveMany: {exc}", exc_info=True)
            return Err(
                ErrorDetail(
                    error=ErrorCatalog.RUNTIME_FAILED.value,
                    detail=str(exc),
                )
            )

    async def delete_multi(
        self, events: list[Event]
    ) -> Result[DeleteTypedDict, ErrorDetail]:
        result: DeleteTypedDict = {
            "deleted": [],
            "not_found": [],
            "total_deleted": 0,
            "total_not_found": 0,
        }

        for event in events:
            delete_result = await self.delete(event)
            match delete_result:
                case Ok(deleted) if deleted is True:
                    result["deleted"].append(event.id)
                case Ok(deleted) if deleted is False:
                    result["not_found"].append(event.id)
                case Err(e):
                    return Err(e)
        result["total_deleted"] = len(result["deleted"])
        result["total_not_found"] = len(result["not_found"])
        return Ok(result)

    async def delete(self, event: Event, hard: bool = False) -> Result[bool, ErrorDetail]:
        """
        Delete an event.
        Returns
        Ok(True) if deleted
        Ok(False) if not found.
        Err(ErrorDetail) if error occurs i.e no id provided for event
        """
        if event.id is None:
            return Err(
                ErrorDetail(
                    error=ErrorCatalog.VALIDATION_FAILED.value,
                    detail="Event ID must be provided for deletion.",
                )
            )
        try:
            # try to delete and foundout if efectively deleted
            _dbEvent = await self.getOne(event.id)
            match _dbEvent:
                case Err(_):
                    return Ok(False)

            existing_event = _dbEvent.unwrap()

            if hard:
                await self.event_crud.db_delete(
                    db=self.session,
                    id=existing_event.id,
                    allow_multiple=False,
                    commit=False,
                )
            else:
                await self.event_crud.delete(
                    db=self.session,
                    id=existing_event.id,
                    allow_multiple=False,
                    commit=False,
                )

            await self.session.flush()
            return Ok(True)
        except Exception as exc:
            return Err(
                ErrorDetail(error=ErrorCatalog.RUNTIME_FAILED.value, detail=str(exc))
            )

    async def getMany(self, ids: list[UUID]) -> Result[list[Event], ErrorDetail]:
        """Retrieve multiple events by ids."""
        # WARN: this is an early optimization to remove duplicates
        _ids = list(dict.fromkeys(ids))
        try:
            result = await self.event_crud.get_multi(
                self.session,
                schema_to_select=Event,
                return_as_model=True,
                # return_total_count=True,
                id__in=_ids,
                deleted_at__is=None,  ## exclude soft-deleted
                limit=None,
            )

            list_of_events: list[Event] = []
            if result and "data" in result and isinstance(result["data"], Iterable):
                fetched_events = cast(list[Event], result["data"])
                logger.debug(f"Fetched {len(fetched_events)} events: {fetched_events}")
                list_of_events += fetched_events

            # query = select(Event).where(
            #     and_(col(Event.id).in_(_ids), col(Event.deleted_at).is_(None))
            # )
            # result = await self.session.execute(query)
            # events = list(result.scalars().all())
            return Ok(list_of_events)
        except Exception as exc:
            return Err(
                ErrorDetail(error=ErrorCatalog.RUNTIME_FAILED.value, detail=str(exc))
            )

    async def getByExternalUUID(self, external_uuid: UUID) -> Result[Event, ErrorDetail]:
        try:
            result = await self.event_crud.get(
                self.session,
                schema_to_select=Event,
                return_as_model=True,
                one_or_none=True,
                # return_total_count=True,
                external_uuid=external_uuid,
                deleted_at__is=None,  ## exclude soft-deleted
                limit=None,
            )

            if result is None:
                return Err(
                    ErrorDetail(
                        error=ErrorCatalog.NOT_FOUND.value,
                        detail=f"Event with external_uuid {external_uuid} not found.",
                    )
                )

            return Ok(result)
        except Exception as exc:
            return Err(
                ErrorDetail(error=ErrorCatalog.RUNTIME_FAILED.value, detail=str(exc))
            )
