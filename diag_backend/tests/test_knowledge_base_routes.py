from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId


@pytest.mark.asyncio
async def test_upload_document_routes_knowledge_type_to_dataset(
    async_client,
    auth_headers: dict,
    tmp_path,
):
    document_id = ObjectId()
    collection = MagicMock()
    collection.insert_one = AsyncMock(
        return_value=SimpleNamespace(inserted_id=document_id)
    )
    collection.update_one = AsyncMock()

    with patch(
        "app.routers.knowledge_base.get_settings",
        return_value=SimpleNamespace(knowledge_base_storage_path=str(tmp_path)),
    ), patch(
        "app.routers.knowledge_base.get_collection",
        return_value=collection,
    ), patch(
        "app.routers.knowledge_base.ragflow_service.resolve_knowledge_dataset",
        new=AsyncMock(return_value="repair-dataset-id"),
    ) as resolve_dataset, patch(
        "app.routers.knowledge_base.ragflow_service.upload_document",
        new=AsyncMock(return_value={"id": "ragflow-doc-id"}),
    ) as upload_document, patch(
        "app.routers.knowledge_base.ragflow_service.run_parsing",
        new=AsyncMock(return_value=True),
    ), patch(
        "app.routers.knowledge_base.ragflow_service.get_document_status",
        new=AsyncMock(return_value="DONE"),
    ):
        response = await async_client.post(
            "/api/knowledge-base/documents",
            data={
                "title": "风扇维修案例",
                "tags": "风扇,维修",
                "knowledge_type": "repair_case",
            },
            files={"file": ("repair_case.md", b"# repair case", "text/markdown")},
            headers=auth_headers,
        )

    assert response.status_code == 200
    assert response.json()["success"] is True
    resolve_dataset.assert_awaited_once_with("repair_case")
    upload_document.assert_awaited_once()
    assert upload_document.await_args.kwargs["dataset_id"] == "repair-dataset-id"
    inserted = collection.insert_one.await_args.args[0]
    assert inserted["knowledge_type"] == "repair_case"
    assert inserted["user_id"] == "test-user-id-123"
    update = collection.update_one.await_args_list[0].args[1]["$set"]
    assert update["ragflow_dataset_id"] == "repair-dataset-id"
    assert update["ragflow_doc_id"] == "ragflow-doc-id"


@pytest.mark.asyncio
async def test_upload_document_without_type_uses_default_routing(
    async_client,
    auth_headers: dict,
    tmp_path,
):
    collection = MagicMock()
    collection.insert_one = AsyncMock(
        return_value=SimpleNamespace(inserted_id=ObjectId())
    )

    with patch(
        "app.routers.knowledge_base.get_settings",
        return_value=SimpleNamespace(knowledge_base_storage_path=str(tmp_path)),
    ), patch(
        "app.routers.knowledge_base.get_collection",
        return_value=collection,
    ), patch(
        "app.routers.knowledge_base.ragflow_service.resolve_knowledge_dataset",
        new=AsyncMock(return_value="default-dataset-id"),
    ) as resolve_dataset, patch(
        "app.routers.knowledge_base.ragflow_service.upload_document",
        new=AsyncMock(return_value={}),
    ):
        response = await async_client.post(
            "/api/knowledge-base/documents",
            files={"file": ("sop.md", b"# SOP", "text/markdown")},
            headers=auth_headers,
        )

    assert response.status_code == 200
    assert response.json()["success"] is True
    resolve_dataset.assert_awaited_once_with("")
    inserted = collection.insert_one.await_args.args[0]
    assert inserted["knowledge_type"] == ""


@pytest.mark.asyncio
async def test_ragflow_status_aggregates_retrieval_datasets(
    async_client,
    auth_headers: dict,
):
    with patch(
        "app.routers.knowledge_base.ragflow_service.resolve_retrieval_dataset_ids",
        new=AsyncMock(return_value=["default-id", "repair-id"]),
    ), patch(
        "app.routers.knowledge_base.ragflow_service.list_datasets",
        new=AsyncMock(
            return_value=[
                {"id": "default-id", "name": "default", "chunk_count": 8},
                {"id": "repair-id", "name": "repairs", "chunk_count": 12},
            ]
        ),
    ), patch(
        "app.routers.knowledge_base.ragflow_service.list_documents",
        new=AsyncMock(
            side_effect=[
                [{"id": "doc-1"}],
                [{"id": "doc-2"}, {"id": "doc-3"}],
            ]
        ),
    ):
        response = await async_client.get(
            "/api/knowledge-base/ragflow/status",
            headers=auth_headers,
        )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["dataset"] == {
        "id": "default-id",
        "name": "多数据集知识库",
        "document_count": 3,
        "chunk_count": 20,
    }
    assert [dataset["id"] for dataset in body["datasets"]] == [
        "default-id",
        "repair-id",
    ]
