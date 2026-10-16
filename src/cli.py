"""Comandos de administración: python -m src.cli <comando>."""
import argparse
import getpass
import sys

from alembic import command
from alembic.config import Config

from src.config.settings import get_settings
from src.db.session import create_db_engine, create_session_factory
from src.services.auth import AuthError, AuthService


def _migrate(_args) -> None:
    command.upgrade(Config("alembic.ini"), "head")
    print("Migraciones aplicadas.")


def _create_user(args) -> None:
    password = args.password or getpass.getpass("Contraseña: ")
    auth = AuthService(create_session_factory(create_db_engine(get_settings().database_url)))
    try:
        user = auth.create_user(args.username, password, args.role)
    except AuthError as exc:
        sys.exit(f"Error: {exc}")
    print(f"Usuario '{user.username}' creado con rol {user.role}.")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m src.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("migrate", help="Aplica las migraciones de la base de datos").set_defaults(func=_migrate)
    cu = sub.add_parser("create-user", help="Crea un usuario")
    cu.add_argument("username")
    cu.add_argument("--role", choices=["admin", "user"], default="user")
    cu.add_argument("--password", help="Si se omite, se pide por teclado")
    cu.set_defaults(func=_create_user)
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
