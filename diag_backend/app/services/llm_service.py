from openai import AsyncOpenAI
from ..core.config import get_settings
from typing import Optional
import json

settings = get_settings()


class LLMService:
    """LLM 服务封装，支持 OpenAI/Gemini"""

    def __init__(self):
        self.openai_client: Optional[AsyncOpenAI] = None
        if settings.openai_api_key:
            self.openai_client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def chat_completion(
        self,
        messages: list[dict],
        model: str = "gpt-4-turbo",
        temperature: float = 0.7
    ) -> str:
        """调用 LLM 生成对话完成"""

        if not self.openai_client:
            # Mock response for development
            return self._mock_response(messages)

        response = await self.openai_client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature
        )

        return response.choices[0].message.content

    async def diagnose_sn(
        self,
        sn: str,
        device_info: dict,
        test_logs: list[dict],
        maintenance: list[dict],
        similar_cases: list[dict]
    ) -> dict:
        """SN 诊断"""

        prompt = f"""
你是一个专业的硬件诊断工程师。请根据以下信息对设备进行诊断：

设备信息：
- SN: {sn}
- 型号: {device_info.get('model', '未知')}
- 批次: {device_info.get('batch', '未知')}

测试日志：
{chr(10).join([f"- [{log.get('test_time')}] {log.get('test_item')}: {log.get('fail_details', '通过')}" for log in test_logs[:10]])}

维修历史：
{chr(10).join([f"- [{record.get('date')}] {record.get('component')}: {record.get('action')}" for record in maintenance[:5]])}

相似案例：
{chr(10).join([f"- {case.get('title')}: {case.get('root_cause', '')}" for case in similar_cases[:3]])}

请以 JSON 格式返回诊断结果，包含以下字段：
- category: 故障类别
- summary: 诊断总结
- confidence: 置信度 (0-1)
- suggestions: 修复建议列表
"""

        response = await self.chat_completion([
            {"role": "system", "content": "你是一个专业的硬件诊断工程师。"},
            {"role": "user", "content": prompt}
        ])

        # 解析 JSON 响应
        import json
        try:
            return json.loads(response)
        except:
            return {
                "category": "未知",
                "summary": response,
                "confidence": 0.5,
                "suggestions": ["建议联系技术支持"]
            }

    async def analyze_error(
        self,
        error_log: dict,
        similar_cases: list[dict]
    ) -> dict:
        """分析异常日志"""

        prompt = f"""
请分析以下测试异常：

异常详情：
- SN: {error_log.get('sn')}
- 测试项目: {error_log.get('test_item')}
- 错误信息: {error_log.get('fail_details')}

相似案例：
{chr(10).join([f"- {case.get('title')}: {case.get('root_cause', '')}" for case in similar_cases[:2]])}

请返回 JSON 格式分析结果：
- root_cause: 根本原因
- analysis: 详细分析
- repair_suggestions: 修复建议
"""

        response = await self.chat_completion([
            {"role": "system", "content": "你是一个专业的硬件故障分析专家。"},
            {"role": "user", "content": prompt}
        ])

        import json
        try:
            return json.loads(response)
        except:
            return {
                "root_cause": "分析中",
                "analysis": response,
                "repair_suggestions": ["进一步诊断中..."]
            }

    def _mock_response(self, messages: list[dict]) -> str:
        """开发环境模拟响应"""
        user_message = messages[-1]["content"] if messages else ""

        if "诊断" in user_message:
            return json.dumps({
                "category": "内存故障",
                "summary": "基于知识图谱分析，DIMM插槽4发生结构性硬件故障的概率极高",
                "confidence": 0.92,
                "suggestions": [
                    "执行 diag --clear-ecc-error 0x4 清除 ECC 寄存器",
                    "更换 8GB-DDR4-HYNX 内存条",
                    "执行 MEM_STRESS_T2 强化测试"
                ]
            })
        elif "分析" in user_message:
            return json.dumps({
                "root_cause": "电压离散跳动导致内存校验失败",
                "analysis": "该批次料件在高温负荷下表现出电压离散跳动特征",
                "repair_suggestions": [
                    "检查主板阻抗节点",
                    "执行 diag --verify 强制复位",
                    "如无效，更换相应 IC 组件"
                ]
            })
        else:
            return "感谢您的查询，请提供更多详细信息。"


# 全局实例
llm_service = LLMService()