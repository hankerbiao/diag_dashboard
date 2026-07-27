"""Administrator access rules for diagnosis history."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId


def _history_collection(doc: dict):
    collection = MagicMock()
    collection.count_documents = AsyncMock(return_value=1)
    cursor = MagicMock()
    collection.find.return_value = cursor
    cursor.sort.return_value = cursor
    cursor.skip.return_value = cursor
    cursor.limit.return_value = cursor
    cursor.to_list = AsyncMock(return_value=[doc])
    collection.find_one = AsyncMock(return_value=doc)
    return collection


@pytest.fixture
def history_doc() -> dict:
    return {
        "_id": ObjectId(),
        "user_id": "another-user-id",
        "user_itcode": "zhangsan",
        "user_name": "张三",
        "sn": "SN-ADMIN-001",
        "factory": "kunshan",
        "category": "内存故障",
        "confidence": 0.91,
        "summary": "诊断摘要",
        "diagnosis_result": {"category": "内存故障"},
        "chat_messages": [],
        "created_at": "2026-07-27T08:00:00+00:00",
        "updated_at": "2026-07-27T08:00:00+00:00",
    }


@pytest.mark.asyncio
async def test_regular_user_history_list_remains_user_scoped(
    async_client, auth_headers, history_doc
):
    collection = _history_collection(history_doc)
    with patch("app.routers.diagnosis.get_collection", return_value=collection):
        response = await async_client.get(
            "/api/diagnosis/sn/history",
            params={"factory": "kunshan"},
            headers=auth_headers,
        )

    assert response.status_code == 200
    collection.count_documents.assert_awaited_once_with(
        {"user_id": "test-user-id-123", "factory": "kunshan"}
    )


@pytest.mark.asyncio
async def test_admin_history_list_includes_all_users(
    async_client, admin_auth_headers, history_doc
):
    collection = _history_collection(history_doc)
    with patch("app.routers.diagnosis.get_collection", return_value=collection):
        response = await async_client.get(
            "/api/diagnosis/sn/history",
            params={"factory": "kunshan"},
            headers=admin_auth_headers,
        )

    assert response.status_code == 200
    collection.count_documents.assert_awaited_once_with({"factory": "kunshan"})
    item = response.json()["data"]["items"][0]
    assert item["user_itcode"] == "zhangsan"
    assert item["user_name"] == "张三"


@pytest.mark.asyncio
async def test_regular_user_history_detail_remains_user_scoped(
    async_client, auth_headers, history_doc
):
    collection = _history_collection(history_doc)
    with patch("app.routers.diagnosis.get_collection", return_value=collection):
        response = await async_client.get(
            f"/api/diagnosis/sn/history/{history_doc['_id']}",
            headers=auth_headers,
        )

    assert response.status_code == 200
    query = collection.find_one.await_args.args[0]
    assert query == {
        "_id": history_doc["_id"],
        "user_id": "test-user-id-123",
    }


@pytest.mark.asyncio
async def test_admin_history_detail_can_read_another_users_record(
    async_client, admin_auth_headers, history_doc
):
    collection = _history_collection(history_doc)
    with patch("app.routers.diagnosis.get_collection", return_value=collection):
        response = await async_client.get(
            f"/api/diagnosis/sn/history/{history_doc['_id']}",
            headers=admin_auth_headers,
        )

    assert response.status_code == 200
    query = collection.find_one.await_args.args[0]
    assert query == {"_id": history_doc["_id"]}
    assert response.json()["data"]["user_itcode"] == "zhangsan"
