import asyncio

from app.database import SessionLocal
from app.models import TournamentStream
from app.services.ome import OmeService


async def main() -> None:
    service = OmeService()
    with SessionLocal() as db:
        for stream in db.query(TournamentStream).filter(TournamentStream.is_active.is_(True)).all():
            ok, status = await service.check_stream(stream.playback_url)
            print(f"{stream.id}: {stream.title}: {'OK' if ok else 'FAIL'} {status}")


if __name__ == "__main__":
    asyncio.run(main())
