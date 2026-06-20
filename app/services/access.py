from sqlalchemy.orm import Session

from app.models import AccessMode, StreamAccessToken, Tournament, TournamentStream
from app.security import generate_token, hash_password, token_expires, utcnow, verify_password


def has_tournament_session_access(session: dict, tournament: Tournament) -> bool:
    return bool(session.get(f"tournament_access_{tournament.id}"))


def grant_tournament_session_access(session: dict, tournament: Tournament) -> None:
    session[f"tournament_access_{tournament.id}"] = True


def can_view_tournament(session: dict, tournament: Tournament) -> bool:
    if not tournament.is_public:
        return False
    if tournament.access_mode in {AccessMode.public, AccessMode.token}:
        return True
    return has_tournament_session_access(session, tournament)


def check_tournament_password(tournament: Tournament, password: str) -> bool:
    return verify_password(password, tournament.password_hash)


def set_tournament_password(tournament: Tournament, password: str | None) -> None:
    if password:
        tournament.password_hash = hash_password(password)


def create_stream_token(db: Session, tournament: Tournament, stream: TournamentStream | None = None) -> StreamAccessToken:
    token = StreamAccessToken(
        tournament_id=tournament.id,
        tournament_stream_id=stream.id if stream else None,
        token=generate_token(24),
        expires_at=token_expires(),
        max_views=None,
        current_views=0,
        is_active=True,
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    return token


def consume_token(db: Session, token_value: str, stream_id: int | None = None) -> StreamAccessToken | None:
    token = db.query(StreamAccessToken).filter(StreamAccessToken.token == token_value).first()
    if not token or not token.is_active or token.expires_at < utcnow():
        return None
    if stream_id and token.tournament_stream_id and token.tournament_stream_id != stream_id:
        return None
    if token.max_views is not None and token.current_views >= token.max_views:
        return None
    token.current_views += 1
    db.commit()
    return token
