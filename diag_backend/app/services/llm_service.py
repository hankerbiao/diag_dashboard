from typing import Awaitable, Callable, Literal, Optional
import json
import re
from string import Formatter

import httpx
from openai import AsyncOpenAI, BadRequestError

from .log_extractor import (
    LOG_EXTRACTION_SYSTEM_PROMPT,
    LOG_EXTRACTION_USER_PROMPT_TPL,
)

DEVICE_INFO_TPL = """## 设备信息
- 设备 SN: {sn}
- 测试项目: {test_item}
- 错误信息: {fail_details}
- 测试时间: {test_time}"""


def _build_diagnosis_prompt(error_log: dict, knowledge_context: str, extra_hint: str = "") -> str:
    sn = error_log.get('sn', '未知')
    test_item = error_log.get('test_item', '未知')
    fail_details = error_log.get('fail_details', '无')
    test_time = error_log.get('test_time', '未知')
    info_block = DEVICE_INFO_TPL.format(
        sn=sn, test_item=test_item, fail_details=fail_details, test_time=test_time,
    )
    return f"""请根据以下内容进行故障诊断。

{info_block}

{knowledge_context}

{extra_hint}

请以 JSON 格式返回诊断结果：
- root_cause: 诊断的根本原因
- evidence: 关键证据列表，每项为一个对象 {{ "log_line": "日志原文行", "conclusion": "该行的结论说明" }}
- analysis: 详细分析摘要
- repair_suggestions: 维修建议列表（3-5条）
- knowledge_refs: 知识库引用列表 [{{source, content}}]，未引用则返回 []"""


class LLMService:
    """LLM 服务封装 — 支持数据库配置热加载"""

    # 模型上下文窗口配置（可通过数据库覆盖）
    DEFAULT_MODEL_CONTEXT_LEN = 1000000

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """粗略估算 token 数量：中文约 1.5 token/字，英文约 0.25 token/字，混合取 2 字符/token"""
        if not text:
            return 0
        total_chars = len(text)
        # 统计中文字符数
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        # 中文字符约 1.5 token，非中文字符约 0.25 token
        non_chinese = total_chars - chinese_chars
        return int(chinese_chars * 1.5 + non_chinese * 0.25)

    @staticmethod
    def _truncate_text(text: str, max_chars: int) -> str:
        """按字符数截断文本，尽量在段尾截断"""
        if len(text) <= max_chars:
            return text
        # 尝试在段落末尾截断
        truncated = text[:max_chars]
        last_break = max(truncated.rfind("\n\n"), truncated.rfind("\n"), truncated.rfind("。"))
        if last_break > max_chars * 0.7:
            truncated = truncated[:last_break + 1]
        return truncated + "\n\n[注：内容过长，已自动截断]"

    def _build_prompt_with_truncation(self, sn: str, device_info: dict,
                                       test_logs: list[dict], maintenance: list[dict],
                                       similar_cases: list[dict], kb_context: str = "",
                                       failed_logs: Optional[list[dict]] = None) -> str:
        """构建诊断 prompt 并确保不超过模型上下文限制"""
        system_prompt = "硬件诊断工程师"
        system_tokens = self._estimate_tokens(system_prompt)
        # 模型上下文长度，加上 10000 的安全余量
        context_len = self._config["answer"].get("model_context_len", self.DEFAULT_MODEL_CONTEXT_LEN)
        max_output = self._config["answer"].get("max_tokens", 28000) or 28000
        # 安全限制：max_output 不超过上下文窗口的 70%，且至少留 4096 给 prompt
        safe_max_output = min(max_output, int(context_len * 0.7), context_len - 4096)
        safe_max_output = max(safe_max_output, 1024)
        available_tokens = context_len - safe_max_output - system_tokens - 10000
        # 转换为字符预算（保守估计 2 字符/token）
        char_budget = int(available_tokens * 2.0)

        # 诊断要求模板（固定部分）
        diagnosis_template = """## 诊断要求

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
```"""
        fixed_overhead = self._estimate_tokens(diagnosis_template)
        char_budget -= int(fixed_overhead * 2.0)

        # 动态分配各部分字符预算
        # kb_context 和其他内容各占一半预算
        content_budget = max(char_budget // 2, 500)
        kb_budget = max(char_budget - content_budget, 1000)

        # 构建各部分
        truncated_kb = self._truncate_text(kb_context, kb_budget) if kb_context else ""

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
        if truncated_kb:
            sections.append(truncated_kb)

        # 设备信息 + 完整日志 + 维修 + 案例（允许截断）
        content_parts = [f"""## 二、设备背景信息
- 设备 SN: {sn}
- 型号: {device_info.get('model', '未知')}
- 批次: {device_info.get('batch', '未知')}
- 厂区: {device_info.get('factory', '未知')}

## 三、全部测试日志（含通过项，用于全面了解设备状态）
{chr(10).join([f"- [{tl.get('test_time')}] {tl.get('test_item')}: {tl.get('fail_details', '通过')}" for tl in test_logs[:10]])}

## 四、历史维修记录
{chr(10).join([f"- [{r.get('date')}] 更换 {r.get('component')}：{r.get('action')}" for r in maintenance[:5]]) if maintenance else "无历史维修记录"}

## 五、相似历史案例
{chr(10).join([f"- {c.get('title')}：根因={c.get('root_cause', '未知')}" for c in similar_cases[:3]]) if similar_cases else "未匹配到相似案例"}"""]
        truncated_content = self._truncate_text("\n\n".join(content_parts), content_budget)
        sections.append(truncated_content)

        sections.append(diagnosis_template)
        final_prompt = "\n\n".join(sections)

        # 最终安全校验
        estimated_total = self._estimate_tokens(final_prompt) + system_tokens
        if estimated_total > context_len - safe_max_output:
            # 如果仍然超限，用更保守的策略重新裁剪
            from logging import getLogger
            getLogger(__name__).warning(
                "prompt 仍超限，执行激进裁剪",
                extra={"estimated_tokens": estimated_total, "limit": context_len - safe_max_output, "sn": sn},
            )
            # 大幅减少内容
            safe_budget = int((context_len - safe_max_output - system_tokens - 10000) * 1.5)
            sections[-2] = self._truncate_text(sections[-2], safe_budget // 3)
            sections[-3] = self._truncate_text(sections[-3], safe_budget // 3)
            final_prompt = "\n\n".join(sections)

        return final_prompt

    def __init__(self):
        self._answer_client: Optional[AsyncOpenAI] = None
        self._extraction_client: Optional[AsyncOpenAI] = None
        self._config: dict = {"answer": {}, "extraction": {}}
        self._loaded = False

    # openai_client 向后兼容别名（指向回答模型客户端）
    @property
    def openai_client(self) -> Optional[AsyncOpenAI]:
        return self._answer_client

    @openai_client.setter
    def openai_client(self, value: Optional[AsyncOpenAI]) -> None:
        self._answer_client = value

    # ------------------------------------------------------------------
    # 配置加载
    # ------------------------------------------------------------------

    async def _load_config_from_db(self) -> dict:
        """从 MongoDB 加载 AI 配置（回答模型 + 提取模型双配置）

        提取模型字段留空时回退复用回答模型配置，以兼容单模型部署。
        """
        from ..core.mongodb import get_collection
        col = get_collection("global_app_config")
        config = await col.find_one({"_id": "ai_config"})
        if not config:
            raise RuntimeError("AI 配置未初始化，请先在设置页面配置 LLM 参数")

        answer = {
            "api_key": config.get("api_key", ""),
            "base_url": config.get("base_url", ""),
            "model": config.get("model", ""),
            "temperature": config.get("temperature", 0.0),
            "max_tokens": config.get("max_tokens", 0),
            "chat_template_kwargs": config.get("chat_template_kwargs", {"enable_thinking": False}),
            "timeout": config.get("timeout", 0),
            "model_context_len": config.get("model_context_len", self.DEFAULT_MODEL_CONTEXT_LEN),
        }
        extraction = {
            "api_key": config.get("extraction_api_key") or answer["api_key"],
            "base_url": config.get("extraction_base_url") or answer["base_url"],
            "model": config.get("extraction_model") or answer["model"],
            "temperature": config.get("extraction_temperature", 0.0),
            "max_tokens": config.get("extraction_max_tokens") or answer["max_tokens"],
            "chat_template_kwargs": config.get("extraction_chat_template_kwargs") or answer["chat_template_kwargs"],
            "timeout": config.get("extraction_timeout") or answer["timeout"],
            "model_context_len": config.get("extraction_model_context_len") or answer["model_context_len"],
        }

        if not answer["api_key"] and not extraction["api_key"]:
            raise RuntimeError("AI 配置未初始化，请先在设置页面配置 LLM 参数")
        return {"answer": answer, "extraction": extraction}

    async def _ensure_configured(self):
        """懒加载配置（仅在无预设客户端时执行一次）"""
        if not self._loaded and self._answer_client is None:
            self._config = await self._load_config_from_db()
            self._rebuild_clients()
            self._loaded = True

    def _build_client(self, cfg: dict) -> AsyncOpenAI:
        """根据单个配置字典构建 AsyncOpenAI 客户端"""
        key = cfg.get("api_key", "")
        url = cfg.get("base_url", "")
        timeout = cfg.get("timeout", 300) or 300
        kwargs = {"api_key": key}
        if url:
            kwargs["base_url"] = url
        kwargs["timeout"] = httpx.Timeout(timeout, connect=10.0, read=timeout)
        return AsyncOpenAI(**kwargs)

    def _rebuild_clients(self):
        """根据当前 _config 重建回答/提取两个 AsyncOpenAI 客户端"""
        self._answer_client = self._build_client(self._config["answer"])
        self._extraction_client = self._build_client(self._config["extraction"])

    async def reload_config(self):
        """从数据库重新加载配置（热加载）"""
        self._config = await self._load_config_from_db()
        self._rebuild_clients()
        self._loaded = True

    # ------------------------------------------------------------------
    # 公共配置访问
    # ------------------------------------------------------------------

    def get_config_value(self, key: str, default=None, client: Literal["answer", "extraction"] = "answer"):
        """安全地获取配置项（client 指定回答/提取模型配置）"""
        return self._config.get(client, {}).get(key, default)

    # ------------------------------------------------------------------
    # LLM 调用
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # 模拟响应（未配置模型时优雅降级）
    # ------------------------------------------------------------------

    def _mock_response(self, messages: list[dict], client: Literal["answer", "extraction"] = "answer") -> str:
        """未配置 LLM 时返回结构化占位响应，保证接口不崩溃。

        - answer 客户端：根据消息内容返回诊断 / 分析两类 JSON 占位。
        - extraction 客户端：返回与 LOG_EXTRACTION_FALLBACK 一致的结构。
        """
        if client == "extraction":
            return json.dumps(self.LOG_EXTRACTION_FALLBACK, ensure_ascii=False)

        text = " ".join(str(m.get("content", "")) for m in messages)
        if "分析" in text or "错误" in text or "root_cause" in text or "分析" in text:
            return json.dumps({
                "root_cause": "（模拟）未配置模型，需进一步定位",
                "analysis": "当前未配置 LLM，返回模拟分析。",
                "repair_suggestions": ["请在设置页配置诊断回答模型（强推理）"],
            }, ensure_ascii=False)
        return json.dumps({
            "category": "未知",
            "summary": "（模拟）未配置模型，返回占位诊断。",
            "confidence": 0.5,
            "root_cause_detail": "未配置 LLM，无法进行深度诊断。",
            "affected_components": [],
            "suggestions": ["请在设置页配置诊断回答模型（强推理）"],
            "preventive_measures": [],
        }, ensure_ascii=False)

    async def chat_completion(
        self, messages: list[dict], model: Optional[str] = None, temperature: Optional[float] = None,
        client: Literal["answer", "extraction"] = "answer",
    ) -> str:
        await self._ensure_configured()
        cfg = self._config[client]
        client_obj = self._answer_client if client == "answer" else self._extraction_client
        # 未配置模型（客户端为空或 key 缺失）：返回模拟响应，避免接口崩溃
        if client_obj is None or not cfg.get("api_key"):
            return self._mock_response(messages, client)
        extra_kwargs = {}
        chat_template_kwargs = cfg.get("chat_template_kwargs")
        if chat_template_kwargs:
            extra_kwargs["extra_body"] = chat_template_kwargs

        # 自动限制 max_tokens：不超过模型上下文窗口的 70%，且至少保留 4096 token 给 prompt
        context_len = cfg.get("model_context_len", self.DEFAULT_MODEL_CONTEXT_LEN)
        max_output = cfg.get("max_tokens", 28000) or 28000
        safe_max_output = min(max_output, int(context_len * 0.7), context_len - 4096)
        safe_max_output = max(safe_max_output, 1024)  # 至少 1024

        try:
            return (await client_obj.chat.completions.create(
                model=model or cfg["model"],
                messages=messages,
                temperature=temperature if temperature is not None else cfg["temperature"],
                max_tokens=safe_max_output,
                **extra_kwargs,
            )).choices[0].message.content
        except BadRequestError as e:
            detail = e.body.get("error", {}).get("message", str(e)) if isinstance(e.body, dict) else str(e)
            raise RuntimeError(f"LLM 请求被拒绝: {detail}") from e

    async def chat_completion_stream(
        self, messages: list[dict], token_cb: Callable[[str], Awaitable[None]],
        model: Optional[str] = None, temperature: Optional[float] = None,
        client: Literal["answer", "extraction"] = "answer",
    ) -> str:
        await self._ensure_configured()
        cfg = self._config[client]
        client_obj = self._answer_client if client == "answer" else self._extraction_client
        # 未配置模型：直接返回模拟响应
        if client_obj is None or not cfg.get("api_key"):
            mock = self._mock_response(messages, client)
            await token_cb(mock)
            return mock
        extra_kwargs = {"stream": True}
        chat_template_kwargs = cfg.get("chat_template_kwargs")
        if chat_template_kwargs:
            extra_kwargs["extra_body"] = chat_template_kwargs

        # 自动限制 max_tokens：不超过模型上下文窗口的 70%，且至少保留 4096 token 给 prompt
        context_len = cfg.get("model_context_len", self.DEFAULT_MODEL_CONTEXT_LEN)
        max_output = cfg.get("max_tokens", 28000) or 28000
        safe_max_output = min(max_output, int(context_len * 0.7), context_len - 4096)
        safe_max_output = max(safe_max_output, 1024)

        try:
            stream = await client_obj.chat.completions.create(
                model=model or cfg["model"],
                messages=messages,
                temperature=temperature if temperature is not None else cfg["temperature"],
                max_tokens=safe_max_output,
                **extra_kwargs,
            )
        except BadRequestError as e:
            detail = e.body.get("error", {}).get("message", str(e)) if isinstance(e.body, dict) else str(e)
            raise RuntimeError(f"LLM 请求被拒绝: {detail}") from e
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
        """构建 SN 诊断 prompt（委托给带截断的版本）"""
        return self._build_prompt_with_truncation(
            sn, device_info, test_logs, maintenance, similar_cases, kb_context, failed_logs)

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

    # ──────────────────────────────────────────────────────────────
    # AI 级日志提取
    # ──────────────────────────────────────────────────────────────

    LOG_EXTRACTION_FALLBACK = {
        "errors": [],
        "summary": "AI 日志提取失败",
        "has_critical_errors": False,
        "suggested_root_cause": "",
    }

    async def extract_log_with_llm(
        self,
        raw_log_text: str,
        encoding_stats: Optional[dict] = None,
        system_prompt: Optional[str] = None,
        user_template: Optional[str] = None,
        client: Literal["answer", "extraction"] = "extraction",
        raise_on_error: bool = False,
    ) -> dict:
        """
        使用 LLM 从原始日志中提取关键错误信息（AI 级精炼）。

        支持外部覆盖 prompt（按机型配置的提取 prompt 注入），并通过 client
        参数选择「提取模型（快速）」或「回答模型（强推理）」。

        Args:
            raw_log_text: 原始日志文本（某一段落）
            encoding_stats: 编码提取阶段的统计信息（可选）
            system_prompt: 覆盖系统提示词；为空则用默认 LOG_EXTRACTION_SYSTEM_PROMPT
            user_template: 覆盖用户提示词模板（接受 {log_text}/{total_lines}/... 占位符）
            client: 使用的模型客户端，"extraction"=快速提取模型，"answer"=推理模型

        Returns:
            dict: {"errors": [...], "summary": str, "has_critical_errors": bool,
                   "suggested_root_cause": str}
        """
        stats = encoding_stats or {}
        template = user_template or LOG_EXTRACTION_USER_PROMPT_TPL
        user_prompt = self._safe_format(
            template,
            total_lines=stats.get("total_lines", "?"),
            total_chars=stats.get("total_chars", "?"),
            matched_lines=stats.get("matched_lines", "?"),
            paragraphs=stats.get("paragraphs", "?"),
            segment_start_line=stats.get("segment_start_line", 1),
            segment_end_line=stats.get("segment_end_line", stats.get("total_lines", "?")),
            segment_index=stats.get("segment_index", 0) + 1,
            segment_count=stats.get("segment_count", 1),
            log_text=raw_log_text,
        )

        try:
            response = await self.chat_completion(
                [
                    {"role": "system", "content": system_prompt or LOG_EXTRACTION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                client=client,
            )
            parsed = json.loads(self._extract_json(response))
            if not isinstance(parsed, dict) or not isinstance(parsed.get("errors", []), list):
                raise ValueError("AI 日志提取结果结构无效")
            return parsed
        except Exception as e:
            logger = __import__("logging").getLogger(__name__)
            logger.warning("AI 日志提取失败 error=%s", e)
            if raise_on_error:
                raise RuntimeError(f"AI 日志提取失败: {e}") from e
            return dict(self.LOG_EXTRACTION_FALLBACK, summary=f"AI 日志提取异常: {e}")

    @staticmethod
    def _safe_format(template: str, **fields) -> str:
        """容忍式字符串格式化：仅替换模板中引用的字段，缺失字段填充空串。

        避免自定义 user_template 缺少某些占位符（如 {total_lines}）时抛 KeyError。
        """
        formatter = Formatter()
        used = {name for _, name, _, _ in formatter.parse(template) if name}
        merged = {k: fields.get(k, "") for k in used}
        return formatter.format(template, **merged)


llm_service = LLMService()
