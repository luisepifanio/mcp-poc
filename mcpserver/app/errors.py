import enum

from pydantic import BaseModel


class ErrorCatalog(str, enum.Enum):
    GENERIC_FAIL = "GENERIC_FAIL"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    NOT_FOUND = "NOT_FOUND"
    RUNTIME_FAILED = "RUNTIME_FAILED"
    USE_CASE_EXECUTION_FAILED = "USE_CASE_EXECUTION_FAILED"
    UNIMPLENTED = "UNIMPLENTED"


class ErrorDetail(BaseModel):
    error: str
    detail: str
    metadata: dict | None = None


class ErrorDetailBuilder:
    def __init__(self):
        self._error: ErrorCatalog | None = None
        self._detail: str | None = None
        self._metadata: dict = {}

    def error(self, error: ErrorCatalog):
        self._error = error
        return self

    def detail(self, detail: str):
        self._detail = detail
        return self

    def metadata(self, metadata: dict):
        self._metadata.update(metadata or {})
        return self

    def build(self) -> ErrorDetail:
        if self._error is None:
            raise ValueError("ErrorDetailBuilder: error is required")
        if self._detail is None:
            raise ValueError("ErrorDetailBuilder: detail is required")

        return ErrorDetail(
            error=self._error.value, detail=self._detail, metadata=self._metadata
        )


class AppError(Exception):
    def __init__(
        self,
        message: str,
        error: ErrorCatalog = ErrorCatalog.RUNTIME_FAILED,
        metadata: dict | None = None,
    ):
        # Call the base class constructor with the parameters it needs
        super().__init__(message)
        self._detail = message
        self.error = error
        self.metadata: dict | None = metadata

    def as_error_detail(self) -> ErrorDetail:
        """
        Convert the exception to an ErrorDetail.
        """
        return (
            ErrorDetailBuilder()
            .error(self.error)
            .detail(self._detail)
            .metadata(self.metadata or {})
            .build()
        )
