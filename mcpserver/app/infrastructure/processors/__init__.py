"""
Callback payload models for long-running processors.

Unified Pydantic models for all callbacks with processor-specific extensions.
Published to: "event-result-{event_id}" (dynamic, per event)
"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TaskCallbackPayload(BaseModel):
    """
    Unified callback structure for all long-running processors.

    Published to: Redis stream "event-result-{event_id}"

    Attributes:
        event_id: ID of the event being processed
        status: "success" | "failed"
        result: Task execution result (if successful)
        error: Error message (if failed)
        metadata: Processor-specific metadata
    """

    event_id: UUID = Field(..., description="Event ID being processed")
    status: str = Field(
        ...,
        description="Task status: 'success' or 'failed'",
        pattern="^(success|failed)$",
    )
    result: dict[str, Any] | None = Field(
        default=None, description="Task result data (if successful)"
    )
    error: str | None = Field(default=None, description="Error message (if failed)")
    metadata: dict[str, Any] | None = Field(
        default=None, description="Processor-specific metadata"
    )

    model_config = ConfigDict(
        extra="allow",  # Allow extra fields for extensibility
        json_schema_extra={
            "example": {
                "event_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "success",
                "result": {"data": "..."},
                "error": None,
                "metadata": {"duration_ms": 5000},
            }
        },
    )


class ScrapingTaskCallbackPayload(TaskCallbackPayload):
    """
    Scraping processor specific callback payload.

    Extends TaskCallbackPayload with scraping-specific metadata.
    """

    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Scraping-specific metadata: url, selector_count, duration_ms, etc.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "event_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "success",
                "result": {"selectors": 42, "elements": [...]},
                "error": None,
                "metadata": {
                    "url": "https://example.com",
                    "selector_count": 42,
                    "duration_ms": 5000,
                    "retry_count": 0,
                },
            }
        }
    )


class MlInferenceCallbackPayload(TaskCallbackPayload):
    """
    ML inference processor specific callback payload.

    Extends TaskCallbackPayload with ML-specific metadata.
    """

    metadata: dict[str, Any] | None = Field(
        default=None,
        description="ML-specific metadata: model_id, confidence, inference_ms, etc.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "event_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "success",
                "result": {"prediction": "category_a", "confidence": 0.95},
                "error": None,
                "metadata": {
                    "model_id": "model_v2.1",
                    "confidence": 0.95,
                    "inference_ms": 250,
                    "batch_id": "batch_001",
                },
            }
        }
    )
