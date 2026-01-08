from __future__ import annotations

import pytest
from result import Err, Ok

from app.core.usecases.utils import async_chain


@pytest.mark.asyncio
async def test_async_chain_happy_path():
    async def add_one(x: int):
        return Ok(x + 1)

    res = Ok(1)
    out = await async_chain(res, add_one)
    assert out.is_ok()
    assert out.unwrap() == 2


@pytest.mark.asyncio
async def test_async_chain_short_circuits_on_err():
    async def add_one(x: int):
        # should not be called
        return Ok(x + 1)

    res = Err("fail")
    out = await async_chain(res, add_one)
    assert out.is_err()
    assert out.unwrap_err() == "fail"


@pytest.mark.asyncio
async def test_async_chain_multiple_links():
    async def add_one(x: int):
        return Ok(x + 1)

    async def times_two(x: int):
        return Ok(x * 2)

    res = Ok(3)
    step1 = await async_chain(res, add_one)
    step2 = await async_chain(step1, times_two)
    assert step2.is_ok()
    assert step2.unwrap() == (3 + 1) * 2
