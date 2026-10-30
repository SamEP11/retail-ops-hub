"""Comandos de administración.

python -m app.cli create-admin --email admin@retailops.dev --name "Admin"
python -m app.cli seed      # usuarios demo, uno por rol (solo entorno local)
"""

import argparse
import getpass
import sys

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.permissions import Role
from app.schemas.user import UserCreate
from app.services import users

DEMO_PASSWORD = "Demo12345!"  # solo para entorno local; documentado en el README
DEMO_USERS = [
    ("admin@retailops.dev", "Ana Admin", Role.ADMIN),
    ("comercial@retailops.dev", "Carlos Comercial", Role.COMERCIAL),
    ("bodega@retailops.dev", "Beatriz Bodega", Role.BODEGA),
    ("analista@retailops.dev", "Andrés Analista", Role.ANALISTA),
]


def create_admin(email: str, name: str) -> None:
    password = getpass.getpass("Contraseña (mín. 10 caracteres): ")
    with SessionLocal() as db:
        user = users.create(
            db,
            UserCreate(email=email, full_name=name, password=password, role=Role.ADMIN),
            actor_id=None,
            ip=None,
        )
    print(f"Admin creado: id={user.id} {user.email}")


def seed() -> None:
    if get_settings().environment not in {"local", "test"}:
        sys.exit("seed solo corre en entorno local")
    with SessionLocal() as db:
        for email, name, role in DEMO_USERS:
            if users.get_by_email(db, email):
                print(f"ya existe: {email}")
                continue
            users.create(
                db,
                UserCreate(email=email, full_name=name, password=DEMO_PASSWORD, role=role),
                actor_id=None,
                ip=None,
            )
            print(f"creado: {email} ({role.value})")


def main() -> None:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    admin = sub.add_parser("create-admin")
    admin.add_argument("--email", required=True)
    admin.add_argument("--name", required=True)
    sub.add_parser("seed")
    args = parser.parse_args()

    if args.cmd == "create-admin":
        create_admin(args.email, args.name)
    else:
        seed()


if __name__ == "__main__":
    main()
