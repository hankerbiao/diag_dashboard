"""
LLM 服务单元测试
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.llm_service import LLMService


class TestLLMService:
    """LLM 服务 Mock 测试"""

    @pytest.fixture
    def llm_service(self) -> LLMService:
        """创建 LLM 服务实例（无数据库依赖）"""
        service = LLMService()
        service._loaded = True  # 跳过数据库懒加载
        return service

    def test_init_no_error(self):
        """初始化不应再抛出 RuntimeError"""
        service = LLMService()
        assert service.openai_client is None
        assert service._loaded is False

    def test_chat_completion_with_mock(self, llm_service: LLMService):
        """测试对话完成（Mock 模式）- 同步测试"""
        messages = [
            {"role": "user", "content": "你好"}
        ]

        response = llm_service._mock_response(messages)

        assert isinstance(response, str)
        assert len(response) > 0

    def test_mock_response_for_diagnosis(self, llm_service: LLMService):
        """测试诊断的 Mock 响应格式"""
        messages = [
            {"role": "user", "content": "请诊断 SN12345678"}
        ]

        response = llm_service._mock_response(messages)

        # 尝试解析 JSON
        try:
            data = json.loads(response)
            assert "category" in data
            assert "suggestions" in data
        except json.JSONDecodeError:
            # 如果不是 JSON，也应该是合理的文本响应
            assert len(response) > 0

    def test_mock_response_for_analysis(self, llm_service: LLMService):
        """测试分析的 Mock 响应格式"""
        messages = [
            {"role": "user", "content": "分析这个错误"}
        ]

        response = llm_service._mock_response(messages)

        try:
            data = json.loads(response)
            assert "root_cause" in data
            assert "repair_suggestions" in data
        except json.JSONDecodeError:
            assert len(response) > 0

    def test_mock_response_fallback(self, llm_service: LLMService):
        """测试未知内容的 Mock 响应"""
        messages = [
            {"role": "user", "content": "随机内容"}
        ]

        response = llm_service._mock_response(messages)
        assert isinstance(response, str)
        assert len(response) > 0

    @pytest.mark.asyncio
    async def test_chat_completion_no_client(self):
        """没有可用客户端时返回 Mock 响应"""
        service = LLMService()
        service._loaded = True  # 跳过数据库加载

        messages = [{"role": "user", "content": "诊断 SN123"}]
        response = await service.chat_completion(messages)

        assert isinstance(response, str)
        assert len(response) > 0
        data = json.loads(response)
        assert "category" in data  # 消息含"诊断"关键词 → 诊断格式


class TestLLMServiceWithMockedClient:
    """使用 Mock OpenAI 客户端的测试"""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """创建 Mock OpenAI 客户端"""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content='{"category":"测试","summary":"测试结果","confidence":0.9,"suggestions":["建议"]}'
                )
            )
        ]
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        return mock_client

    @pytest.mark.asyncio
    async def test_chat_completion_with_real_client(
        self,
        mock_client: MagicMock
    ):
        """测试使用真实客户端调用"""
        service = LLMService()
        service.openai_client = mock_client
        # 预设客户端时 _ensure_configured 会跳过
        service._loaded = True

        messages = [{"role": "user", "content": "测试"}]
        response = await service.chat_completion(messages)

        assert response == '{"category":"测试","summary":"测试结果","confidence":0.9,"suggestions":["建议"]}'
        mock_client.chat.completions.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_chat_completion_with_model_param(
        self,
        mock_client: MagicMock
    ):
        """测试自定义模型参数"""
        service = LLMService()
        service.openai_client = mock_client
        service._loaded = True

        messages = [{"role": "user", "content": "测试"}]
        await service.chat_completion(messages, model="gpt-4", temperature=0.5)

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "gpt-4"
        assert call_kwargs["temperature"] == 0.5


class TestLLMServiceReload:
    """LLMService 热加载测试"""

    @pytest.mark.asyncio
    async def test_reload_config_rebuilds_client(self):
        """reload_config 应重建客户端"""
        service = LLMService()
        assert service.openai_client is None
        assert service._loaded is False

        # 模拟数据库配置有 API Key
        with patch.object(service, '_load_config_from_db', return_value={
            "api_key": "sk-test-key",
            "base_url": "https://test.api.com/v1",
            "model": "gpt-4",
            "temperature": 0.5,
        }):
            await service.reload_config()

            assert service._loaded is True
            assert service.openai_client is not None
            assert service._config["model"] == "gpt-4"
            assert service._config["temperature"] == 0.5

    @pytest.mark.asyncio
    async def test_reload_config_mock_fallback(self):
        """热加载空 Key 时应回退 Mock 模式"""
        service = LLMService()

        # 模拟数据库配置 API Key 为空
        with patch.object(service, '_load_config_from_db', return_value={
            "api_key": "",
            "base_url": "",
            "model": "gpt-4",
            "temperature": 0.7,
        }):
            await service.reload_config()
            assert service.openai_client is None

            messages = [{"role": "user", "content": "诊断 SN999"}]
            response = await service.chat_completion(messages)
            assert isinstance(response, str)
            assert len(response) > 0

    @pytest.mark.asyncio
    async def test_reload_config_used_by_chat_completion(self):
        """热加载后 chat_completion 应使用新配置"""
        service = LLMService()

        # 加载真实 key 则创建真实 client
        with patch.object(service, '_load_config_from_db', return_value={
            "api_key": "sk-real-key",
            "base_url": "https://real.api.com/v1",
            "model": "gpt-4-turbo",
            "temperature": 0.7,
        }):
            await service.reload_config()
            assert service.openai_client is not None
            assert service._config["api_key"] == "sk-real-key"

        # 再次热加载为空 key → client 应置为 None
        with patch.object(service, '_load_config_from_db', return_value={
            "api_key": "",
            "base_url": "",
            "model": "gpt-4",
            "temperature": 0.7,
        }):
            await service.reload_config()
            assert service.openai_client is None

    @pytest.mark.asyncio
    async def test_ensure_configured_skips_when_client_set(self):
        """预设 openai_client 时 _ensure_configured 应跳过"""
        service = LLMService()
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content="custom client response"))
        ]
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        # 手动设置客户端，不应被 _ensure_configured 覆盖
        service.openai_client = mock_client

        messages = [{"role": "user", "content": "test"}]
        response = await service.chat_completion(messages)

        assert response == "custom client response"
        mock_client.chat.completions.create.assert_called_once()
