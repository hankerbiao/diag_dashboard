"""OA 单点登录路由。"""
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError, jwt
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from ..core.auth import create_access_token, get_current_user
from ..core.config import get_settings
from ..core.mongodb import get_collection
from ..core.utils import utc_now_iso
from ..models.auth import OACallbackRequest, OACallbackResponse, OAUserResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["认证"])


def _profile_value(profile: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = profile.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _serialize_user(user: dict[str, Any]) -> OAUserResponse:
    profile = user.get("profile") or {}
    itcode = str(user.get("itcode") or _profile_value(profile, "itcode") or "")
    name = str(
        user.get("name")
        or _profile_value(profile, "姓名", "name", "displayName")
        or itcode
    )
    email = user.get("email") or _profile_value(profile, "email", "邮箱")
    return OAUserResponse(
        id=str(user.get("_id") or user.get("id") or ""),
        itcode=itcode,
        name=name,
        email=str(email) if email else None,
        profile=profile,
    )


def _find_user_filter(user_data: dict[str, Any]) -> dict[str, Any]:
    user_id = user_data.get("id")
    if user_id:
        try:
            return {"_id": ObjectId(user_id)}
        except Exception:
            pass
    if user_data.get("itcode"):
        return {"itcode": user_data["itcode"]}
    return {"_id": user_id}


async def _persist_oa_user(
    collection: Any,
    *,
    itcode: str,
    email: str | None,
    update: dict[str, Any],
) -> dict[str, Any] | None:
    user = await collection.find_one_and_update(
        {"itcode": itcode},
        update,
        return_document=ReturnDocument.AFTER,
    )
    if user:
        return user

    # Preserve user-scoped data created before the OA migration by linking a
    # verified OA email to a legacy account that does not yet have an itcode.
    if email:
        user = await collection.find_one_and_update(
            {
                "email": email,
                "$or": [
                    {"itcode": {"$exists": False}},
                    {"itcode": None},
                ],
            },
            update,
            return_document=ReturnDocument.AFTER,
        )
        if user:
            return user

    try:
        return await collection.find_one_and_update(
            {"itcode": itcode},
            update,
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
    except DuplicateKeyError:
        # Concurrent callbacks for the same OA user can race on the first insert.
        return await collection.find_one({"itcode": itcode})


async def _consume_oa_assertion(payload_token: str, profile: dict[str, Any]) -> None:
    try:
        expires_at = datetime.fromtimestamp(float(profile["exp"]), tz=timezone.utc)
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OA payload expiry",
        ) from exc

    assertion_hash = sha256(payload_token.encode("utf-8")).hexdigest()
    collection = get_collection("oa_login_assertions")
    try:
        await collection.insert_one(
            {
                "_id": assertion_hash,
                "expires_at": expires_at,
                "consumed_at": datetime.now(timezone.utc),
            }
        )
    except DuplicateKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OA payload has already been used",
        ) from exc


@router.post("/oa/callback", response_model=OACallbackResponse)
async def oa_login_callback(request: OACallbackRequest):
    """验证 OA 回调 payload，并签发应用 Bearer JWT。"""
    if request.status != "success":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OA login failed")

    settings = get_settings()
    if not settings.oa_jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OA JWT secret not configured",
        )

    try:
        profile = jwt.decode(
            request.payload,
            settings.oa_jwt_secret,
            algorithms=["HS256"],
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OA payload",
        ) from exc

    if not isinstance(profile, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OA payload")
    if profile.get("exp") is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token missing exp")

    itcode = _profile_value(profile, "itcode")
    if not itcode:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token missing itcode")

    await _consume_oa_assertion(request.payload, profile)

    name = _profile_value(profile, "姓名", "name", "displayName") or itcode
    email = _profile_value(profile, "email", "邮箱")
    if email:
        email = email.lower()
    now = utc_now_iso()
    collection = get_collection("users")
    update = {
        "$set": {
            "itcode": itcode,
            "name": name,
            "email": email,
            "profile": profile,
            "updated_at": now,
            "last_login_at": now,
        },
        "$setOnInsert": {"created_at": now},
    }
    user = await _persist_oa_user(
        collection,
        itcode=itcode,
        email=email,
        update=update,
    )
    if not user:
        raise HTTPException(status_code=500, detail="Failed to persist OA user")

    user_response = _serialize_user(user)
    access_token = create_access_token(
        user_response.id,
        user_response.email,
        itcode=user_response.itcode,
        name=user_response.name,
    )
    return OACallbackResponse(
        access_token=access_token,
        user=user_response,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    """获取当前 OA 用户信息。"""
    collection = get_collection("users")
    user = await collection.find_one(_find_user_filter(current_user))
    if user:
        return _serialize_user(user)
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User no longer exists")
