from __future__ import annotations

from typing import Awaitable, Callable, TypeVar

from result import Err, Result

T = TypeVar("T")
E = TypeVar("E")


async def async_chain(
    res: Result[T, E], fn: Callable[[T], Awaitable[Result[T, E]]]
) -> Result[T, E]:
    """Compose an async Result-returning function with short-circuiting.

    If `res` is `Err`, returns it immediately. Otherwise awaits `fn` with
    the unwrapped value and returns its Result.
    """
    if isinstance(res, Err):
        return res
    return await fn(res.unwrap())
