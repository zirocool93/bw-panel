from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import ArchiveRecording, Tournament


def cleanup_old_archive(db: Session) -> int:
    removed = 0
    tournaments = db.query(Tournament).filter(Tournament.archive_enabled.is_(True)).all()
    for tournament in tournaments:
        cutoff = datetime.now(UTC) - timedelta(days=tournament.archive_depth_days)
        records = (
            db.query(ArchiveRecording)
            .filter(ArchiveRecording.tournament_id == tournament.id, ArchiveRecording.created_at < cutoff)
            .all()
        )
        for record in records:
            path = Path(record.file_path)
            if path.exists() and path.is_file():
                path.unlink()
            record.status = "deleted"
            removed += 1
    db.commit()
    return removed
