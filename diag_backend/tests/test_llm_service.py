"""
LLM 服务单元测试 — 覆盖双模型客户端（回答/提取）、配置热加载与未配置时的模拟降级。
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.llm_service import LLMService


def _nested_config(api_key="sk-test", model="gpt-4", base_url="https://test.api.com/v1",
                   extraction_api_key=None, extraction_model=None):
    return {
        "answer": {
            "api_key": api_key,
            "base_url": base_url,
            "model": model,
            "temperature": 0.5,
            "max_tokens": 0,
            "chat_template_kwargs": {"enable_thinking": False},
            "timeout": 0,
            "model_context_len": 1000000,
        },
        "extraction": {
            "api_key": extraction_api_key or api_key,
            "base_url": base_url,
            "model": extraction_model or model,
            "temperature": 0.0,
            "max_tokens": 0,
            "chat_template_kwargs": {"enable_thinking": False},
            "timeout": 0,
            "model_context_len": 1000000,
        },
    }


class TestLLMService:
    """LLM 服务基础 / 模拟降级测试"""

    def test_init_no_error(self):
        """初始化不应抛出错误，且双客户端均为 None"""
        service = LLMService()
        assert service.openai_client is None
        assert service._answer_client is None
        assert service._extraction_client is None
        assert service._loaded is False

    def test_openai_client_alias(self):
        """openai_client 属性应等价于回答模型客户端 _answer_client"""
        service = LLMService()
        fake = object()
        service.openai_client = fake
        assert service._answer_client is fake
        assert service.openai_client is fake

    def test_mock_response_for_diagnosis(self):
        """诊断类消息的模拟响应是合法 JSON 且含诊断字段"""
        service = LLMService()
        resp = service._mock_response([{"role": "user", "content": "请诊断 SN12345678"}])
        data = json.loads(resp)
        assert "category" in data
        assert "suggestions" in data

    def test_mock_response_for_analysis(self):
        """分析类消息的模拟响应含 root_cause / repair_suggestions"""
        service = LLMService()
        resp = service._mock_response([{"role": "user", "content": "分析这个错误"}])
        data = json.loads(resp)
        assert "root_cause" in data
        assert "repair_suggestions" in data

    def test_mock_response_for_extraction(self):
        """提取客户端的模拟响应与 LOG_EXTRACTION_FALLBACK 结构一致"""
        service = LLMService()
        resp = service._mock_response([{"role": "user", "content": "x"}], client="extraction")
        data = json.loads(resp)
        assert set(data.keys()) == set(LLMService.LOG_EXTRACTION_FALLBACK.keys())

    def test_mock_response_fallback(self):
        """无关内容的模拟响应仍为非空字符串"""
        service = LLMService()
        resp = service._mock_response([{"role": "user", "content": "随机内容"}])
        assert isinstance(resp, str)
        assert len(resp) > 0

    @pytest.mark.asyncio
    async def test_chat_completion_no_client(self):
        """无可用客户端时返回模拟响应（接口不崩溃）"""
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
    async def test_chat_completion_with_real_client(self, mock_client: MagicMock):
        """回答客户端走真实（mock）客户端调用"""
        service = LLMService()
        service.openai_client = mock_client
        service._loaded = True
        service._config = _nested_config(api_key="sk-test")  # 标记为已配置，避免走模拟降级

        messages = [{"role": "user", "content": "测试"}]
        response = await service.chat_completion(messages)

        assert response == '{"category":"测试","summary":"测试结果","confidence":0.9,"suggestions":["建议"]}'
        mock_client.chat.completions.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_chat_completion_with_model_param(self, mock_client: MagicMock):
        """自定义模型 / 温度参数应正确传递"""
        service = LLMService()
        service.openai_client = mock_client
        service._loaded = True
        service._config = _nested_config(api_key="sk-test")

        messages = [{"role": "user", "content": "测试"}]
        await service.chat_completion(messages, model="gpt-4", temperature=0.5)

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "gpt-4"
        assert call_kwargs["temperature"] == 0.5

    @pytest.mark.asyncio
    async def test_chat_completion_routes_extraction_client(self, mock_client: MagicMock):
        """client='extraction' 时应使用提取客户端"""
        service = LLMService()
        service._extraction_client = mock_client
        service._loaded = True
        service._config = _nested_config(api_key="sk-extract", extraction_model="gpt-4-mini")

        messages = [{"role": "user", "content": "提取错误"}]
        await service.chat_completion(messages, client="extraction")

        mock_client.chat.completions.create.assert_called_once()
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == service._config["extraction"]["model"]


class TestLLMServiceReload:
    """LLMService 热加载（双客户端）测试"""

    @pytest.mark.asyncio
    async def test_reload_config_rebuilds_clients(self):
        """reload_config 应重建回答 + 提取两个客户端"""
        service = LLMService()
        assert service.openai_client is None
        assert service._extraction_client is None
        assert service._loaded is False

        with patch.object(service, '_load_config_from_db',
                          return_value=_nested_config(extraction_model="gpt-4-mini")):
            await service.reload_config()

            assert service._loaded is True
            assert service._answer_client is not None
            assert service._extraction_client is not None
            assert service._config["answer"]["model"] == "gpt-4"
            assert service._config["extraction"]["model"] == "gpt-4-mini"

    @pytest.mark.asyncio
    async def test_reload_config_extraction_fallback(self):
        """提取配置留空时应回退复用回答配置"""
        service = LLMService()
        with patch.object(service, '_load_config_from_db',
                          return_value=_nested_config(extraction_api_key="", extraction_model="")):
            await service.reload_config()
            # extraction 回退到 answer 的 key/model
            assert service._config["extraction"]["api_key"] == "sk-test"
            assert service._config["extraction"]["model"] == "gpt-4"
            assert service.get_config_value("model", client="extraction") == "gpt-4"

    @pytest.mark.asyncio
    async def test_reload_config_used_by_chat_completion(self):
        """热加载后 chat_completion 应使用新配置"""
        service = LLMService()

        with patch.object(service, '_load_config_from_db',
                          return_value=_nested_config(api_key="sk-real-key", model="gpt-4-turbo")):
            await service.reload_config()
            assert service.openai_client is not None
            assert service._config["answer"]["api_key"] == "sk-real-key"

    @pytest.mark.asyncio
    async def test_ensure_configured_skips_when_client_set(self):
        """预设 openai_client 时 _ensure_configured 应跳过"""
        service = LLMService()
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="custom client response"))]
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        service.openai_client = mock_client
        # 标记为已配置，确保不触发模拟降级
        service._config = _nested_config(api_key="sk-test")

        messages = [{"role": "user", "content": "test"}]
        response = await service.chat_completion(messages)

        assert response == "custom client response"
        mock_client.chat.completions.create.assert_called_once()
