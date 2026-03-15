from fastapi import Depends, APIRouter

from src.auth.models import User
from src.auth.schemas import UserCreate, UserRead, UserUpdate
from src.auth.users import auth_backend, current_active_user, fastapi_users


users_router = APIRouter()


users_router.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/jwt",
    tags=["auth"]
)
users_router.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    tags=["auth"],
)
users_router.include_router(
    fastapi_users.get_reset_password_router(),
    tags=["auth"],
)
users_router.include_router(
    fastapi_users.get_verify_router(UserRead),
    tags=["auth"],
)
users_router.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    tags=["users"],
)


@users_router.get("/authenticated-route")
async def authenticated_route(user: User = Depends(current_active_user)):
    return {"message": f"Hello {user.email}!"}
