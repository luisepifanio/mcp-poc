import pytest
from fastapi.testclient import TestClient


@pytest.mark.ignore
def test_validate_injection(value_inject: str):
    assert value_inject == "injected_value"


@pytest.mark.ignore
@pytest.mark.asyncio
async def test_read_root(http_client: TestClient):
    response = http_client.get("/ping")
    assert response.status_code == 200
    assert response.json() == "pong"


@pytest.mark.ignore
@pytest.mark.asyncio
async def test_get_nonexistent_course(http_client: TestClient):
    response = http_client.get("/courses?courses=67902&courses=65192&force_scrap=false")
    assert response.status_code == 200
    assert response.json() == []
