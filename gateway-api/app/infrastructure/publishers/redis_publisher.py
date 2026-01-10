"""Redis implementation of the Publisher interface."""

import logging
from typing import Any

from faststream.redis import RedisBroker
from pydantic import BaseModel
from result import Err, Ok, Result

from app.core.publisher import ErrorDetail, IPublisher
from app.core.types import JSONValue

logger = logging.getLogger(__name__)


class RedisPublisher(IPublisher):
    """Publisher implementation using RedisBroker for Redis Streams."""

    def __init__(self, broker: RedisBroker) -> None:
        """
        Initialize RedisPublisher with a RedisBroker instance.

        Args:
            broker: FastStream RedisBroker instance
        """
        self.broker = broker

    async def publish(
        self, message: JSONValue | BaseModel, stream: str
    ) -> Result[None, ErrorDetail]:
        """
        Publish a message to a Redis Stream.

        Args:
            message: JSON-serializable value or Pydantic BaseModel
            stream: Redis Stream name

        Returns:
            Result[None, ErrorDetail]: Ok if published, Err on failure
        """
        try:
            # Convert BaseModel to dict if needed
            payload: Any = (
                message.model_dump() if isinstance(message, BaseModel) else message
            )

            # Publish to Redis Stream via broker
            await self.broker.publish(payload, stream=stream)

            logger.debug(
                f"Message published to stream '{stream}'", extra={"stream": stream}
            )
            return Ok(None)

        except Exception as e:
            error_msg = f"Failed to publish message to stream '{stream}': {str(e)}"
            logger.error(error_msg, extra={"stream": stream, "error": str(e)})
            return Err(ErrorDetail(error="PUBLISH_FAILED", detail=error_msg))
