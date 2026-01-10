import logging
from collections.abc import Iterable
from typing import Any, TypedDict, cast
from uuid import UUID

from fastcrud import FastCRUD
from result import Err, Ok, Result
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlmodel import or_, select

from app.core.entities import Event, EventTransition
from app.core.repository_event import EventRepository
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
        self.session: AsyncSession = session
        self.event_crud: Any = FastCRUD(Event)
        self.transition_crud: Any = FastCRUD(EventTransition)

    # -------------------------------------------------------------------------
    # saveMany: Simple insert, fails on conflict (no conflict resolution)
    # -------------------------------------------------------------------------
    async def saveMany(self, events: list[Event]) -> Result[list[Event], ErrorDetail]:
        """Insert multiple Events. Fails on IntegrityError.

        This is the strict insert method. It does NOT handle conflicts.
        If a unique constraint is violated, the operation fails with an error.
        Use save_or_resolve() for idempotent insert-or-fetch semantics.
        """
        try:
            list_of_events: list[Event] = []

            for event in events:
                # If the event instance is not attached to this session, merge it
                try:
                    if not self.session.object_session(event):
                        event = await self.session.merge(event)
                except Exception:
                    # If merge fails for any reason, fall back to adding the original
                    pass

                self.session.add(event)
                await self.session.flush()

                # Ensure transitions collection exists
                self._ensure_transitions_collection(event)
                list_of_events.append(event)

            # Eager-load transitions to avoid lazy-load outside greenlet context
            list_of_events = await self._eager_load_transitions(list_of_events)

            return Ok(list_of_events)
        except Exception as exc:
            logger.error(f"Error in saveMany: {exc}", exc_info=True)
            return Err(
                ErrorDetail(error=ErrorCatalog.RUNTIME_FAILED.value, detail=str(exc))
            )

    # -------------------------------------------------------------------------
    # save_or_resolve: Uses SAVEPOINTs for conflict isolation
    # -------------------------------------------------------------------------
    async def save_or_resolve(
        self, events: list[Event]
    ) -> Result[list[Event], ErrorDetail]:
        """Insert or resolve multiple Events using SAVEPOINTs.

        Strategy:
        - For each event, create a SAVEPOINT (begin_nested) before inserting.
        - On IntegrityError: rollback only the savepoint (not the whole transaction),
          then resolve the existing canonical row.
        - This preserves the parent transaction for coordinated use case operations.
        """

        list_of_events: list[Event] = []
        list_of_conflicted_events: list[Event] = []
        for event in events:
            try:
                logger.info(
                    "Attempting to save_or_resolve event (id=%s, external_uuid=%s)",
                    event.id,
                    event.external_uuid,
                )
                self.session.begin_nested()
                self.session.add(event)
                await self.session.flush()
                # Insert succeeded
                self._ensure_transitions_collection(event)
                list_of_events.append(event)
            except IntegrityError:
                await self.session.rollback()  # ROLLBACK TO SAVEPOINT
                logger.warning(
                    "IntegrityError on save_or_resolve for event (id=%s, external_uuid=%s)",
                    event.id,
                    event.external_uuid,
                )
                list_of_conflicted_events.append(event)
            except Exception as exc:
                logger.error(f"Error in save_or_resolve: {exc}", exc_info=True)
                return Err(
                    ErrorDetail(error=ErrorCatalog.RUNTIME_FAILED.value, detail=str(exc))
                )

        if list_of_conflicted_events:
            logger.info(
                "Resolving %d conflicted events after IntegrityError",
                len(list_of_conflicted_events),
            )
            canonical_events = await self._resolve_this_events(list_of_conflicted_events)
            if canonical_events.is_err():
                logger.error(
                    "Failed to resolve existing events after conflict: %s",
                    canonical_events.unwrap_err(),
                )
                return Err(canonical_events.unwrap_err())
            res_list = canonical_events.unwrap()
            if len(res_list) != len(list_of_conflicted_events):
                logger.error(
                    "Could not fully resolve existing events after conflict: expected %d, got %d",
                    len(list_of_conflicted_events),
                    len(res_list),
                )
                return Err(
                    ErrorDetail(
                        error=ErrorCatalog.RUNTIME_FAILED.value,
                        detail="Conflict detected but existing events could not be fully resolved",
                    )
                )
            list_of_events.extend(res_list)

        return Ok(list_of_events)

    def _ensure_transitions_collection(self, event: Event) -> None:
        """Ensure transitions collection exists without breaking SQLAlchemy internals."""
        try:
            if getattr(event, "transitions", None) is None:
                event.transitions = []
        except Exception:
            pass

    async def save_or_resolve_one(self, event: Event) -> Result[Event, ErrorDetail]:
        """Insert or resolve a single Event using save_or_resolve() internally.

        Delegates to save_or_resolve() which uses SAVEPOINTs for safe conflict isolation.
        Converts the list result to a single event result.

        Strategy:
        - Calls save_or_resolve([event]) which handles:
          * SAVEPOINT creation before INSERT
          * IntegrityError → rollback savepoint (not whole TX)
          * Resolves existing canonical row on conflict
        - Extracts first element from the result list
        """
        resolved = await self.save_or_resolve([event])

        return resolved.and_then(
            lambda evs: Ok(evs[0])
            if len(evs) == 1
            else Err(
                ErrorDetail(
                    error=ErrorCatalog.NOT_FOUND.value,
                    detail=f"Event with id {event.id} not found after conflict",
                )
            )
            if len(evs) == 0
            else Err(
                ErrorDetail(
                    error=ErrorCatalog.RUNTIME_FAILED.value,
                    detail="Event resolution failed on uniqueness after conflict",
                )
            )
        )

    async def _resolve_this_events(
        self, list_of_events: list[Event]
    ) -> Result[list[Event], ErrorDetail]:
        uids = [ev.id for ev in list_of_events if ev.id is not None]
        external_uids = [
            ev.external_uuid for ev in list_of_events if ev.external_uuid is not None
        ]

        expression = (
            or_(
                cast(Any, Event.id).in_(uids),
                cast(Any, Event.external_uuid).in_(external_uids),
            )
            if len(uids) > 0 and len(external_uids) > 0
            else cast(Any, Event.id).in_(uids)
            if len(uids) > 0
            else cast(Any, Event.external_uuid).in_(external_uids)
        )
        try:
            query = (
                select(Event)
                .where(expression, cast(Any, Event.deleted_at).is_(None))
                .options(selectinload(cast(Any, Event.transitions)))
            )
            result = await self.session.execute(query)
            return Ok(list(result.scalars().all()))

        except Exception:
            logger.error(
                "Failed to eager-load transitions; continuing without load",
                exc_info=True,
            )
            return Err(
                ErrorDetail(
                    error=ErrorCatalog.RUNTIME_FAILED.value,
                    detail=f"Failed to resolve existing events on ids {uids} or external_uuids {external_uids}",
                )
            )

    async def _eager_load_transitions(self, list_of_events: list[Event]) -> list[Event]:
        """Eager-load transitions to prevent lazy-load outside greenlet context."""
        try:
            ids = [ev.id for ev in list_of_events if ev.id is not None]
            if not ids:
                return list_of_events

            query = (
                select(Event)
                .where(cast(Any, Event.id).in_(ids))
                .options(selectinload(cast(Any, Event.transitions)))
            )
            result = await self.session.execute(query)
            loaded = result.scalars().all()
            byid = {e.id: e for e in loaded}
            return [byid.get(ev.id, ev) for ev in list_of_events]
        except Exception:
            logger.debug(
                "Failed to eager-load transitions; continuing without load",
                exc_info=True,
            )
            return list_of_events

    async def delete_multi(
        self, events: list[Event]
    ) -> Result[dict[str, Any], ErrorDetail]:
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
        return Ok(cast(dict[str, Any], result))

    async def delete(self, event: Event, hard: bool = False) -> Result[bool, ErrorDetail]:
        if event.id is None:
            return Err(
                ErrorDetail(
                    error=ErrorCatalog.VALIDATION_FAILED.value,
                    detail="Event ID must be provided for deletion.",
                )
            )
        try:
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
        _ids = list(dict.fromkeys(ids))
        try:
            result = await self.event_crud.get_multi(
                self.session,
                schema_to_select=Event,
                return_as_model=True,
                id__in=_ids,
                deleted_at__is=None,
                limit=None,
            )

            list_of_events: list[Event] = []
            if result and "data" in result and isinstance(result["data"], Iterable):
                fetched_events = cast(list[Event], result["data"])
                list_of_events += fetched_events

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
                external_uuid=external_uuid,
                deleted_at__is=None,
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
