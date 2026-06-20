import os

from sqlalchemy import select

from app.database import SessionLocal
from app.models import User, UserRole
from app.security import hash_password


def main() -> None:
    username = os.getenv("ADMIN_USERNAME", "admin")
    email = os.getenv("ADMIN_EMAIL", "admin@example.com")
    password = os.getenv("ADMIN_PASSWORD", "admin12345")
    with SessionLocal() as db:
        exists = db.scalar(select(User).limit(1))
        if exists:
            print("Пользователь уже существует, создание администратора пропущено.")
            return
        user = User(username=username, email=email, password_hash=hash_password(password), role=UserRole.admin, is_active=True)
        db.add(user)
        db.commit()
        print(f"Создан администратор: {username}")


if __name__ == "__main__":
    main()
