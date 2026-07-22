"""
提取 Prompt 注册表 — 按机型读取/管理 AI 错误日志提取 prompt。

存储集合：log_extraction_prompts
- _id="default"：默认 prompt（未配置机型的回退）
- _id=<机型>：该机型的专属提取 prompt

prompt 由 system_prompt + user_template 组成，user_template 支持占位符：
{log_text} / {total_lines} / {total_chars} / {matched_lines} / {paragraphs}
"""

from __future__ import annotations

import logging

from ...core.mongodb import get_collection
from ...core.utils import utc_now_iso
from ..log_extractor import (
    LOG_EXTRACTION_SYSTEM_PROMPT,
    LOG_EXTRACTION_USER_PROMPT_TPL,
)

logger = logging.getLogger(__name__)

DEFAULT_ID = "default"
COLLECTION = "log_extraction_prompts"


class PromptRegistry:
    """从 MongoDB 读取/管理按机型配置的提取 prompt。"""

    def __init__(self, collection: str = COLLECTION):
        self.collection = collection

    async def get_prompt(self, model: str) -> dict:
        """获取机型对应 prompt；未配置或不存在时回退 default / 代码内置兜底。"""
        col = get_collection(self.collection)
        doc = None
        if model and model != DEFAULT_ID:
            doc = await col.find_one({"_id": model})
        if not doc:
            doc = await col.find_one({"_id": DEFAULT_ID})

        if not doc:
            return {
                "model": DEFAULT_ID,
                "system_prompt": LOG_EXTRACTION_SYSTEM_PROMPT,
                "user_template": LOG_EXTRACTION_USER_PROMPT_TPL,
            }

        return {
            "model": doc.get("model", doc.get("_id", DEFAULT_ID)),
            "system_prompt": doc.get("system_prompt") or LOG_EXTRACTION_SYSTEM_PROMPT,
            "user_template": doc.get("user_template") or LOG_EXTRACTION_USER_PROMPT_TPL,
        }

    async def list_prompts(self) -> list[dict]:
        """列出全部已配置的 prompt（含 default）。"""
        col = get_collection(self.collection)
        cursor = col.find({})
        docs = await cursor.to_list(length=200)
        out: list[dict] = []
        for d in docs:
            mid = d.get("_id", DEFAULT_ID)
            out.append({
                "model": d.get("model", mid),
                "is_default": d.get("is_default", mid == DEFAULT_ID),
                "system_prompt": d.get("system_prompt", ""),
                "user_template": d.get("user_template", ""),
                "updated_at": d.get("updated_at", ""),
                "updated_by": d.get("updated_by", ""),
            })
        return out

    async def upsert(self, model: str, system_prompt: str, user_template: str,
                     updated_by: str = "system") -> None:
        """新增或更新某机型的提取 prompt（model="default" 即默认）。"""
        col = get_collection(self.collection)
        await col.update_one(
            {"_id": model},
            {"$set": {
                "model": model,
                "is_default": model == DEFAULT_ID,
                "system_prompt": system_prompt,
                "user_template": user_template,
                "updated_by": updated_by,
                "updated_at": utc_now_iso(),
            }},
            upsert=True,
        )

    async def delete(self, model: str) -> None:
        """删除某机型的提取 prompt；default 不可删。"""
        if model == DEFAULT_ID:
            raise ValueError("默认 prompt 不可删除")
        col = get_collection(self.collection)
        await col.delete_one({"_id": model})
