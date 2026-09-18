import argparse
import os
import sys

from sqlalchemy import select

from app.database import SessionLocal
from app.models import User
from app.services.security import hash_password


def seed_admin():
    email = os.getenv("ADMIN_EMAIL", "").lower().strip()
    password = os.getenv("ADMIN_PASSWORD", "")
    if not email or not password or password.startswith("change-"):
        raise SystemExit("Configure ADMIN_EMAIL e ADMIN_PASSWORD no .env antes de criar o administrador.")
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        if user:
            print(f"Administrador {email} já existe; senha preservada.")
            return
        db.add(User(name=os.getenv("ADMIN_NAME", "Administrador"), email=email, password_hash=hash_password(password)))
        db.commit()
        print(f"Administrador {email} criado.")


def reset_admin_password():
    email = os.getenv("ADMIN_EMAIL", "").lower().strip()
    password = os.getenv("ADMIN_PASSWORD", "")
    if not email or not password or password.startswith("change-"):
        raise SystemExit("Configure ADMIN_EMAIL e uma nova ADMIN_PASSWORD antes de trocar a senha.")
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            raise SystemExit(f"Administrador {email} não encontrado.")
        user.password_hash = hash_password(password)
        db.commit()
        print(f"Senha do administrador {email} atualizada.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["seed-admin", "reset-admin-password"])
    args = parser.parse_args()
    if args.command == "seed-admin":
        seed_admin()
    elif args.command == "reset-admin-password":
        reset_admin_password()
