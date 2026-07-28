"""
LLM 服务单元测试 — 覆盖双模型客户端（回答/提取）、配置热加载与未配置时的模拟降级。
"""
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from openai import BadRequestError

from app.services.llm_service import LLMResponseParseError, LLMService


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

    @pytest.mark.asyncio
    async def test_connection_uses_temporary_client_and_reports_latency(self):
        service = LLMService()
        client = MagicMock()
        client.chat.completions.create = AsyncMock(
            return_value=SimpleNamespace(choices=[SimpleNamespace()])
        )
        client.close = AsyncMock()

        with patch.object(service, "_build_client", return_value=client):
            result = await service.test_connection(
                {
                    "api_key": "sk-test",
                    "base_url": "https://model.example/v1",
                    "model": "test-model",
                    "timeout": 30,
                }
            )

        assert result["success"] is True
        assert result["model"] == "test-model"
        assert isinstance(result["latency_ms"], int)
        client.chat.completions.create.assert_awaited_once()
        client.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_connection_masks_api_key_in_error(self):
        service = LLMService()
        client = MagicMock()
        client.chat.completions.create = AsyncMock(
            side_effect=RuntimeError("request rejected for sk-sensitive")
        )
        client.close = AsyncMock()

        with patch.object(service, "_build_client", return_value=client):
            result = await service.test_connection(
                {
                    "api_key": "sk-sensitive",
                    "base_url": "https://model.example/v1",
                    "model": "test-model",
                }
            )

        assert result["success"] is False
        assert "sk-sensitive" not in result["error"]
        assert "***" in result["error"]
        client.close.assert_awaited_once()

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

    def test_parse_json_response_accepts_surrounding_explanation(self):
        service = LLMService()

        result = service._parse_json_response(
            '分析如下：\n{"category": "存储", "confidence": 0.9}\n请查收。',
            {},
            strict=True,
        )

        assert result == {"category": "存储", "confidence": 0.9}

    def test_parse_json_response_strict_mode_exposes_raw_response(self):
        service = LLMService()

        with pytest.raises(LLMResponseParseError) as caught:
            service._parse_json_response("not valid json", {}, strict=True)

        assert str(caught.value) == "大模型返回格式异常，无法生成诊断结果"
        assert "not valid json" in caught.value.detail

    def test_parse_json_response_fallback_does_not_mutate_template(self):
        service = LLMService()
        fallback = {"summary": "解析失败", "suggestions": ["重试"]}

        result = service._parse_json_response("not valid json", fallback)
        result["suggestions"].append("联系支持")

        assert result["analysis"] == "not valid json"
        assert fallback == {"summary": "解析失败", "suggestions": ["重试"]}

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

    @pytest.mark.asyncio
    async def test_preprocessed_log_prompt_explains_original_line_prefix(self):
        service = LLMService()
        response = json.dumps(
            {
                "errors": [],
                "summary": "ok",
                "has_critical_errors": False,
                "suggested_root_cause": "",
            }
        )

        with patch.object(
            service, "chat_completion", new=AsyncMock(return_value=response)
        ) as chat:
            await service.extract_log_with_llm(
                "[L123] ERROR fan failed\n",
                encoding_stats={"source_line_prefixes": True},
                user_template="日志：\n{log_text}",
            )

        user_prompt = chat.await_args.args[0][1]["content"]
        assert "[L123] ERROR fan failed" in user_prompt
        assert "[L123] 表示该行在原始完整日志中的第 123 行" in user_prompt


class TestAdaptiveTokenBudget:
    @pytest.mark.parametrize(
        ("model", "expected"),
        [
            ("gpt-4", 8192),
            ("gpt-4o-mini", 128000),
            ("gpt-4.1", 1047576),
            ("deepseek-reasoner", 65536),
            ("qwen2.5-72b-instruct", 131072),
            ("anthropic/claude-sonnet-4", 200000),
            ("company/custom-model", 32768),
        ],
    )
    def test_infers_context_window_from_model_id(self, model: str, expected: int):
        assert LLMService._infer_model_context_len(model) == expected

    def test_prepare_request_truncates_oversized_log(self):
        service = LLMService()
        cfg = {"model": "custom", "base_url": "", "model_context_len": 4096, "max_tokens": 28000}
        messages = [
            {"role": "system", "content": "硬件诊断工程师"},
            {"role": "user", "content": "ERROR 内存故障 0xDEADBEEF\n" * 4000},
        ]

        prepared, max_output, context_len, input_tokens = service._prepare_request(
            messages, cfg, "custom", "answer"
        )

        assert context_len == 4096
        assert input_tokens + max_output + 512 <= context_len
        assert len(prepared[1]["content"]) < len(messages[1]["content"])
        assert "自动裁剪" in prepared[1]["content"]

    def test_output_budget_is_automatic_and_client_specific(self):
        service = LLMService()
        cfg = {"model": "custom", "base_url": "", "model_context_len": 32768, "max_tokens": 28000}
        messages = [{"role": "user", "content": "分析错误"}]

        _, answer_output, _, _ = service._prepare_request(messages, cfg, "custom", "answer")
        _, extraction_output, _, _ = service._prepare_request(messages, cfg, "custom", "extraction")

        assert answer_output == 8192
        assert extraction_output == 4096

    def test_parses_and_learns_provider_context_limit(self):
        service = LLMService()
        cfg = {"model": "proxy-model", "base_url": "https://proxy/v1", "model_context_len": 0}
        detail = "This model's maximum context length is 16,384 tokens"

        assert service._context_limit_from_error(detail) == 16384
        assert service._learn_context_limit(cfg, "proxy-model", detail, 32768) == 16384
        assert service._resolve_context_len(cfg, "proxy-model") == 16384

    def test_parses_and_learns_provider_output_limit(self):
        service = LLMService()
        cfg = {"model": "proxy-model", "base_url": "https://proxy/v1", "max_tokens": 28000}
        detail = "max_tokens must be less than or equal to 4,096"

        assert service._output_limit_from_error(detail) == 4096
        assert service._learn_output_limit(cfg, "proxy-model", detail, 8192) == 4096
        assert service._resolve_output_limit(cfg, "proxy-model", "answer") == 4096


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

    @pytest.mark.asyncio
    async def test_extraction_uses_structured_reasoning_when_content_is_none(self):
        service = LLMService()
        mock_client = MagicMock()
        message = MagicMock()
        message.content = None
        message.reasoning_content = '{"errors": [], "summary": "ok"}'
        response = MagicMock()
        response.choices = [MagicMock(message=message, finish_reason="stop")]
        mock_client.chat.completions.create = AsyncMock(return_value=response)
        service._extraction_client = mock_client
        service._loaded = True
        service._config = _nested_config(api_key="sk-extract")

        result = await service.chat_completion(
            [{"role": "user", "content": "提取错误"}], client="extraction"
        )

        assert result == '{"errors": [], "summary": "ok"}'

    @pytest.mark.asyncio
    async def test_chat_completion_reports_empty_content_clearly(self):
        service = LLMService()
        mock_client = MagicMock()
        message = MagicMock()
        message.content = None
        message.reasoning_content = None
        message.model_extra = {}
        response = MagicMock()
        response.choices = [MagicMock(message=message, finish_reason="length")]
        mock_client.chat.completions.create = AsyncMock(return_value=response)
        service._extraction_client = mock_client
        service._loaded = True
        service._config = _nested_config(api_key="sk-extract")

        with pytest.raises(RuntimeError, match="LLM 返回空内容.*finish_reason=length"):
            await service.chat_completion(
                [{"role": "user", "content": "提取错误"}], client="extraction"
            )

    def test_extract_json_rejects_none_with_clear_error(self):
        with pytest.raises(ValueError, match="LLM 返回内容为空"):
            LLMService._extract_json(None)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_context_error_learns_limit_and_retries_once(self, mock_client: MagicMock):
        service = LLMService()
        service.openai_client = mock_client
        service._loaded = True
        service._config = _nested_config(api_key="sk-test", model="proxy-model")

        request = httpx.Request("POST", "https://test.api.com/v1/chat/completions")
        error = BadRequestError(
            "context exceeded",
            response=httpx.Response(400, request=request),
            body={"error": {"message": "Maximum context length is 4096 tokens"}},
        )
        success = MagicMock()
        success.choices = [MagicMock(message=MagicMock(content="ok"))]
        mock_client.chat.completions.create.side_effect = [error, success]

        response = await service.chat_completion(
            [{"role": "user", "content": "ERROR 0xDEADBEEF\n" * 5000}]
        )

        assert response == "ok"
        assert mock_client.chat.completions.create.await_count == 2
        retry_kwargs = mock_client.chat.completions.create.await_args_list[1].kwargs
        retry_input = service._estimate_messages_tokens(retry_kwargs["messages"])
        assert retry_input + retry_kwargs["max_tokens"] + 512 <= 4096


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
