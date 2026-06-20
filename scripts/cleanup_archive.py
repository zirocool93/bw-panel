from app.database import SessionLocal
from app.services.archive import cleanup_old_archive


def main() -> None:
    with SessionLocal() as db:
        removed = cleanup_old_archive(db)
    print(f"Обработано устаревших архивных записей: {removed}")


if __name__ == "__main__":
    main()
