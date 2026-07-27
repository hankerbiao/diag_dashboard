"""User analytics route tests."""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def overview_data() -> dict:
    return {
        "summary": {
            "total_users": 18,
            "new_users": 4,
            "active_users": 11,
            "today_active_users": 3,
            "total_usage": 72,
            "avg_usage_per_active_user": 6.5,
            "changes": {
                "new_users": 33.3,
                "active_users": 10.0,
                "total_usage": 20.0,
            },
        },
        "daily": [
            {
                "date": "2026-07-27",
                "new_users": 1,
                "active_users": 3,
                "usage_count": 8,
            }
        ],
        "features": [{"feature": "diagnosis", "count": 42}],
        "users": {"items": [], "total": 18, "page": 1, "limit": 10},
        "generated_at": "2026-07-27T08:00:00+00:00",
    }


@pytest.mark.asyncio
async def test_overview_requires_authentication(async_client):
    response = await async_client.get("/api/user-analytics/overview")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_overview_returns_service_data(async_client, auth_headers, overview_data):
    service = AsyncMock()
    service.get_overview.return_value = overview_data

    with patch(
        "app.routers.user_analytics.get_user_analytics_service",
        return_value=service,
    ):
        response = await async_client.get(
            "/api/user-analytics/overview",
            params={"days": 30, "page": 1, "limit": 10, "search": "zhang"},
            headers=auth_headers,
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["summary"]["total_users"] == 18
    service.get_overview.assert_awaited_once_with(
        days=30,
        page=1,
        limit=10,
        search="zhang",
    )


@pytest.mark.asyncio
async def test_overview_validates_date_range(async_client, auth_headers):
    response = await async_client.get(
        "/api/user-analytics/overview",
        params={"days": 365},
        headers=auth_headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_track_feature_records_authenticated_user(async_client, auth_headers):
    service = AsyncMock()
    with patch(
        "app.routers.user_analytics.get_user_analytics_service",
        return_value=service,
    ):
        response = await async_client.post(
            "/api/user-analytics/events",
            json={"feature": "user_analytics"},
            headers=auth_headers,
        )

    assert response.status_code == 200
    assert response.json()["data"] == {"recorded": True}
    tracked_user, tracked_feature = service.track_event.await_args.args
    assert tracked_user["id"] == "test-user-id-123"
    assert tracked_feature == "user_analytics"


@pytest.mark.asyncio
async def test_track_feature_rejects_unknown_feature(async_client, auth_headers):
    response = await async_client.post(
        "/api/user-analytics/events",
        json={"feature": "not-a-feature"},
        headers=auth_headers,
    )
    assert response.status_code == 422
