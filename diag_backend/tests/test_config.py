"""
配置模块单元测试
"""
import os
from unittest.mock import patch

import pytest

from app.core.config import Settings, get_settings


class TestSettings:
    """配置类测试"""

    def test_constructor_values(self):
        """测试通过构造函数设置值"""
        settings = Settings(
            mongodb_uri="mongodb://custom:27017",
            port=9000,
            debug=True
        )

        assert settings.mongodb_uri == "mongodb://custom:27017"
        assert settings.port == 9000
        assert settings.debug is True

    def test_sync_config_defaults(self):
        """测试同步配置默认值"""
        settings = Settings()

        assert settings.sync_api_base_url == "http://10.2.68.103"
        assert settings.sync_api_timeout == 30
        assert settings.sync_max_concurrency == 5
        assert settings.sync_max_retries == 3

    def test_jwt_algorithm(self):
        """测试 JWT 算法"""
        settings = Settings()
        assert settings.jwt_algorithm == "HS256"

    def test_access_token_expire_minutes(self):
        """测试 Token 过期时间"""
        settings = Settings()
        assert settings.access_token_expire_minutes == 60


class TestGetSettings:
    """get_settings 缓存测试"""

    def test_returns_singleton(self):
        """测试返回单例"""
        # 清除缓存
        get_settings.cache_clear()

        settings1 = get_settings()
        settings2 = get_settings()

        assert settings1 is settings2

    def test_cache_clear(self):
        """测试缓存清除"""
        get_settings.cache_clear()

        settings1 = get_settings()
        get_settings.cache_clear()
        settings2 = get_settings()

        # 缓存清除后是新实例
        assert settings1 is not settings2