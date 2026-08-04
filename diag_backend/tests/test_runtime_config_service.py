"""RuntimeConfigService 单元测试 — 缓存、持久化与实时生效回调（不依赖真实 MongoDB）。"""
from unittest.mock import AsyncMock

import pytest

from app.services.runtime_config_service import DEFAULTS, RuntimeConfigService


@pytest.fixture
def mock_mongo(monkeypatch):
    """Mock MongoDB 集合，并屏蔽对全局信号量的真实改动。"""
    col = AsyncMock()
    col.find_one = AsyncMock(return_value=None)
    col.update_one = AsyncMock()

    monkeypatch.setattr("app.core.mongodb.get_collection", lambda name: col)
    monkeypatch.setattr(
        "app.services.log_processing.ai_extractor.set_global_concurrency",
        lambda limit: None,
    )
    return col


class TestRuntimeConfigService:
    @pytest.mark.asyncio
    async def test_defaults_when_no_doc(self, mock_mongo):
        svc = RuntimeConfigService()
        config = await svc.get()
        assert config == DEFAULTS
        assert svc.generation >= 1

    @pytest.mark.asyncio
    async def test_apply_update_persists_and_refreshes_cache(self, mock_mongo):
        svc = RuntimeConfigService()
        config = await svc.apply_update(
            {"per_request_concurrency": 4, "global_concurrency": 12}
        )
        assert config["per_request_concurrency"] == 4
        assert config["global_concurrency"] == 12
        mock_mongo.update_one.assert_awaited_once()
        # 写库使用点路径，便于 MongoDB 嵌套更新
        args = mock_mongo.update_one.await_args
        assert "log_extraction.per_request_concurrency" in args.args[1]["$set"]

    @pytest.mark.asyncio
    async def test_apply_update_partial_keeps_other_value(self, mock_mongo):
        svc = RuntimeConfigService()
        await svc.apply_update({"per_request_concurrency": 4})
        cached = svc.cached()
        assert cached["per_request_concurrency"] == 4
        assert cached["global_concurrency"] == DEFAULTS["global_concurrency"]

    @pytest.mark.asyncio
    async def test_reload_reads_db_doc(self, mock_mongo):
        mock_mongo.find_one = AsyncMock(
            return_value={
                "_id": "runtime_config",
                "log_extraction": {
                    "per_request_concurrency": 6,
                    "global_concurrency": 20,
                },
            }
        )
        svc = RuntimeConfigService()
        config = await svc.get()
        assert config["per_request_concurrency"] == 6
        assert config["global_concurrency"] == 20

    @pytest.mark.asyncio
    async def test_ignores_invalid_values_in_db(self, mock_mongo):
        mock_mongo.find_one = AsyncMock(
            return_value={
                "_id": "runtime_config",
                "log_extraction": {
                    "per_request_concurrency": "abc",
                    "global_concurrency": 0,
                },
            }
        )
        svc = RuntimeConfigService()
        config = await svc.get()
        assert config["per_request_concurrency"] == DEFAULTS["per_request_concurrency"]
        assert config["global_concurrency"] == 1  # max(1, ...) 钳制
