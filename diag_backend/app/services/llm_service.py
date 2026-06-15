from typing import Awaitable, Callable, Optional
import json
import re

import httpx
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
- evidence: 关键证据列表，每项为一个对象 { "log_line": "日志原文行", "conclusion": "该行的结论说明" }
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
            "max_tokens": 28000,
        }
        self._loaded = False

    # ------------------------------------------------------------------
    # 配置加载
    # ------------------------------------------------------------------

    async def _load_config_from_db(self) -> dict:
        """从 MongoDB 加载 AI 配置"""
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
                    "max_tokens": config.get("max_tokens", 28000),
                }
        except Exception:
            pass
        return {"api_key": "", "base_url": "", "model": "gpt-4-turbo", "temperature": 0.7, "max_tokens": 28000}

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
            kwargs["timeout"] = httpx.Timeout(300.0, connect=10.0, read=120.0)
            self.openai_client = AsyncOpenAI(**kwargs)
        else:
            self.openai_client = None

    async def reload_config(self):
        """从数据库重新加载配置（热加载）"""
        self._config = await self._load_config_from_db()
        self._rebuild_client()
        self._loaded = True

    # ------------------------------------------------------------------
    # 公共配置访问
    # ------------------------------------------------------------------

    def get_config_value(self, key: str, default=None):
        """安全地获取配置项"""
        return self._config.get(key, default)

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

    SN_DIAGNOSIS_FALLBACK = {
        "category": "未知", "summary": "解析失败", "confidence": 0.5,
        "root_cause_detail": "", "affected_components": [],
        "suggestions": ["联系技术支持"], "preventive_measures": [],
    }

    def _build_sn_diagnosis_prompt(self, sn: str, device_info: dict,
                                    test_logs: list[dict], maintenance: list[dict],
                                    similar_cases: list[dict], kb_context: str = "",
                                    failed_logs: Optional[list[dict]] = None) -> str:
        sections: list[str] = [
            "你是一个资深的服务器硬件诊断工程师，拥有丰富的 x86 服务器、存储设备、网络设备故障排查经验。",
            "请综合利用以下数据源以及你自身的硬件工程知识，对设备进行深度诊断分析：",
        ]

        # 失败用例 — 重点分析对象
        failed = failed_logs or []
        if failed:
            lines = ["## 一、失败测试用例（重点分析）\n以下为该设备在 SIMS 测试中的失败项目："]
            for fl in failed[:10]:
                lines.append(f"- [{fl.get('test_time')}] {fl.get('test_item')}: {fl.get('fail_details', '异常')}")
            sections.append("\n".join(lines))

        # 知识库上下文
        if kb_context:
            sections.append(kb_context)

        # 设备信息 + 完整日志 + 维修 + 案例
        sections.append(f"""## 二、设备背景信息
- 设备 SN: {sn}
- 型号: {device_info.get('model', '未知')}
- 批次: {device_info.get('batch', '未知')}
- 厂区: {device_info.get('factory', '未知')}

## 三、全部测试日志（含通过项，用于全面了解设备状态）
{chr(10).join([f"- [{tl.get('test_time')}] {tl.get('test_item')}: {tl.get('fail_details', '通过')}" for tl in test_logs[:10]])}

## 四、历史维修记录
{chr(10).join([f"- [{r.get('date')}] 更换 {r.get('component')}：{r.get('action')}" for r in maintenance[:5]]) if maintenance else "无历史维修记录"}

## 五、相似历史案例
{chr(10).join([f"- {c.get('title')}：根因={c.get('root_cause', '未知')}" for c in similar_cases[:3]]) if similar_cases else "未匹配到相似案例"}""")

        sections.append("""## 诊断要求

请综合以上所有信息，结合你作为硬件工程师的专业知识（包括但不限于：Intel/AMD CPU 架构、DDR4/DDR5 内存子系统、PCIe 总线、电源管理、散热设计、BMC/IPMI 管理、固件交互），进行深度诊断分析。

如有知识库参考文档，优先参考其中的技术方案；对于知识库未覆盖的部分，请运用你自身的工程经验进行推理和补充。

请以 JSON 格式返回（所有字段为必填）：
```json
{
  "category": "故障大类（如：内存故障、电源故障、CPU故障、存储故障、网络故障、散热故障、固件/BIOS故障、组装工艺问题、其他）",
  "summary": "一段 100-200 字的诊断摘要，概述核心发现和诊断结论",
  "confidence": 0.0-1.0,
  "root_cause_detail": "详细的根因分析（200-400字），包含故障机理、可能的原因链条、为什么排除其他可能性",
  "affected_components": ["受影响的硬件组件列表，如CPU1_Socket、DIMM_A4、PSU2等，如无法确定则返回空数组"],
  "suggestions": ["3-5 条维修建议，每条包含具体操作步骤，按优先级从高到低排序"],
  "preventive_measures": ["2-3 条预防措施，说明如何避免同类问题再次发生"]
}
```""")
        return "\n\n".join(sections)

    async def diagnose_sn(self, sn: str, device_info: dict, test_logs: list[dict],
                          maintenance: list[dict], similar_cases: list[dict],
                          kb_context: str = "", failed_logs: Optional[list[dict]] = None) -> dict:
        prompt = self._build_sn_diagnosis_prompt(
            sn, device_info, test_logs, maintenance, similar_cases, kb_context, failed_logs)
        return self._parse_json_response(
            await self.chat_completion([{"role": "system", "content": "硬件诊断工程师"},
                                        {"role": "user", "content": prompt}]),
            self.SN_DIAGNOSIS_FALLBACK,
        )

    async def diagnose_sn_stream(self, sn: str, device_info: dict, test_logs: list[dict],
                                  maintenance: list[dict], similar_cases: list[dict],
                                  token_cb: Callable[[str], Awaitable[None]],
                                  kb_context: str = "", failed_logs: Optional[list[dict]] = None) -> dict:
        prompt = self._build_sn_diagnosis_prompt(
            sn, device_info, test_logs, maintenance, similar_cases, kb_context, failed_logs)
        return self._parse_json_response(
            await self.chat_completion_stream(
                [{"role": "system", "content": "硬件诊断工程师"},
                 {"role": "user", "content": prompt}],
                token_cb,
            ),
            self.SN_DIAGNOSIS_FALLBACK,
        )

    async def follow_up_question(self, question: str, diagnosis_context: str) -> str:
        prompt = f"""你是一个专业的硬件诊断工程师。以下是之前对设备进行的诊断结果：

{diagnosis_context}

用户现在有一个追问：{question}

请用中文回答用户的问题，保持专业、简洁、准确。基于已有的诊断结果回答，不要编造没有的信息。"""

        return await self.chat_completion(
            [{"role": "system", "content": "硬件诊断工程师"},
             {"role": "user", "content": prompt}]
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
        result = self._parse_json_response(
            await self.chat_completion_stream(
                [{"role": "system", "content": "硬件故障诊断专家"},
                 {"role": "user", "content": prompt}],
                token_cb,
            ),
            {"root_cause": "分析失败", "evidence": [], "repair_suggestions": ["请重试"], "knowledge_refs": []}
        )
        # 将 evidence 中的字符串条目转为 { "log_line": str, "conclusion": "" }
        if "evidence" in result and isinstance(result["evidence"], list):
            result["evidence"] = [
                {"log_line": item, "conclusion": ""} if isinstance(item, str) else item
                for item in result["evidence"]
            ]
        return result


llm_service = LLMService()