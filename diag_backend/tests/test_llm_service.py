"""
LLM 服务单元测试
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.llm_service import LLMService


class TestLLMService:
    """LLM 服务测试"""

    @pytest.fixture
    def llm_service(self) -> LLMService:
        """创建 LLM 服务实例"""
        return LLMService()

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

        messages = [{"role": "user", "content": "测试"}]
        await service.chat_completion(messages, model="gpt-4", temperature=0.5)

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "gpt-4"
        assert call_kwargs["temperature"] == 0.5

    @pytest.mark.asyncio
    async def test_chat_completion_no_client(self):
        """无客户端时返回 Mock"""
        service = LLMService()
        service.openai_client = None

        messages = [{"role": "user", "content": "诊断 SN123"}]
        response = await service.chat_completion(messages)

        assert isinstance(response, str)
        assert len(response) > 0