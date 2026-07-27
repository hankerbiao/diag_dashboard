"""OA 认证路由测试。"""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from bson import ObjectId
from jose import jwt
from pymongo.errors import DuplicateKeyError

from app.core.config import Settings


@pytest.fixture
def oa_settings() -> Settings:
    return Settings(
        mongodb_uri="mongodb://localhost:27017",
        mongodb_db_name="test_diag_analysis",
        jwt_secret_key="application-jwt-secret-for-tests",
        jwt_algorithm="HS256",
        access_token_expire_minutes=60,
        oa_jwt_secret="oa-jwt-secret-for-tests",
    )


def make_oa_payload(settings: Settings, **overrides) -> tuple[str, dict]:
    profile = {
        "itcode": "zhangsan",
        "姓名": "张三",
        "email": "zhangsan@example.com",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
    }
    profile.update(overrides)
    return jwt.encode(profile, settings.oa_jwt_secret, algorithm="HS256"), profile


@pytest.mark.asyncio
async def test_oa_callback_upserts_user_and_returns_application_jwt(async_client, oa_settings):
    token, profile = make_oa_payload(oa_settings)
    user_id = ObjectId()
    collection = AsyncMock()
    persisted_user = {
        "_id": user_id,
        "itcode": "zhangsan",
        "name": "张三",
        "email": "zhangsan@example.com",
        "profile": profile,
    }
    collection.find_one_and_update.side_effect = [None, None, persisted_user]

    with (
        patch("app.routers.auth.get_settings", return_value=oa_settings),
        patch("app.core.auth.settings", oa_settings),
        patch("app.routers.auth.get_collection", return_value=collection),
    ):
        response = await async_client.post(
            "/api/auth/oa/callback",
            json={"status": "success", "payload": token, "next": "http://test/"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["token_type"] == "bearer"
    assert data["user"] == {
        "id": str(user_id),
        "itcode": "zhangsan",
        "name": "张三",
        "email": "zhangsan@example.com",
        "profile": data["user"]["profile"],
        "is_admin": False,
    }
    app_claims = jwt.decode(
        data["access_token"],
        oa_settings.jwt_secret_key,
        algorithms=[oa_settings.jwt_algorithm],
    )
    assert app_claims["sub"] == str(user_id)
    assert app_claims["itcode"] == "zhangsan"
    assert app_claims["name"] == "张三"
    assert collection.find_one_and_update.await_count == 3
    assert collection.find_one_and_update.await_args.kwargs["upsert"] is True
    update = collection.find_one_and_update.await_args.args[1]
    assert update["$set"]["profile"]["itcode"] == "zhangsan"
    assert "last_login_at" in update["$set"]


@pytest.mark.asyncio
async def test_oa_callback_reuses_itcode_on_repeated_login(async_client, oa_settings):
    token, profile = make_oa_payload(oa_settings, jti="login-1")
    second_token, second_profile = make_oa_payload(oa_settings, jti="login-2")
    collection = AsyncMock()
    collection.find_one_and_update.side_effect = [{
        "_id": ObjectId(),
        "itcode": "zhangsan",
        "name": "张三",
        "profile": profile,
    }, {
        "_id": ObjectId(),
        "itcode": "zhangsan",
        "name": "张三",
        "profile": second_profile,
    }]

    with (
        patch("app.routers.auth.get_settings", return_value=oa_settings),
        patch("app.core.auth.settings", oa_settings),
        patch("app.routers.auth.get_collection", return_value=collection),
    ):
        for current_token in (token, second_token):
            response = await async_client.post(
                "/api/auth/oa/callback",
                json={"status": "success", "payload": current_token},
            )
            assert response.status_code == 200

    assert collection.find_one_and_update.await_count == 2
    assert collection.find_one_and_update.await_args.args[0] == {"itcode": "zhangsan"}


@pytest.mark.asyncio
async def test_oa_callback_rejects_replayed_payload(async_client, oa_settings):
    token, _ = make_oa_payload(oa_settings, jti="replayed")
    collection = AsyncMock()
    collection.insert_one.side_effect = DuplicateKeyError("already consumed")

    with (
        patch("app.routers.auth.get_settings", return_value=oa_settings),
        patch("app.routers.auth.get_collection", return_value=collection),
    ):
        response = await async_client.post(
            "/api/auth/oa/callback",
            json={"status": "success", "payload": token},
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "OA payload has already been used"


@pytest.mark.asyncio
async def test_oa_callback_links_legacy_user_by_verified_email(async_client, oa_settings):
    token, profile = make_oa_payload(oa_settings)
    legacy_user_id = ObjectId()
    linked_user = {
        "_id": legacy_user_id,
        "itcode": "zhangsan",
        "name": "张三",
        "email": "zhangsan@example.com",
        "profile": profile,
    }
    collection = AsyncMock()
    collection.find_one_and_update.side_effect = [None, linked_user]

    with (
        patch("app.routers.auth.get_settings", return_value=oa_settings),
        patch("app.core.auth.settings", oa_settings),
        patch("app.routers.auth.get_collection", return_value=collection),
    ):
        response = await async_client.post(
            "/api/auth/oa/callback",
            json={"status": "success", "payload": token},
        )

    assert response.status_code == 200
    assert response.json()["user"]["id"] == str(legacy_user_id)
    legacy_filter = collection.find_one_and_update.await_args_list[1].args[0]
    assert legacy_filter["email"] == "zhangsan@example.com"
    assert legacy_filter["$or"] == [
        {"itcode": {"$exists": False}},
        {"itcode": None},
    ]


@pytest.mark.asyncio
async def test_oa_callback_rejects_non_success_status(async_client):
    response = await async_client.post(
        "/api/auth/oa/callback",
        json={"status": "failed", "payload": "ignored"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_oa_callback_requires_configured_secret(async_client, oa_settings):
    token, _ = make_oa_payload(oa_settings)
    settings_without_secret = oa_settings.model_copy(update={"oa_jwt_secret": ""})
    with patch("app.routers.auth.get_settings", return_value=settings_without_secret):
        response = await async_client.post(
            "/api/auth/oa/callback",
            json={"status": "success", "payload": token},
        )
    assert response.status_code == 500


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload_factory, expected_detail",
    [
        (lambda settings: "not-a-jwt", "Invalid OA payload"),
        (
            lambda settings: jwt.encode(
                {"itcode": "zhangsan", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
                "wrong-secret",
                algorithm="HS256",
            ),
            "Invalid OA payload",
        ),
        (
            lambda settings: jwt.encode(
                {"itcode": "zhangsan", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
                settings.oa_jwt_secret,
                algorithm="HS256",
            ),
            "Invalid OA payload",
        ),
        (
            lambda settings: jwt.encode(
                {"itcode": "zhangsan"}, settings.oa_jwt_secret, algorithm="HS256"
            ),
            "Token missing exp",
        ),
        (
            lambda settings: jwt.encode(
                {"exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
                settings.oa_jwt_secret,
                algorithm="HS256",
            ),
            "Token missing itcode",
        ),
    ],
)
async def test_oa_callback_rejects_invalid_payloads(
    async_client, oa_settings, payload_factory, expected_detail
):
    with patch("app.routers.auth.get_settings", return_value=oa_settings):
        response = await async_client.post(
            "/api/auth/oa/callback",
            json={"status": "success", "payload": payload_factory(oa_settings)},
        )
    assert response.status_code == 400
    assert response.json()["detail"] == expected_detail


@pytest.mark.asyncio
async def test_get_me_returns_persisted_oa_profile(async_client, auth_headers):
    collection = AsyncMock()
    collection.find_one.return_value = {
        "_id": "test-user-id-123",
        "itcode": "test-user",
        "name": "测试用户",
        "email": "test@example.com",
        "profile": {"itcode": "test-user", "姓名": "测试用户"},
    }
    with patch("app.routers.auth.get_collection", return_value=collection):
        response = await async_client.get("/api/auth/me", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["itcode"] == "test-user"
    assert response.json()["name"] == "测试用户"


@pytest.mark.asyncio
async def test_get_me_requires_valid_bearer_token(async_client):
    assert (await async_client.get("/api/auth/me")).status_code == 401
    response = await async_client.get(
        "/api/auth/me", headers={"Authorization": "Bearer invalid-token"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me_rejects_deleted_user(async_client, auth_headers):
    collection = AsyncMock()
    collection.find_one.return_value = None
    with patch("app.routers.auth.get_collection", return_value=collection):
        response = await async_client.get("/api/auth/me", headers=auth_headers)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_password_login_and_registration_are_removed(async_client):
    login = await async_client.post("/api/auth/login", json={})
    register = await async_client.post("/api/auth/register", json={})
    assert login.status_code == 404
    assert register.status_code == 404
