import asyncio
from collections.abc import Callable
from typing import AsyncContextManager
from uuid import uuid4

import pytest
from result import Ok, Result

from app.core.unit_of_work import UnitOfWork
from app.core.usecases.event_usecases import (
    EnqueuedEventUseCaseInput,
    EnqueuedEventUseCaseOutput,
    EnqueueEventUseCase,
)
from app.errors import ErrorDetail


@pytest.mark.asyncio
async def test_enqueue_concurrent_idempotency(
    uow_factory: Callable[[], AsyncContextManager[UnitOfWork]],
) -> None:
    """Run two EnqueueEventUseCase executions concurrently using two DB sessions.

    Expectation:
    - Both executions return Ok
    - Both results reference the same canonical event (same id & external_uuid)
    - Only one event is ultimately persisted for that external_uuid
    """

    external = uuid4()

    async def run_in_session() -> Result[EnqueuedEventUseCaseOutput, ErrorDetail]:
        async with uow_factory() as uow:
            uc = EnqueueEventUseCase(uow)
            inp = EnqueuedEventUseCaseInput(
                name="concurrent-test", external_uuid=external, payload={"x": 1}
            )
            return await uc.execute(inp)

    # Run two coroutines concurrently, each with its own DB session
    results = await asyncio.gather(run_in_session(), run_in_session())

    # Both should be Ok and reference same canonical event
    for idx, r in enumerate(results):
        if not isinstance(r, Ok):
            # provide helpful diagnostic in test failure
            import pytest

            pytest.fail(f"Worker {idx} returned non-Ok result: {r}")

    out0 = results[0].unwrap()
    out1 = results[1].unwrap()

    assert out0.external_uuid == external
    assert out1.external_uuid == external
    assert out0.id == out1.id

    # Verify canonical event exists and can be fetched
    async with uow_factory() as uow:
        found = await uow.events.get_by_external_uuid(external)
        assert isinstance(found, Ok)
        persisted = found.unwrap()
        assert persisted.id == out0.id
