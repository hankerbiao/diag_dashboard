from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId


def _feedback_doc(feedback_id: ObjectId) -> dict:
    return {
        "_id": feedback_id,
        "user_id": "test-user-id-123",
        "history_id": None,
        "sn": "SN-FEEDBACK-01",
        "factory": "kunshan",
        "rating": "unsolved",
        "comment": "更换部件后问题仍然存在",
        "diagnosis_context": "诊断认为是风扇故障",
        "status": "pending",
        "resolution_note": "",
        "created_at": "2026-07-23T10:00:00+00:00",
    }


@pytest.mark.asyncio
async def test_list_feedback_returns_summary_and_normalized_items(
    async_client,
    auth_headers: dict,
):
    feedback_id = ObjectId()
    collection = MagicMock()
    collection.count_documents = AsyncMock(side_effect=[12, 7, 3, 2, 4, 1, 2])
    cursor = MagicMock()
    cursor.sort.return_value = cursor
    cursor.skip.return_value = cursor
    cursor.limit.return_value = cursor
    cursor.to_list = AsyncMock(return_value=[_feedback_doc(feedback_id)])
    collection.find.return_value = cursor

    with patch("app.routers.diagnosis.get_collection", return_value=collection):
        response = await async_client.get(
            "/api/diagnosis/feedback",
            params={
                "factory": "kunshan",
                "rating": "unsolved",
                "status": "pending",
                "keyword": "风扇",
                "page": 1,
                "limit": 20,
            },
            headers=auth_headers,
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["total"] == 2
    assert body["data"]["summary"] == {
        "total": 12,
        "solved": 7,
        "partially": 3,
        "unsolved": 2,
        "pending": 4,
        "processing": 1,
        "solved_rate": 0.5833,
    }
    assert body["data"]["items"][0]["id"] == str(feedback_id)
    assert body["data"]["items"][0]["status"] == "pending"
    assert body["data"]["items"][0]["submitter"] == {
        "id": "test-user-id-123",
        "email": "test@example.com",
    }
    query = collection.find.call_args.args[0]
    assert "$and" in query
    assert {"user_id": "test-user-id-123"} in query["$and"]


@pytest.mark.asyncio
async def test_update_feedback_status(async_client, auth_headers: dict):
    feedback_id = ObjectId()
    updated_doc = {
        **_feedback_doc(feedback_id),
        "status": "resolved",
        "resolution_note": "已补充知识库并复测",
        "updated_at": "2026-07-23T11:00:00+00:00",
    }
    collection = MagicMock()
    collection.update_one = AsyncMock(return_value=SimpleNamespace(matched_count=1))
    collection.find_one = AsyncMock(return_value=updated_doc)

    with patch("app.routers.diagnosis.get_collection", return_value=collection):
        response = await async_client.patch(
            f"/api/diagnosis/feedback/{feedback_id}",
            json={"status": "resolved", "resolution_note": "已补充知识库并复测"},
            headers=auth_headers,
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["status"] == "resolved"
    assert body["data"]["resolution_note"] == "已补充知识库并复测"
    update = collection.update_one.await_args.args[1]["$set"]
    assert update["status"] == "resolved"
    assert update["updated_by"] == "test-user-id-123"
    assert collection.update_one.await_args.args[0]["user_id"] == "test-user-id-123"


@pytest.mark.asyncio
async def test_update_missing_feedback_returns_business_error(
    async_client,
    auth_headers: dict,
):
    feedback_id = ObjectId()
    collection = MagicMock()
    collection.update_one = AsyncMock(return_value=SimpleNamespace(matched_count=0))

    with patch("app.routers.diagnosis.get_collection", return_value=collection):
        response = await async_client.patch(
            f"/api/diagnosis/feedback/{feedback_id}",
            json={"status": "processing"},
            headers=auth_headers,
        )

    assert response.status_code == 200
    assert response.json() == {
        "success": False,
        "data": None,
        "error": "反馈不存在",
        "message": None,
    }


@pytest.mark.asyncio
async def test_new_feedback_starts_as_pending(async_client, auth_headers: dict):
    feedback_id = ObjectId()
    collection = MagicMock()
    collection.insert_one = AsyncMock(
        return_value=SimpleNamespace(inserted_id=feedback_id)
    )

    with patch("app.routers.diagnosis.get_collection", return_value=collection):
        response = await async_client.post(
            "/api/diagnosis/feedback",
            json={
                "sn": "SN-FEEDBACK-02",
                "factory": "kunshan",
                "rating": "unsolved",
                "comment": "建议补充此故障案例",
            },
            headers=auth_headers,
        )

    assert response.status_code == 200
    assert response.json()["success"] is True
    inserted = collection.insert_one.await_args.args[0]
    assert inserted["status"] == "pending"
    assert inserted["resolution_note"] == ""
    assert inserted["submitter"] == {
        "id": "test-user-id-123",
        "email": "test@example.com",
    }


@pytest.mark.asyncio
async def test_link_feedback_knowledge_merges_documents_for_current_user(
    async_client,
    auth_headers: dict,
):
    feedback_id = ObjectId()
    updated_doc = {
        **_feedback_doc(feedback_id),
        "knowledge_document_ids": ["doc-existing", "doc-new"],
        "knowledge_title": "风扇故障处理案例",
        "knowledge_uploaded_at": "2026-07-23T12:00:00+00:00",
    }
    collection = MagicMock()
    collection.update_one = AsyncMock(return_value=SimpleNamespace(matched_count=1))
    collection.find_one = AsyncMock(return_value=updated_doc)

    with patch("app.routers.diagnosis.get_collection", return_value=collection):
        response = await async_client.post(
            f"/api/diagnosis/feedback/{feedback_id}/knowledge",
            json={
                "document_ids": [" doc-existing ", "doc-new", "doc-new"],
                "knowledge_title": " 风扇故障处理案例 ",
            },
            headers=auth_headers,
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["knowledge_document_ids"] == ["doc-existing", "doc-new"]
    query, update = collection.update_one.await_args.args
    assert query == {"_id": feedback_id, "user_id": "test-user-id-123"}
    assert update["$addToSet"] == {
        "knowledge_document_ids": {"$each": ["doc-existing", "doc-new"]}
    }
    assert update["$set"]["knowledge_title"] == "风扇故障处理案例"
    assert update["$set"]["updated_by"] == "test-user-id-123"
    assert collection.find_one.await_args.args[0] == query


@pytest.mark.asyncio
async def test_link_feedback_knowledge_missing_or_other_user_returns_business_error(
    async_client,
    auth_headers: dict,
):
    feedback_id = ObjectId()
    collection = MagicMock()
    collection.update_one = AsyncMock(return_value=SimpleNamespace(matched_count=0))

    with patch("app.routers.diagnosis.get_collection", return_value=collection):
        response = await async_client.post(
            f"/api/diagnosis/feedback/{feedback_id}/knowledge",
            json={"document_ids": ["doc-1"], "knowledge_title": "反馈案例"},
            headers=auth_headers,
        )

    assert response.status_code == 200
    assert response.json() == {
        "success": False,
        "data": None,
        "error": "反馈不存在",
        "message": None,
    }
    assert collection.update_one.await_args.args[0]["user_id"] == "test-user-id-123"
    collection.find_one.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"document_ids": [], "knowledge_title": "反馈案例"},
        {"document_ids": ["   "], "knowledge_title": "反馈案例"},
        {"document_ids": [f"doc-{index}" for index in range(21)], "knowledge_title": "反馈案例"},
        {"document_ids": ["doc-1"], "knowledge_title": "   "},
    ],
)
async def test_link_feedback_knowledge_rejects_invalid_payload(
    async_client,
    auth_headers: dict,
    payload: dict,
):
    response = await async_client.post(
        f"/api/diagnosis/feedback/{ObjectId()}/knowledge",
        json=payload,
        headers=auth_headers,
    )

    assert response.status_code == 422
