from fastapi import Depends
from fastapi_users import BaseUserManager, FastAPIUsers, IntegerIDMixin
from fastapi_users.authentication import (
    AuthenticationBackend, BearerTransport, JWTStrategy
)

from config import SECRET
from database import get_user_db
from auth.models import User


bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=SECRET, lifetime_seconds=3600)


auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)


class UserManager(IntegerIDMixin, BaseUserManager[User, int]):
    reset_password_token_secret = SECRET
    verification_token_secret = SECRET

    async def on_after_register(self, user, request):
        print(f"User {user.id} has registered.")

    async def on_after_forgot_password(
        self, user, token, request
    ):
        print(f"""User {user.id} has forgot their password.
              Reset token: {token}""")

    async def on_after_request_verify(
        self, user, token, request
    ):
        print(f"""Verification requested for user {user.id}.
              Verification token: {token}""")


async def get_user_manager(user_db=Depends(get_user_db)):
    yield UserManager(user_db)

fastapi_users = FastAPIUsers[User, int](get_user_manager, [auth_backend])
current_active_user = fastapi_users.current_user(active=True)
current_user_optional = fastapi_users.current_user(active=True, optional=True)
