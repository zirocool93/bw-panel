from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AccessMode, Tournament, TournamentStream
from app.services.access import can_view_tournament, create_stream_token
from app.services.ome import OmeService

router = APIRouter(prefix="/api", tags=["api"])


def serialize_tournament(t: Tournament) -> dict:
    return {"id": t.id, "title": t.title, "slug": t.slug, "status": t.status.value, "date_start": t.date_start}


@router.get("/tournaments")
def tournaments(db: Session = Depends(get_db)):
    return [serialize_tournament(t) for t in db.scalars(select(Tournament).where(Tournament.is_public.is_(True))).all()]


@router.get("/tournaments/{slug}")
def tournament(slug: str, db: Session = Depends(get_db)):
    item = db.scalar(select(Tournament).where(Tournament.slug == slug, Tournament.is_public.is_(True)))
    if not item:
        raise HTTPException(status_code=404)
    return serialize_tournament(item)


@router.get("/tournaments/{slug}/streams")
def streams(slug: str, db: Session = Depends(get_db)):
    tournament = db.scalar(select(Tournament).where(Tournament.slug == slug, Tournament.is_public.is_(True)))
    if not tournament:
        raise HTTPException(status_code=404)
    return [
        {"id": s.id, "title": s.title, "is_main": s.is_main, "is_active": s.is_active}
        for s in tournament.streams
        if s.is_active
    ]


@router.post("/tournaments/{slug}/check-password")
def check_password_redirect(slug: str):
    return {"detail": "Используйте HTML-форму /tournaments/{slug}/password для сессионного доступа"}


@router.get("/streams/{stream_id}/playback-url")
def playback_url(stream_id: int, request: Request, db: Session = Depends(get_db)):
    stream = db.get(TournamentStream, stream_id)
    if not stream or not stream.is_active:
        raise HTTPException(status_code=404, detail="Трансляция недоступна")
    tournament = stream.tournament
    if not can_view_tournament(request.session, tournament):
        raise HTTPException(status_code=403, detail="Нет доступа к турниру")
    if tournament.access_mode == AccessMode.token or stream.token_required:
        token = create_stream_token(db, tournament, stream)
        return {"playback_url": stream.playback_url or OmeService().playback_url(stream.ome_app_name, stream.ome_stream_name or "", stream.playback_type.value), "token": token.token, "expires_at": token.expires_at}
    return {"playback_url": stream.playback_url or OmeService().playback_url(stream.ome_app_name, stream.ome_stream_name or "", stream.playback_type.value)}
