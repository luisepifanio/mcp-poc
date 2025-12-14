import logging
from collections.abc import Iterable
from typing import TypedDict, cast
from uuid import UUID

from fastcrud import FastCRUD
from result import Err, Ok, Result
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.entities import Event, EventTransition
from app.core.respository_event import EventRepository
from app.errors import ErrorCatalog, ErrorDetail

logger = logging.getLogger(__name__)


class DeleteTypedDict(TypedDict):  # All keys are optional by default
    deleted: list[UUID]
    not_found: list[UUID]
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

            from sqlalchemy.exc import IntegrityError

            for event in events:
                # Strategy: try to INSERT the event (session.add + flush) to avoid
                # accidental UPDATE of existing rows. If the insert fails due to a
                # uniqueness constraint, query the canonical row and return it.
                try:
                    # add event and flush to persist and populate PK
                    self.session.add(event)
                    await self.session.flush()

                    # if transitions exist (and are already loaded), attach them to the newly persisted event
                    # Avoid triggering lazy-loading (which may attempt IO in unexpected contexts).
                    transitions_attr = getattr(event, "__dict__", {}).get(
                        "transitions", None
                    )
                    if transitions_attr:
                        for transition in transitions_attr:
                            transition.event_id = event.id
                            self.session.add(transition)
                        # attach transitions without triggering lazy-loading by setting __dict__ directly
                        event.__dict__["transitions"] = transitions_attr
                    else:
                        event.__dict__["transitions"] = []

                    list_of_events.append(event)
                except IntegrityError:
                    # uniqueness constraint violated; the session's transaction is
                    # marked for rollback. Roll back the current transaction so
                    # we can safely execute subsequent SELECTs using this
                    # session (some DB drivers require the rollback before new
                    # statements can be run).
                    try:
                        await self.session.rollback()
                    except Exception:
                        # best-effort rollback; continue to attempt resolution
                        logger.debug("Rollback after IntegrityError failed or was unnecessary", exc_info=True)

                    # uniqueness constraint violated; attempt to fetch existing row
                    try:
                        found = None
                        if event.external_uuid is not None:
                            found = await self.event_crud.get(
                                self.session,
                                schema_to_select=Event,
                                return_as_model=True,
                                one_or_none=True,
                                external_uuid=event.external_uuid,
                                deleted_at__is=None,
                            )
                        if not found and event.id is not None:
                            found = await self.event_crud.get(
                                self.session,
                                schema_to_select=Event,
                                return_as_model=True,
                                one_or_none=True,
                                id=event.id,
                                deleted_at__is=None,
                            )
                        if isinstance(found, Event):
                            # Avoid lazy-loading transitions during conflict resolution; only use already-loaded data
                            transitions_attr = getattr(found, "__dict__", {}).get(
                                "transitions", None
                            )
                            if transitions_attr:
                                found.__dict__["transitions"] = transitions_attr
                            else:
                                found.__dict__["transitions"] = []
                            list_of_events.append(found)
                        else:
                            # If we cannot resolve the existing row, return Err
                            return Err(
                                ErrorDetail(
                                    error=ErrorCatalog.RUNTIME_FAILED.value,
                                    detail="Conflict detected but existing event could not be resolved",
                                )
                            )
                    except Exception as exc:  # pragma: no cover
                        logger.exception(
                            "Error while resolving existing event after insert"
                        )
                        return Err(
                            ErrorDetail(
                                error=ErrorCatalog.RUNTIME_FAILED.value, detail=str(exc)
                            )
                        )
            # logger.info(f"🟢 Love is good {list_of_events}")
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

    async def get_by_external_uuid(
        self, external_uuid: UUID
    ) -> Result[Event, ErrorDetail]:
        try:
            result = await self.event_crud.get(
                self.session,
                schema_to_select=Event,
                return_as_model=True,
                one_or_none=True,
                # return_total_count=True,
                external_uuid=external_uuid,
                deleted_at__is=None,  ## exclude soft-deleted
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
