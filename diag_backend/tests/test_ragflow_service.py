"""RAGFlow retrieval 错误处理测试。"""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.services import ragflow_service


@pytest.mark.asyncio
async def test_retrieval_business_error_returns_concise_warning(caplog):
    response = Mock()
    response.status_code = 200
    response.text = '{"code": 100, "message": "dataset is not ready"}'
    response.raise_for_status = Mock()
    response.json.return_value = {
        "code": 100,
        "message": "dataset is not ready",
    }
    client = AsyncMock()
    client.post.return_value = response

    @asynccontextmanager
    async def fake_client(_timeout):
        yield client

    with patch.object(ragflow_service, "_ok", return_value=True), patch.object(
        ragflow_service, "_cfg", return_value=("http://ragflow.test", "secret")
    ), patch.object(
        ragflow_service,
        "resolve_retrieval_dataset_ids",
        new=AsyncMock(return_value=["dataset-1", "dataset-2"]),
    ), patch.object(ragflow_service, "_client", new=fake_client):
        result = await ragflow_service.search_knowledge_base("disk error")

    assert result == {
        "references": [],
        "warning": "知识库检索暂不可用: dataset is not ready",
    }
    assert "dataset is not ready" in caplog.text
    request_body = client.post.await_args.kwargs["json"]
    assert request_body["dataset_ids"] == ["dataset-1", "dataset-2"]


@pytest.mark.asyncio
async def test_resolve_retrieval_dataset_ids_combines_default_and_existing_types():
    datasets = [
        {"id": "default-id", "name": "weaveeye-knowledge-base"},
        {"id": "repair-id", "name": "weaveeye-repair-cases"},
        {"id": "other-id", "name": "unrelated-dataset"},
        {"id": "repair-id", "name": "weaveeye-repair-cases"},
    ]
    with patch.object(
        ragflow_service,
        "resolve_default_dataset",
        new=AsyncMock(return_value="default-id"),
    ), patch.object(
        ragflow_service,
        "knowledge_dataset_names",
        return_value={
            "troubleshooting": "weaveeye-troubleshooting",
            "repair_case": "weaveeye-repair-cases",
        },
    ), patch.object(
        ragflow_service,
        "list_datasets",
        new=AsyncMock(return_value=datasets),
    ):
        dataset_ids = await ragflow_service.resolve_retrieval_dataset_ids()

    assert dataset_ids == ["default-id", "repair-id"]


@pytest.mark.asyncio
async def test_resolve_knowledge_dataset_routes_type_and_falls_back_to_default():
    resolve_dataset = AsyncMock(return_value="repair-id")
    resolve_default = AsyncMock(return_value="default-id")
    with patch.object(
        ragflow_service,
        "knowledge_dataset_names",
        return_value={"repair_case": "weaveeye-repair-cases"},
    ), patch.object(
        ragflow_service,
        "resolve_dataset",
        new=resolve_dataset,
    ), patch.object(
        ragflow_service,
        "resolve_default_dataset",
        new=resolve_default,
    ):
        repair_id = await ragflow_service.resolve_knowledge_dataset("repair_case")
        default_id = await ragflow_service.resolve_knowledge_dataset("")

    assert repair_id == "repair-id"
    resolve_dataset.assert_awaited_once_with(
        "weaveeye-repair-cases",
        description="WeaveEye 维修案例知识库",
    )
    assert default_id == "default-id"
    resolve_default.assert_awaited_once()
