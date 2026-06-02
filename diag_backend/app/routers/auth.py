"""
认证 API - 注册/登录
"""
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status

from ..core.utils import utc_now_iso
from ..models.auth import LoginRequest, RegisterRequest, AuthResponse, UserResponse
from ..core.auth import hash_password, verify_password, create_access_token, get_current_user
from ..core.mongodb import get_collection

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/register", response_model=AuthResponse)
async def register(request: RegisterRequest):
    """用户注册"""
    col = get_collection("users")

    # 检查邮箱是否已存在
    existing = await col.find_one({"email": request.email})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # 创建用户
    user_doc = {
        "email": request.email,
        "password_hash": hash_password(request.password),
        "created_at": utc_now_iso(),
    }
    result = await col.insert_one(user_doc)

    # 生成 token
    user_id = str(result.inserted_id)
    access_token = create_access_token(user_id, request.email)

    return AuthResponse(
        access_token=access_token,
        user_id=user_id,
        email=request.email
    )


@router.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest):
    """用户登录"""
    col = get_collection("users")

    # 查找用户
    user = await col.find_one({"email": request.email})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # 验证密码
    if not verify_password(request.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # 生成 token
    user_id = str(user["_id"])

    # 如果选择记住我，token 有效期设为 1 天
    if request.remember:
        expires_delta = timedelta(days=1)
    else:
        expires_delta = None  # 使用默认配置

    access_token = create_access_token(user_id, request.email, expires_delta)

    return AuthResponse(
        access_token=access_token,
        user_id=user_id,
        email=request.email
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    """获取当前用户信息"""
    return UserResponse(
        id=current_user["id"],
        email=current_user["email"]
    )