from typing import Awaitable, Callable, Optional
import json
import re

from openai import AsyncOpenAI

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
- knowledge_refs: 知识库引用列表 [{{source, content}}]，未引用则返回 []"""


class LLMService:
    """LLM 服务封装 — 支持数据库配置热加载"""

    def __init__(self):
        self.openai_client: Optional[AsyncOpenAI] = None
        self._config: dict = {
            "api_key": "",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4-turbo",
            "temperature": 0.7,
        }
        self._loaded = False

    # ------------------------------------------------------------------
    # 配置加载
    # ------------------------------------------------------------------

    async def _load_config_from_db(self) -> dict:
        """从 MongoDB 加载 AI 配置，不存在时回退到环境变量"""
        try:
            from ..core.mongodb import get_collection
            col = get_collection("global_app_config")
            config = await col.find_one({"_id": "ai_config"})
            if config:
                return {
                    "api_key": config.get("api_key", ""),
                    "base_url": config.get("base_url", "https://api.openai.com/v1"),
                    "model": config.get("model", "gpt-4-turbo"),
                    "temperature": config.get("temperature", 0.7),
                }
        except Exception:
            pass

        from ..core.config import get_settings
        s = get_settings()
        return {
            "api_key": s.openai_api_key or "",
            "base_url": s.openai_api_url or "https://api.openai.com/v1",
            "model": s.ai_model or "gpt-4-turbo",
            "temperature": s.ai_temperature or 0.7,
        }

    async def _ensure_configured(self):
        """懒加载配置（仅在无预设客户端时执行一次）"""
        if not self._loaded and self.openai_client is None:
            self._config = await self._load_config_from_db()
            self._rebuild_client()
            self._loaded = True

    def _rebuild_client(self):
        """根据当前 _config 重建 AsyncOpenAI 客户端"""
        key = self._config.get("api_key", "")
        url = self._config.get("base_url", "")
        if key:
            kwargs = {"api_key": key}
            if url:
                kwargs["base_url"] = url
            self.openai_client = AsyncOpenAI(**kwargs)
        else:
            self.openai_client = None

    async def reload_config(self):
        """从数据库重新加载配置（热加载）"""
        self._config = await self._load_config_from_db()
        self._rebuild_client()
        self._loaded = True

    # ------------------------------------------------------------------
    # Mock 响应（无可用 LLM 时的降级路径）
    # ------------------------------------------------------------------

    @staticmethod
    def _mock_response(messages: list[dict]) -> str:
        """无可用大模型时返回 Mock 诊断结果"""
        content = " ".join(m.get("content", "") for m in messages if m.get("content"))

        if "诊断" in content or "SN" in content.upper():
            return json.dumps({
                "category": "硬件故障",
                "summary": "模拟诊断：设备存在潜在硬件异常，建议进行深度检测",
                "confidence": 0.85,
                "suggestions": [
                    "检查电源模块供电稳定性",
                    "验证主控芯片信号完整性",
                    "排查连接器接触不良问题",
                    "运行完整老化测试",
                ],
            }, ensure_ascii=False)

        if "分析" in content or "错误" in content:
            return json.dumps({
                "root_cause": "模拟分析：测试环境异常导致",
                "analysis": "经综合分析，该故障可能由测试治具接触不良引起，建议清洁后重新测试。",
                "repair_suggestions": [
                    "清洁测试探针及连接器",
                    "重新校准测试治具",
                    "更换同批次测试线缆",
                ],
            }, ensure_ascii=False)

        return json.dumps({
            "response": f"收到请求：{content[:50]}{'...' if len(content) > 50 else ''}",
        }, ensure_ascii=False)

    # ------------------------------------------------------------------
    # LLM 调用
    # ------------------------------------------------------------------

    async def chat_completion(
        self, messages: list[dict], model: Optional[str] = None, temperature: Optional[float] = None,
    ) -> str:
        await self._ensure_configured()
        if not self.openai_client:
            return self._mock_response(messages)
        return (await self.openai_client.chat.completions.create(
            model=model or self._config["model"],
            messages=messages,
            temperature=temperature if temperature is not None else self._config["temperature"],
        )).choices[0].message.content

    async def chat_completion_stream(
        self, messages: list[dict], token_cb: Callable[[str], Awaitable[None]],
        model: Optional[str] = None, temperature: Optional[float] = None,
    ) -> str:
        await self._ensure_configured()
        if not self.openai_client:
            result = self._mock_response(messages)
            for token in result:
                await token_cb(token)
            return result
        stream = await self.openai_client.chat.completions.create(
            model=model or self._config["model"],
            messages=messages,
            temperature=temperature if temperature is not None else self._config["temperature"],
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

    # ------------------------------------------------------------------
    # 诊断业务方法
    # ------------------------------------------------------------------

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