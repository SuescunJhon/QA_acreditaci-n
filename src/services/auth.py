import uuid
from dataclasses import dataclass

import bcrypt
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from src.db.models import USER_ROLES, User
from src.db.session import session_scope

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_BYTES = 72  # límite de bcrypt
_DUMMY_HASH = bcrypt.hashpw(b"dummy-password", bcrypt.gensalt()).decode()


class AuthError(ValueError):
    pass


@dataclass(frozen=True)
class UserView:
    id: uuid.UUID
    username: str
    role: str
    is_active: bool

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


def _view(user: User) -> UserView:
    return UserView(user.id, user.username, user.role, user.is_active)


def _validate_password(password: str) -> bytes:
    raw = password.encode("utf-8")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise AuthError(f"La contraseña debe tener al menos {MIN_PASSWORD_LENGTH} caracteres.")
    if len(raw) > MAX_PASSWORD_BYTES:
        raise AuthError(f"La contraseña no puede superar {MAX_PASSWORD_BYTES} bytes.")
    return raw


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_validate_password(password), bcrypt.gensalt()).decode()


def _check_password(password: str, password_hash: str) -> bool:
    raw = password.encode("utf-8")
    if len(raw) > MAX_PASSWORD_BYTES:
        return False
    try:
        return bcrypt.checkpw(raw, password_hash.encode())
    except ValueError:
        return False


class AuthService:
    def __init__(self, session_factory: sessionmaker[Session]):
        self.session_factory = session_factory

    def create_user(self, username: str, password: str, role: str = "user") -> UserView:
        username = username.strip().lower()
        if not username or len(username) > 64:
            raise AuthError("El nombre de usuario debe tener entre 1 y 64 caracteres.")
        if role not in USER_ROLES:
            raise AuthError(f"Rol inválido: {role}.")
        password_hash = hash_password(password)
        try:
            with session_scope(self.session_factory) as session:
                user = User(username=username, password_hash=password_hash, role=role)
                session.add(user)
                session.flush()
                return _view(user)
        except IntegrityError:
            raise AuthError(f"El usuario '{username}' ya existe.") from None

    def authenticate(self, username: str, password: str) -> UserView | None:
        with session_scope(self.session_factory) as session:
            user = session.scalar(select(User).where(User.username == username.strip().lower()))
            # se verifica siempre un hash para no revelar si el usuario existe
            valid = _check_password(password, user.password_hash if user else _DUMMY_HASH)
            if user is None or not valid or not user.is_active:
                return None
            return _view(user)

    def get(self, user_id: uuid.UUID) -> UserView | None:
        with session_scope(self.session_factory) as session:
            user = session.get(User, user_id)
            return _view(user) if user and user.is_active else None

    def list_users(self) -> list[UserView]:
        with session_scope(self.session_factory) as session:
            return [_view(u) for u in session.scalars(select(User).order_by(User.username))]

    def count_users(self) -> int:
        with session_scope(self.session_factory) as session:
            return session.scalar(select(func.count()).select_from(User)) or 0

    def set_active(self, user_id: uuid.UUID, active: bool) -> None:
        with session_scope(self.session_factory) as session:
            user = session.get(User, user_id)
            if user is None:
                raise AuthError("Usuario no encontrado.")
            if not active and user.role == "admin":
                admins = session.scalar(
                    select(func.count())
                    .select_from(User)
                    .where(User.role == "admin", User.is_active.is_(True))
                )
                if admins <= 1:
                    raise AuthError("No se puede desactivar al único administrador activo.")
            user.is_active = active

    def change_password(self, user_id: uuid.UUID, new_password: str) -> None:
        password_hash = hash_password(new_password)
        with session_scope(self.session_factory) as session:
            user = session.get(User, user_id)
            if user is None:
                raise AuthError("Usuario no encontrado.")
            user.password_hash = password_hash
