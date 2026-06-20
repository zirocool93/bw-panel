from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import AccessMode, Tournament, TournamentStatus, TournamentStream
from app.services.access import can_view_tournament, check_tournament_password, grant_tournament_session_access

router = APIRouter(tags=["public"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    active = db.scalars(
        select(Tournament)
        .where(Tournament.is_public.is_(True), Tournament.status == TournamentStatus.active)
        .order_by(Tournament.date_start)
    ).all()
    upcoming = db.scalars(
        select(Tournament)
        .where(Tournament.is_public.is_(True), Tournament.status == TournamentStatus.draft, Tournament.show_on_homepage.is_(True))
        .order_by(Tournament.date_start)
        .limit(6)
    ).all()
    return templates.TemplateResponse("public/home.html", {"request": request, "active": active, "upcoming": upcoming})


@router.get("/tournaments", response_class=HTMLResponse)
def tournaments(request: Request, db: Session = Depends(get_db)):
    items = db.scalars(
        select(Tournament)
        .where(Tournament.is_public.is_(True))
        .order_by(Tournament.date_start.desc().nullslast(), Tournament.created_at.desc())
    ).all()
    return templates.TemplateResponse("public/tournaments.html", {"request": request, "tournaments": items})


@router.get("/tournaments/{slug}", response_class=HTMLResponse)
def tournament_page(slug: str, request: Request, db: Session = Depends(get_db)):
    tournament = db.scalar(
        select(Tournament).options(selectinload(Tournament.streams)).where(Tournament.slug == slug)
    )
    if not tournament or not tournament.is_public:
        return templates.TemplateResponse("public/not_found.html", {"request": request}, status_code=404)
    password_error = request.query_params.get("password_error")
    allowed = can_view_tournament(request.session, tournament)
    main_stream = next((stream for stream in tournament.streams if stream.is_main and stream.is_active), None)
    if not main_stream:
        main_stream = next((stream for stream in tournament.streams if stream.is_active), None)
    return templates.TemplateResponse(
        "public/tournament_detail.html",
        {
            "request": request,
            "tournament": tournament,
            "streams": tournament.streams,
            "main_stream": main_stream,
            "allowed": allowed,
            "password_error": password_error,
        },
    )


@router.post("/tournaments/{slug}/password")
def tournament_password(slug: str, request: Request, password: str = Form(...), db: Session = Depends(get_db)):
    tournament = db.scalar(select(Tournament).where(Tournament.slug == slug))
    if not tournament or tournament.access_mode != AccessMode.password:
        return RedirectResponse(f"/tournaments/{slug}", status_code=303)
    if check_tournament_password(tournament, password):
        grant_tournament_session_access(request.session, tournament)
        return RedirectResponse(f"/tournaments/{slug}", status_code=303)
    return RedirectResponse(f"/tournaments/{slug}?password_error=1", status_code=303)


@router.get("/tournaments/{slug}/streams/{stream_id}", response_class=HTMLResponse)
def stream_page(slug: str, stream_id: int, request: Request, db: Session = Depends(get_db)):
    tournament = db.scalar(select(Tournament).where(Tournament.slug == slug))
    stream = db.get(TournamentStream, stream_id)
    if not tournament or not stream or stream.tournament_id != tournament.id:
        return templates.TemplateResponse("public/not_found.html", {"request": request}, status_code=404)
    allowed = can_view_tournament(request.session, tournament)
    return templates.TemplateResponse(
        "public/stream_detail.html",
        {"request": request, "tournament": tournament, "stream": stream, "allowed": allowed},
    )
