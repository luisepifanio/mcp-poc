"""Publisher abstraction for decoupling from specific frameworks."""

from abc import ABC, abstractmethod

from pydantic import BaseModel
from result import Result

from .types import JSONValue


class ErrorDetail:
    """Error detail for Result type."""

    def __init__(self, error: str, detail: str = "") -> None:
        self.error = error
        self.detail = detail

    def __repr__(self) -> str:
        return f"ErrorDetail(error={self.error!r}, detail={self.detail!r})"


class IPublisher(ABC):
    """Abstract interface for publishing messages to streams/topics."""

    @abstractmethod
    async def publish(
        self, message: JSONValue | BaseModel, stream: str
    ) -> Result[None, ErrorDetail]:
        """
        Publish a message to a stream/topic.

        Args:
            message: JSON-serializable value or Pydantic BaseModel
            stream: Stream/topic name where message will be published

        Returns:
            Result[None, ErrorDetail]: Ok if published successfully, Err otherwise
        """
        pass
