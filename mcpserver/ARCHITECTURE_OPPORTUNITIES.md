# 🏗️ Top 5 Architecture Improvement Opportunities
## Clean Architecture & SOLID Principles Analysis

**Date**: 2025-12-31  
**Scope**: Violations of Clean Architecture and SOLID principles  
**Target Audience**: Development team (reference for best practices)  
**Status**: Opportunities identified for strategic refactoring

---

## 📊 Executive Summary

| Rank | Opportunity | SOLID Violation | Impact | Effort | Priority |
| ---- | ----------- | --------------- | ------ | ------ | -------- |
| #1 | **Course UseCases** | SRP + DIP | High | ⭐⭐ | 🔴 CRITICAL |
| #2 | **Bare DB Layer Access** | DIP + ISP | High | ⭐⭐⭐ | 🔴 CRITICAL |
| #3 | **Router Infrastructure Coupling** | DIP + SRP | Medium | ⭐⭐ | 🟠 MEDIUM |
| #4 | **UseCase Result Type Inconsistency** | LSP | Medium | ⭐⭐ | 🟠 MEDIUM |
| #5 | **Settings Global Singleton** | DIP + SRP | Low-Medium | ⭐ | 🟡 LOW |

---

## 🎯 #1: Course UseCases - Dead Code & Incomplete Implementation
### VIOLATIONS: Single Responsibility + Dependency Inversion
### IMPACT: 🔴 CRITICAL | EFFORT: ⭐⭐ (1 hour)

### Current State

**File**: `app/core/usecases/course_usecases.py` (68% coverage, 22 statements)

```python
# ❌ PROBLEMATIC CODE
class GetAsyncCourseUseCase(AsyncUseCase[GetCourseUseCaseInput, list[Course]]):
    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    async def execute(self, input_port: GetCourseUseCaseInput) -> list[Course]:
        async with self.uow:
            if input_port.force_scrap:
                pass  # TODO: implement force scrap logic ❌ UNFINISHED
            return await self.uow.courses.get_courses(input_port.courses)


class CreateCourseUseCase:
    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    async def execute(self, course: Course) -> None:
        async with self.uow:
            await self.uow.courses.save_course(course)
```

### Problems Identified

**1. Incomplete TODO Implementation** (SRP Violation)
- `force_scrap` logic is a stub with `pass`
- Suggests unfinished feature or unclear requirements
- Creates cognitive load: "Is this feature needed?"

**2. Two Classes, No Cohesion** (SRP Violation)
- `GetAsyncCourseUseCase` and `CreateCourseUseCase` are loosely related
- No shared abstraction or pattern
- Mixed concerns: Get vs Create with different signatures

**3. No Error Handling** (Inconsistent with Event UseCases)
- Event UseCases return `Result[T, ErrorDetail]`
- Course UseCases return raw values or None
- Violates **Liskov Substitution Principle**: Subclasses not substitutable

**4. Unused in Routes** (Dead Code)
- No routes reference these UseCases
- Repository exists (`course_crud`) but UseCases aren't connected
- Violates **"Lo que no está, no falla"** principle

### Why This Matters for the Template

❌ **Bad Template Pattern**:
- Shows incomplete TODO instead of working example
- Demonstrates error handling inconsistency (Result vs raw values)
- Creates confusion: "Should I follow this pattern or the Event one?"

### Recommended Solution

**Option A: REMOVE** (Recommended) - Per "Lo que no está no falla" principle

```bash
# Delete files that are not used
rm app/core/usecases/course_usecases.py
rm app/infrastructure/api/course_routes.py
rm app/core/repositories.py  # Only used by course_usecases

# Update imports in app/infrastructure/api/main.py
# Remove: from .course_routes import router
# Remove: app.include_router(router)
```

**Impact**: -25 lines, -68% coverage loss (offset by removing untested code)

**Option B: COMPLETE** (If course feature is planned)

```python
# ✅ GOOD: Complete implementation with Result type
class GetCourseUseCaseInput(BaseModel):
    course_ids: list[str]
    force_scrap: bool = False

class GetCourseUseCaseOutput(BaseModel):
    courses: list[Course]
    total: int

class GetAsyncCourseUseCase(
    AsyncUseCase[GetCourseUseCaseInput, Result[GetCourseUseCaseOutput, ErrorDetail]]
):
    def __init__(self, uow: IUnitOfWork):  # DIP: Abstract interface
        self.uow = uow

    async def execute(
        self, input: GetCourseUseCaseInput
    ) -> Result[GetCourseUseCaseOutput, ErrorDetail]:
        try:
            async with self.uow as uow:
                # Implement force_scrap logic with proper error handling
                if input.force_scrap:
                    # Trigger web scraping here
                    pass
                
                courses = await uow.courses.get_many(input.course_ids)
                return Ok(GetCourseUseCaseOutput(
                    courses=courses,
                    total=len(courses)
                ))
        except Exception as exc:
            return Err(ErrorDetail(...))
```

**Impact**: +50 lines, complete feature, testable, consistent pattern

### Template Lesson

✅ **Always follow this pattern**:
- Complete implementations with error handling
- No TODO stubs in production code
- Consistent Result[T, ErrorDetail] across all UseCases
- If feature is not ready, remove it entirely

---

## 🎯 #2: Bare DB Layer Access in Endpoints
### VIOLATIONS: Dependency Inversion + Interface Segregation
### IMPACT: 🔴 CRITICAL | EFFORT: ⭐⭐⭐ (2-3 hours)

### Current State

**File**: `app/infrastructure/api/pingrouter.py`

```python
# ❌ PROBLEMATIC CODE: Direct infrastructure access
class PingRouter(BaseRouter):
    def __init__(self, redis_broker: RedisBroker) -> None:  # Infrastructure type!
        super().__init__()
        self.redis_broker = redis_broker  # Direct dependency on FastStream
        self._router.add_api_route("/ping", self.ping, methods=["GET"])

    async def ping(self) -> str:
        # Direct access to Redis internals
        if (
            not hasattr(self.redis_broker, "_connection")
            or self.redis_broker._connection is None
            or self.redis_broker._connection.connection is None
        ):
            await self.redis_broker.connect()

        # Publishing directly to Redis
        await self.redis_broker.publish(
            {"message": "Hi there from /ping endpoint"}, stream="in-subject"
        )

        return "pong"
```

**File**: `app/infrastructure/db/connection.py`

```python
# ❌ PROBLEMATIC: Global singleton, tight coupling
settings = getAppSettings()  # Global call in module scope
async_engine: AsyncEngine = create_async_engine(
    settings.database_url,  # Direct database setup
    ...
)

AsyncSessionLocal = async_sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=async_engine,  # Global binding
    ...
)
```

### Problems Identified

**1. Infrastructure Types in API Layer** (DIP Violation)
```python
# ❌ BAD: API depends on concrete FastStream type
def __init__(self, redis_broker: RedisBroker):
    self.redis_broker = redis_broker

# ✅ GOOD: API depends on abstract interface
def __init__(self, message_broker: IMessageBroker):
    self.broker = message_broker
```

**2. Direct Access to Internals** (ISP Violation)
```python
# ❌ BAD: Accessing private implementation details
if (
    not hasattr(self.redis_broker, "_connection")  # Private attr!
    or self.redis_broker._connection is None
    or self.redis_broker._connection.connection is None
):
    await self.redis_broker.connect()

# ✅ GOOD: Use abstraction
if not await self.broker.is_connected():
    await self.broker.connect()
```

**3. Global Module-Level Initialization** (DIP Violation)
```python
# ❌ BAD: Settings injected at module import time
settings = getAppSettings()  # Executed when module loads
async_engine = create_async_engine(settings.database_url, ...)

# ✅ GOOD: Lazy initialization with DI
class DatabaseConnection:
    def __init__(self, settings: AppSettings):
        self.settings = settings
        self.engine: AsyncEngine | None = None
    
    async def get_engine(self) -> AsyncEngine:
        if self.engine is None:
            self.engine = create_async_engine(self.settings.database_url, ...)
        return self.engine
```

**4. Testability Issues**
```python
# ❌ BAD: Hard to mock Redis in tests
async def test_ping():
    router = PingRouter(redis_broker)  # Must use real broker
    result = await router.ping()
    # Can't easily mock Redis

# ✅ GOOD: Inject mock interface
async def test_ping(message_broker_mock: MagicMock):
    router = PingRouter(message_broker_mock)
    result = await router.ping()
    message_broker_mock.is_connected.assert_called_once()
```

### Why This Matters for the Template

❌ **Bad Template Pattern**:
- Shows tight coupling to infrastructure libraries (RedisBroker, SQLAlchemy)
- Demonstrates accessing private attributes (`_connection`)
- Creates unmockable code that's hard to test
- Makes it impossible to swap implementations (Redis → RabbitMQ, SQLite → PostgreSQL)

### Recommended Solution

**Step 1: Create Abstraction Interfaces**

```python
# app/core/message_broker.py
from abc import ABC, abstractmethod

class IMessageBroker(ABC):
    """Abstraction for message brokers (Redis, RabbitMQ, etc.)"""
    
    @abstractmethod
    async def is_connected(self) -> bool:
        """Check if broker is connected."""
        pass
    
    @abstractmethod
    async def connect(self) -> None:
        """Establish connection."""
        pass
    
    @abstractmethod
    async def publish(self, message: dict, channel: str) -> None:
        """Publish message to channel."""
        pass


# app/core/database.py
from abc import ABC, abstractmethod

class IDatabase(ABC):
    """Abstraction for database connections."""
    
    @abstractmethod
    async def get_session(self) -> AsyncSession:
        """Get database session."""
        pass
    
    @abstractmethod
    async def setup_models(self) -> None:
        """Initialize database schema."""
        pass
```

**Step 2: Implement Adapters**

```python
# app/infrastructure/message_broker_adapter.py
from app.core.message_broker import IMessageBroker
from faststream.redis import RedisBroker

class RedisMessageBrokerAdapter(IMessageBroker):
    def __init__(self, broker: RedisBroker):
        self._broker = broker
    
    async def is_connected(self) -> bool:
        return (
            hasattr(self._broker, "_connection")
            and self._broker._connection is not None
        )
    
    async def connect(self) -> None:
        if not await self.is_connected():
            await self._broker.connect()
    
    async def publish(self, message: dict, channel: str) -> None:
        await self._broker.publish(message, stream=channel)


# app/infrastructure/database_adapter.py
from app.core.database import IDatabase

class SQLAlchemyDatabaseAdapter(IDatabase):
    def __init__(self, settings: AppSettings):
        self.settings = settings
        self._engine: AsyncEngine | None = None
        self._session_maker: async_sessionmaker | None = None
    
    async def get_session(self) -> AsyncSession:
        if self._session_maker is None:
            await self._initialize()
        return self._session_maker()  # type: ignore
    
    async def setup_models(self) -> None:
        if self._engine is None:
            await self._initialize()
        async with self._engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
    
    async def _initialize(self) -> None:
        self._engine = create_async_engine(
            self.settings.database_url,
            ...
        )
        self._session_maker = async_sessionmaker(
            bind=self._engine,
            ...
        )
```

**Step 3: Update API Layer**

```python
# app/infrastructure/api/pingrouter.py
from app.core.message_broker import IMessageBroker  # Abstract!

class PingRouter(BaseRouter):
    def __init__(self, broker: IMessageBroker) -> None:  # DIP!
        super().__init__()
        self.broker = broker
        self._router.add_api_route("/ping", self.ping, methods=["GET"])

    async def ping(self) -> dict:
        await self.broker.connect()  # Clean interface
        await self.broker.publish(
            {"message": "Hi from /ping"},
            channel="in-subject"
        )
        return {"status": "pong"}
```

**Impact**:
- +80-120 lines (abstraction interfaces + adapters)
- Fully testable with mocks
- Can swap implementations without changing API code
- Follows Dependency Inversion Principle

### Template Lesson

✅ **Always follow this pattern for infrastructure**:
1. Define abstract interface in `app/core/`
2. Implement adapter in `app/infrastructure/`
3. Inject interface into API/UseCase layer
4. Never directly reference infrastructure types (RedisBroker, AsyncEngine)
5. Hide implementation details behind abstraction

---

## 🎯 #3: Router Dependency Injection Inconsistency
### VIOLATIONS: Dependency Inversion + Single Responsibility
### IMPACT: 🟠 MEDIUM | EFFORT: ⭐⭐ (1.5 hours)

### Current State

**File**: `app/infrastructure/api/routes.py`

```python
# ❌ PROBLEMATIC: Magic factory, unclear dependencies
def get_routers(
    defaults: Sequence[BaseRouter | APIRouter] | None = None,
) -> Sequence[BaseRouter | APIRouter]:
    return (
        defaults  # Mocking/testing
        if defaults is not None
        else [
            PingRouter(redis_broker),  # ❌ Tightly coupled
            RedisRouter(url="redis://localhost:6379"),  # ❌ String URL
        ]
    )

# app/infrastructure/api/main.py
for specific in get_routers():  # ❌ Hidden dependencies
    app.include_router(
        specific.router if isinstance(specific, BaseRouter) else specific
    )
```

### Problems Identified

**1. Factory Pattern Without DI Container** (DIP Violation)
```python
# ❌ BAD: Dependencies created in factory
def get_routers(defaults=None):
    return defaults if defaults is not None else [
        PingRouter(redis_broker),  # Where does redis_broker come from?
        RedisRouter(url="redis://localhost:6379"),  # Hardcoded URL
    ]

# ✅ GOOD: Explicit dependency injection
class RouterRegistry:
    def __init__(self, broker: IMessageBroker, db: IDatabase):
        self.broker = broker
        self.db = db
    
    def get_routers(self) -> list[BaseRouter]:
        return [
            PingRouter(self.broker),
            CourseRouter(self.db),
        ]
```

**2. Type Checking Complexity** (ISP Violation)
```python
# ❌ BAD: Mix of BaseRouter and APIRouter, runtime type checking
for specific in get_routers():
    app.include_router(
        specific.router if isinstance(specific, BaseRouter) else specific
    )

# ✅ GOOD: Consistent abstraction
for router in registry.get_routers():  # All implement BaseRouter
    app.include_router(router.router)
```

**3. Testing Complications** (DIP Violation)
```python
# ❌ BAD: Must pass full list to override defaults
def test_api():
    mock_broker = MagicMock()
    routers = get_routers(defaults=[PingRouter(mock_broker)])  # Workaround

# ✅ GOOD: Clear dependency mocking
def test_api(broker_mock, registry_factory):
    registry = registry_factory(broker=broker_mock)
    routers = registry.get_routers()
    routers[0].broker.is_connected.assert_called()
```

### Recommended Solution

**Create a DI Container Pattern**

```python
# app/infrastructure/api/router_registry.py
from typing import Sequence
from app.core.message_broker import IMessageBroker
from app.core.database import IDatabase
from .base_router import BaseRouter

class RouterRegistry:
    """Central registry for API routers with dependency injection."""
    
    def __init__(
        self,
        message_broker: IMessageBroker,
        database: IDatabase,
    ):
        self.broker = message_broker
        self.db = database
    
    def get_routers(self) -> list[BaseRouter]:
        """Get all configured routers with injected dependencies."""
        return [
            PingRouter(self.broker),
            CourseRouter(self.db),
            EventRouter(self.db),  # Add more routers as needed
        ]


# app/infrastructure/api/main.py
from .router_registry import RouterRegistry
from app.infrastructure.message_broker_adapter import RedisMessageBrokerAdapter
from app.infrastructure.database_adapter import SQLAlchemyDatabaseAdapter

# Initialize dependencies
message_broker = RedisMessageBrokerAdapter(redis_broker)
database = SQLAlchemyDatabaseAdapter(getAppSettings())

# Create registry with clear DI
registry = RouterRegistry(message_broker, database)

# Include routers
for router in registry.get_routers():
    app.include_router(router.router)
```

**Testing becomes clean**

```python
# tests/functional/test_routers.py
@pytest.fixture
def router_registry(broker_mock, db_mock):
    return RouterRegistry(
        message_broker=broker_mock,
        database=db_mock,
    )

def test_ping_router(router_registry):
    routers = router_registry.get_routers()
    ping_router = routers[0]
    assert isinstance(ping_router, PingRouter)
```

**Impact**:
- +40-60 lines (clear DI container)
- Eliminates magic factory pattern
- Makes dependencies explicit and testable
- Single point of router configuration

### Template Lesson

✅ **Always follow this pattern for routing**:
1. Create dedicated `RouterRegistry` class
2. Inject dependencies explicitly in constructor
3. Centralized router configuration
4. Easy to test by mocking dependencies
5. Clear and explicit, not hidden in functions

---

## 🎯 #4: UseCase Result Type Inconsistency
### VIOLATIONS: Liskov Substitution Principle
### IMPACT: 🟠 MEDIUM | EFFORT: ⭐⭐ (1.5 hours)

### Current State

**Event UseCases** (✅ Good):
```python
# app/core/usecases/event_usecases.py
class EnqueueEventUseCase(AsyncUseCase[Input, Result[Output, ErrorDetail]]):
    async def execute(self, input: Input) -> Result[Output, ErrorDetail]:
        # Returns Result type for error handling
        return Ok(output) or Err(error_detail)


class TransitionEventUseCase(AsyncUseCase[Input, Result[Output, ErrorDetail]]):
    async def execute(self, input: Input) -> Result[Output, ErrorDetail]:
        # Consistent Result type
        return Ok(output) or Err(error_detail)
```

**Course UseCases** (❌ Bad):
```python
# app/core/usecases/course_usecases.py
class GetAsyncCourseUseCase(AsyncUseCase[Input, list[Course]]):
    async def execute(self, input_port: Input) -> list[Course]:
        # Returns raw type, no error handling!
        return courses


class CreateCourseUseCase:  # Doesn't even inherit AsyncUseCase!
    async def execute(self, course: Course) -> None:
        # Returns None, no error handling!
        pass
```

### Problems Identified

**1. Liskov Substitution Principle Violation**

```python
# ❌ BAD: Subclasses not substitutable
async def process_usecase(uc: AsyncUseCase[T, R]) -> R:
    result = await uc.execute(input)  # What type is result?
    # Could be Result[T, E] or raw list[T] or None!
    # Type checker can't help us

# ✅ GOOD: All UseCases have same contract
async def process_usecase(uc: AsyncUseCase[T, Result[R, ErrorDetail]]) -> R:
    result = await uc.execute(input)
    match result:
        case Ok(output): return output
        case Err(error): raise HTTPException(status_code=400, detail=str(error))
```

**2. API Layer Confusion**

```python
# ❌ BAD: Different error handling patterns
# For Event UseCases
result = await event_use_case.execute(input)
if result.is_err():
    raise HTTPException(status_code=400, detail=result.unwrap_err().detail)

# For Course UseCases
courses = await course_use_case.execute(input)
if not courses:
    raise HTTPException(status_code=404, detail="Not found")
```

**3. Testing Inconsistency**

```python
# ❌ BAD: Different test patterns
# Test Event UseCase
def test_event(uow_mock):
    result = await use_case.execute(input)
    assert result.is_ok()
    assert result.unwrap().id is not None

# Test Course UseCase
def test_course(uow_mock):
    courses = await use_case.execute(input)
    assert len(courses) > 0
    assert courses[0].name == "Python"
```

### Recommended Solution

**Standardize All UseCases to Return Result Type**

```python
# ✅ GOOD: Consistent contract
from result import Ok, Err, Result
from app.errors import ErrorDetail

class GetCourseUseCaseOutput(BaseModel):
    courses: list[Course]
    total: int

class GetAsyncCourseUseCase(
    AsyncUseCase[GetCourseUseCaseInput, Result[GetCourseUseCaseOutput, ErrorDetail]]
):
    def __init__(self, uow: IUnitOfWork):
        self.uow = uow

    async def execute(
        self, input: GetCourseUseCaseInput
    ) -> Result[GetCourseUseCaseOutput, ErrorDetail]:
        try:
            async with self.uow as uow:
                courses = await uow.courses.get_many(input.course_ids)
                return Ok(GetCourseUseCaseOutput(
                    courses=courses,
                    total=len(courses)
                ))
        except Exception as exc:
            return Err(ErrorDetail(
                error=ErrorCatalog.RUNTIME_FAILED.value,
                detail=str(exc)
            ))


class CreateCourseUseCase(
    AsyncUseCase[CreateCourseUseCaseInput, Result[CreateCourseUseCaseOutput, ErrorDetail]]
):
    def __init__(self, uow: IUnitOfWork):
        self.uow = uow

    async def execute(
        self, input: CreateCourseUseCaseInput
    ) -> Result[CreateCourseUseCaseOutput, ErrorDetail]:
        try:
            async with self.uow as uow:
                course = await uow.courses.save(input.course)
                return Ok(CreateCourseUseCaseOutput(course=course))
        except Exception as exc:
            return Err(ErrorDetail(...))
```

**Unified API Layer**

```python
# ✅ GOOD: Consistent pattern for all endpoints
@router.post("/courses")
async def create_course(
    input: CreateCourseUseCaseInput,
    use_case: CreateCourseUseCase = Depends(),
) -> dict:
    result = await use_case.execute(input)
    
    match result:
        case Ok(output):
            return output.model_dump()
        case Err(error):
            raise HTTPException(
                status_code=400,
                detail=error.detail
            )


@router.get("/courses")
async def get_courses(
    input: GetCourseUseCaseInput,
    use_case: GetAsyncCourseUseCase = Depends(),
) -> dict:
    result = await use_case.execute(input)
    
    match result:
        case Ok(output):
            return output.model_dump()
        case Err(error):
            raise HTTPException(
                status_code=400,
                detail=error.detail
            )
```

**Impact**:
- +40-50 lines (DTO classes + error handling)
- Consistent pattern across all UseCases
- Testable error scenarios
- Type-safe error handling in API layer

### Template Lesson

✅ **Always follow this pattern for all UseCases**:
1. All UseCases return `Result[OutputDTO, ErrorDetail]`
2. Create output DTOs with relevant fields
3. Handle all exceptions with proper error details
4. Test both Ok and Err paths
5. Consistent API layer error handling with `match`

---

## 🎯 #5: Settings Global Singleton
### VIOLATIONS: Dependency Inversion + Single Responsibility
### IMPACT: 🟡 LOW | EFFORT: ⭐ (45 minutes)

### Current State

**File**: `app/core/settings.py`

```python
# ❌ PROBLEMATIC: Global mutable singleton
_config: AppSettings | None = None

def getAppSettings(reload: bool = False) -> AppSettings:
    global _config
    if reload:
        clearAppSettings()
    if not _config or _config is None:
        _config = AppSettings()
    return _config

def clearAppSettings() -> None:
    global _config
    _config = None

# Module-level execution
settings = getAppSettings()  # Called when module loads!
```

**Usage in Infrastructure**:
```python
# app/infrastructure/db/connection.py
settings = getAppSettings()  # Global call at module level
async_engine: AsyncEngine = create_async_engine(
    settings.database_url,  # Tightly coupled to singleton
    ...
)
```

### Problems Identified

**1. Global Mutable State** (DIP Violation)
```python
# ❌ BAD: Hard to test with different configurations
# Can't easily test with different database URLs
settings = getAppSettings()
settings.database_url = "sqlite:///:memory:"  # Might not work!
```

**2. Module-Level Side Effects** (SRP Violation)
```python
# ❌ BAD: Initializing engine when module imports
settings = getAppSettings()  # Happens on import!
async_engine = create_async_engine(settings.database_url)

# This means the database connection is created before tests are ready
# Can cause issues with async context
```

**3. Testing Complications** (DIP Violation)
```python
# ❌ BAD: Must manipulate global state in tests
def test_with_test_db():
    getAppSettings(reload=True)  # Global reset
    # Hope env var TEST is set correctly
    settings = getAppSettings()
    assert settings.database_url == "sqlite:///:memory:"
```

**4. Reload Pattern is Fragile**

```python
# ❌ BAD: reload=True is confusing
def getAppSettings(reload: bool = False) -> AppSettings:
    global _config
    if reload:
        clearAppSettings()  # Must remember to set reload=True
    # ...

# Easy to forget:
settings1 = getAppSettings()
settings1.database_url = "sqlite:///test.db"
settings2 = getAppSettings()  # Still returns old instance!
```

### Recommended Solution

**Use Constructor-Based DI Instead of Singleton**

```python
# ✅ GOOD: app/core/settings.py (no global state)
class AppSettings(BaseSettings):
    env: str = "development"
    database_url: str = "sqlite:///./var/lib/database.sqlite"
    log_level: str = "DEBUG"

    model_config = SettingsConfigDict(
        env_file=resolve_env_file(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

# No global variable!
# No singleton pattern!


# ✅ GOOD: app/infrastructure/db/connection.py
class DatabaseConnection:
    """Encapsulates database connection with explicit DI."""
    
    def __init__(self, settings: AppSettings):
        self.settings = settings
        self._engine: AsyncEngine | None = None
        self._session_maker: async_sessionmaker | None = None
    
    async def get_engine(self) -> AsyncEngine:
        if self._engine is None:
            self._engine = create_async_engine(
                self.settings.database_url,
                connect_args={"check_same_thread": False},
            )
        return self._engine
    
    async def get_session(self) -> AsyncSession:
        if self._session_maker is None:
            engine = await self.get_engine()
            self._session_maker = async_sessionmaker(
                bind=engine,
                expire_on_commit=False,
            )
        return self._session_maker()
    
    async def setup_models(self) -> None:
        engine = await self.get_engine()
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)


# ✅ GOOD: app/infrastructure/api/main.py
from app.core.settings import AppSettings
from app.infrastructure.db.connection import DatabaseConnection

# Initialize at startup with explicit settings
settings = AppSettings()  # Create instance, not singleton
db_connection = DatabaseConnection(settings)

@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    setup_logging()
    await db_connection.setup_models()
    
    yield
    # Cleanup if needed
```

**Testing is Clean**

```python
# ✅ GOOD: tests/functional/conftest.py
@pytest.fixture
def app_settings() -> AppSettings:
    """Create test settings with in-memory DB."""
    return AppSettings(
        env="test",
        database_url="sqlite:///:memory:",
        log_level="WARNING",
    )

@pytest.fixture
async def db_connection(app_settings: AppSettings) -> DatabaseConnection:
    """Create test DB connection."""
    conn = DatabaseConnection(app_settings)
    await conn.setup_models()
    return conn

@pytest.fixture
async def test_app(db_connection: DatabaseConnection):
    """Create test FastAPI app with test database."""
    app = FastAPI(lifespan=lifespan)  # Uses test settings
    return app

async def test_api_with_test_db(test_app):
    # Uses in-memory database automatically
    # No global state manipulation!
    client = TestClient(test_app)
    response = client.get("/ping")
    assert response.status_code == 200
```

**Backward Compatibility (if needed)**

```python
# ✅ OPTIONAL: Provide convenience function for legacy code
_default_settings: AppSettings | None = None

def get_default_settings() -> AppSettings:
    """Get or create default settings (for backward compatibility)."""
    global _default_settings
    if _default_settings is None:
        _default_settings = AppSettings()
    return _default_settings

# New code should pass AppSettings explicitly via DI
# Old code can use get_default_settings() as a transitional pattern
```

**Impact**:
- +40-50 lines (DatabaseConnection class, cleaner settings)
- Eliminates global state
- Testing is straightforward
- Can have multiple configurations simultaneously

### Template Lesson

✅ **Always follow this pattern for configuration**:
1. Create settings class without global state
2. Wrap infrastructure (DB, Redis) in classes that take settings in constructor
3. Initialize in lifespan or main app factory
4. Pass dependencies explicitly through function parameters
5. Avoid global variables and singletons
6. Makes testing trivial: create fixtures with different settings

---

## 📊 Summary Table: Before & After

| Opportunity | Current | Improved | Benefit |
| --- | --- | --- | --- |
| **#1 Course UseCases** | Incomplete TODOs, no error handling | Consistent Result type or removed | Clear patterns, testable |
| **#2 Bare DB Access** | RedisBroker/AsyncEngine in API | Abstract interfaces with adapters | Swappable implementations |
| **#3 Router DI** | Magic factory, type checks | Clear RouterRegistry with DI | Explicit dependencies |
| **#4 UseCase Results** | Mixed Result/raw/None | Consistent Result type everywhere | Testable error handling |
| **#5 Settings Singleton** | Global mutable state | Constructor-based DI | Clean testing, no side effects |

---

## 🎓 Key Takeaways for the Template

### SOLID Principles Applied

**Single Responsibility** (SRP):
- Course UseCases should either be complete OR removed
- Settings should not initialize database engine
- Routers should not decide which routers to load

**Open/Closed** (OCP):
- Add new message broker without changing API code
- Add new router without modifying RouterRegistry logic
- Extend settings without breaking existing code

**Liskov Substitution** (LSP):
- All UseCases implement same Result contract
- All routers inherit from BaseRouter consistently
- All adapters implement their interface fully

**Interface Segregation** (ISP):
- IMessageBroker has minimal required methods
- IDatabase has focused methods
- BaseRouter doesn't expose internal details

**Dependency Inversion** (DIP):
- API depends on abstractions (IMessageBroker)
- UseCases depend on IUnitOfWork, not concrete implementations
- Settings passed as constructor arguments, not global singletons

### Clean Architecture Rules

```
✅ DEPENDENCIES FLOW INWARD (toward core)
API → Routers → UseCases → Repositories → Entities

❌ NEVER OUTWARD (core must not import infrastructure)
Core → Infrastructure (broken architecture!)

✅ Infrastructure depends on Core (adapters pattern)
Infrastructure → Core Interfaces → Core
```

### Red Flags to Watch For

When reviewing code, ask these questions:

1. **Is there a TODO stub?** → Remove or complete
2. **Are we accessing private attributes?** → Create abstraction
3. **Is infrastructure type visible in API?** → Create adapter
4. **Does this return different error types than similar code?** → Standardize
5. **Is there a global variable initialized at module level?** → Use DI
6. **Can I mock this in tests without complexity?** → Refactor to interfaces
7. **Does this have more than one reason to change?** → Split responsibilities

---

## 🚀 Recommended Implementation Order

1. **Phase 1 (This week)**: Remove or complete Course UseCases (#1)
2. **Phase 2 (Next week)**: Extract message broker and database adapters (#2)
3. **Phase 3 (Following week)**: Create RouterRegistry with clear DI (#3)
4. **Phase 4 (Optional)**: Standardize UseCase Result types (#4)
5. **Phase 5 (Optional)**: Remove settings singleton pattern (#5)

---

**Last Updated**: 2025-12-31  
**Created for**: Development team as architecture reference  
**Next Review**: After implementing Phase 1

