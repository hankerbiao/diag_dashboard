"""
共享的 pytest fixtures
"""
import asyncio
from datetime import timedelta
from typing import AsyncGenerator, Generator

import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import MagicMock, AsyncMock, patch

from app.main import app
from app.core.auth import hash_password, create_access_token
from app.core.config import Settings


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """创建事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_settings() -> Settings:
    """测试配置"""
    return Settings(
        mongodb_uri="mongodb://localhost:27017",
        mongodb_db_name="test_diag_analysis",
        jwt_secret_key="test-secret-key-for-testing-only-64-char",
        jwt_algorithm="HS256",
        access_token_expire_minutes=60,
    )


@pytest.fixture
def test_user() -> dict:
    """测试用户数据"""
    return {
        "email": "test@example.com",
        "password": "testpassword123",
        "password_hash": None,
    }


@pytest.fixture
def test_user_with_hash(test_user: dict) -> dict:
    """带哈希密码的测试用户"""
    test_user["password_hash"] = hash_password(test_user["password"])
    return test_user


@pytest.fixture
def valid_token(test_settings: Settings) -> str:
    """生成有效 JWT Token"""
    return create_access_token(
        user_id="test-user-id-123",
        email="test@example.com",
        expires_delta=timedelta(minutes=60)
    )


@pytest.fixture
def auth_headers(valid_token: str) -> dict:
    """认证请求头"""
    return {"Authorization": f"Bearer {valid_token}"}


@pytest.fixture
def mock_mongo_collection() -> AsyncMock:
    """Mock MongoDB Collection"""
    collection = AsyncMock()
    collection.find_one = AsyncMock(return_value=None)
    collection.insert_one = AsyncMock()
    collection.find_one_and_update = AsyncMock()
    collection.delete_one = AsyncMock()
    return collection


@pytest.fixture
def mock_mongo_db(mock_mongo_collection: AsyncMock) -> MagicMock:
    """Mock MongoDB Database"""
    db = MagicMock()
    db.__getitem__ = MagicMock(return_value=mock_mongo_collection)
    return db


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """异步 HTTP 客户端用于 API 测试"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def sample_device_info() -> dict:
    """示例设备信息"""
    return {
        "id": "device-001",
        "sn": "SN12345678",
        "model": "GServer-4280G4",
        "factory": "Factory-A",
        "batch": "2024-W01",
        "production_date": "2024-01-15"
    }


@pytest.fixture
def sample_test_logs() -> list[dict]:
    """示例测试日志"""
    return [
        {
            "id": "log-001",
            "sn": "SN12345678",
            "test_item": "Memory Test",
            "test_time": "2024-01-15T10:30:00",
            "status": "FAIL",
            "fail_details": "ECC error on DIMM4"
        },
        {
            "id": "log-002",
            "sn": "SN12345678",
            "test_item": "CPU Test",
            "test_time": "2024-01-15T10:35:00",
            "status": "PASS",
            "fail_details": None
        }
    ]


@pytest.fixture
def sample_maintenance() -> list[dict]:
    """示例维修记录"""
    return [
        {
            "id": "maint-001",
            "date": "2024-01-10",
            "component": "DIMM4",
            "action": "更换内存条"
        }
    ]


@pytest.fixture
def sample_diagnosis_result() -> dict:
    """示例诊断结果"""
    return {
        "category": "内存故障",
        "summary": "基于知识图谱分析，DIMM4 发生结构性硬件故障",
        "confidence": 0.92,
        "suggestions": [
            "清除 ECC 寄存器错误",
            "更换 8GB-DDR4-HYNX 内存条",
            "执行 MEM_STRESS_T2 强化测试"
        ]
    }


@pytest.fixture
def sample_error_log() -> dict:
    """示例错误日志"""
    return {
        "id": "error-001",
        "sn": "SN12345678",
        "test_item": "Memory Test",
        "test_time": "2024-01-15T10:30:00",
        "status": "FAIL",
        "fail_details": "ECC error on DIMM4",
        "mes_reported": True
    }