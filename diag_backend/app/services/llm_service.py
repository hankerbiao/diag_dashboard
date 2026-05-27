from typing import Awaitable, Callable, Optional
import json
import re

from openai import AsyncOpenAI

from ..core.config import get_settings

settings = get_settings()

DEVICE_INFO_TPL = """## 设备信息
- 设备 SN: {sn}
- 测试项目: {test_item}
- 错误信息: {fail_details}
- 测试时间: {test_time}"""


def _build_diagnosis_prompt(error_log: dict, knowledge_context: str, extra_hint: str = "") -> str:
    return f"""请根据以下内容进行故障诊断。

{DEVICE_INFO_TPL.format(
    sn=error_log.get('sn', '未知'),
    test_item=error_log.get('test_item', '未知'),
    fail_details=error_log.get('fail_details', '无'),
    test_time=error_log.get('test_time', '未知'),
)}

{knowledge_context}

{extra_hint}

请以 JSON 格式返回诊断结果：
- root_cause: 诊断的根本原因
- evidence: 关键证据列表（每项：日志行 + 结论说明）
- analysis: 详细分析摘要
- repair_suggestions: 维修建议列表（3-5条）
- knowledge_refs: 知识库引用列表 [{source, content}]，未引用则返回 []"""


class LLMService:
    """LLM 服务封装"""

    def __init__(self):
        kwargs = {"api_key": settings.openai_api_key} if settings.openai_api_key else {}
        if settings.openai_api_url:
            kwargs["base_url"] = settings.openai_api_url
        self.openai_client = AsyncOpenAI(**kwargs) if kwargs else None
        if not self.openai_client:
            raise RuntimeError("LLM 服务未配置，请设置 openai_api_key")

    async def chat_completion(
        self, messages: list[dict], model: Optional[str] = None, temperature: Optional[float] = None,
    ) -> str:
        return (await self.openai_client.chat.completions.create(
            model=model or settings.ai_model,
            messages=messages,
            temperature=temperature if temperature is not None else settings.ai_temperature,
        )).choices[0].message.content

    async def chat_completion_stream(
        self, messages: list[dict], token_cb: Callable[[str], Awaitable[None]],
        model: Optional[str] = None, temperature: Optional[float] = None,
    ) -> str:
        stream = await self.openai_client.chat.completions.create(
            model=model or settings.ai_model,
            messages=messages,
            temperature=temperature if temperature is not None else settings.ai_temperature,
            stream=True,
        )
        chunks = []
        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                chunks.append(delta.content)
                await token_cb(delta.content)
        return "".join(chunks)

    @staticmethod
    def _extract_json(text: str) -> str:
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        return match.group(1).strip() if match else text.strip()

    def _parse_json_response(self, response: str, fallback: dict) -> dict:
        try:
            return json.loads(self._extract_json(response))
        except json.JSONDecodeError:
            fallback["analysis"] = response
            return fallback

    async def diagnose_sn(self, sn: str, device_info: dict, test_logs: list[dict],
                          maintenance: list[dict], similar_cases: list[dict]) -> dict:
        prompt = f"""你是一个专业的硬件诊断工程师。请根据以下信息对设备进行诊断：

设备信息：SN={sn}, 型号={device_info.get('model', '未知')}, 批次={device_info.get('batch', '未知')}

测试日志：
{chr(10).join([f"- [{l.get('test_time')}] {l.get('test_item')}: {l.get('fail_details', '通过')}" for l in test_logs[:10]])}

维修历史：
{chr(10).join([f"- [{r.get('date')}] {r.get('component')}: {r.get('action')}" for r in maintenance[:5]])}

相似案例：
{chr(10).join([f"- {c.get('title')}: {c.get('root_cause', '')}" for c in similar_cases[:3]])}

请以 JSON 格式返回：category, summary, confidence (0-1), suggestions"""

        return self._parse_json_response(
            await self.chat_completion([{"role": "system", "content": "硬件诊断工程师"},
                                        {"role": "user", "content": prompt}]),
            {"category": "未知", "summary": "解析失败", "confidence": 0.5, "suggestions": ["联系技术支持"]}
        )

    async def analyze_error(self, error_log: dict, similar_cases: list[dict]) -> dict:
        prompt = f"""请分析以下测试异常：SN={error_log.get('sn')}, 项目={error_log.get('test_item')},
错误={error_log.get('fail_details')}。相似案例：{chr(10).join([c.get('title', '') for c in similar_cases[:2]])}
请返回 JSON: root_cause, analysis, repair_suggestions"""

        return self._parse_json_response(
            await self.chat_completion([{"role": "system", "content": "硬件故障分析专家"},
                                        {"role": "user", "content": prompt}]),
            {"root_cause": "分析中", "analysis": "", "repair_suggestions": ["进一步诊断中..."]}
        )

    async def analyze_with_knowledge(self, error_log: dict, knowledge_context: str, error_count: int = 0) -> dict:
        hint = f"以上日志已被正则扫描，发现 {error_count} 个错误区段，请逐一分析。" if error_count else "未匹配到明显错误行，请自行定位分析。"
        prompt = _build_diagnosis_prompt(error_log, knowledge_context, hint)
        return self._parse_json_response(
            await self.chat_completion([{"role": "system", "content": "硬件故障诊断专家"},
                                        {"role": "user", "content": prompt}]),
            {"root_cause": "分析失败", "evidence": [], "repair_suggestions": ["请重试"], "knowledge_refs": []}
        )

    async def analyze_with_knowledge_stream(
        self, error_log: dict, knowledge_context: str, token_cb: Callable[[str], Awaitable[None]],
    ) -> dict:
        prompt = _build_diagnosis_prompt(error_log, knowledge_context, "如果引用了知识库内容，请标注 [参考 N]。")
        return self._parse_json_response(
            await self.chat_completion_stream(
                [{"role": "system", "content": "硬件故障诊断专家"},
                 {"role": "user", "content": prompt}],
                token_cb,
            ),
            {"root_cause": "分析失败", "evidence": [], "repair_suggestions": ["请重试"], "knowledge_refs": []}
        )


llm_service = LLMService()