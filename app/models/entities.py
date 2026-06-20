import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserRole(str, enum.Enum):
    admin = "admin"
    operator = "operator"
    manager = "manager"


class TournamentStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    finished = "finished"
    archived = "archived"


class AccessMode(str, enum.Enum):
    public = "public"
    token = "token"
    password = "password"


class SourceType(str, enum.Enum):
    camera = "camera"
    obs = "obs"
    external = "external"


class PlaybackType(str, enum.Enum):
    hls = "hls"
    ll_hls = "ll_hls"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.operator)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Camera(Base, TimestampMixin):
    __tablename__ = "cameras"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(180))
    description: Mapped[str | None] = mapped_column(Text)
    camera_type: Mapped[str] = mapped_column(String(60), default="hikvision_rtsp")
    rtsp_url: Mapped[str] = mapped_column(Text)
    rtsp_username: Mapped[str | None] = mapped_column(String(120))
    rtsp_password: Mapped[str | None] = mapped_column(String(255))
    lane_from: Mapped[int | None] = mapped_column(Integer)
    lane_to: Mapped[int | None] = mapped_column(Integer)
    is_scoreboard_camera: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    ome_stream_name: Mapped[str | None] = mapped_column(String(180), unique=True)
    preview_url: Mapped[str | None] = mapped_column(Text)
    last_status: Mapped[str | None] = mapped_column(String(60), default="unknown")
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    streams: Mapped[list["TournamentStream"]] = relationship(back_populates="camera")


class ObsInput(Base, TimestampMixin):
    __tablename__ = "obs_inputs"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(180))
    description: Mapped[str | None] = mapped_column(Text)
    stream_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    ingest_protocol: Mapped[str] = mapped_column(String(30), default="rtmp")
    ingest_url: Mapped[str | None] = mapped_column(Text)
    ome_stream_name: Mapped[str | None] = mapped_column(String(180), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_status: Mapped[str | None] = mapped_column(String(60), default="unknown")
    last_connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    streams: Mapped[list["TournamentStream"]] = relationship(back_populates="obs_input")


class Tournament(Base, TimestampMixin):
    __tablename__ = "tournaments"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(220))
    slug: Mapped[str] = mapped_column(String(220), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    date_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    date_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[TournamentStatus] = mapped_column(Enum(TournamentStatus), default=TournamentStatus.draft)
    poster_image: Mapped[str | None] = mapped_column(Text)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    access_mode: Mapped[AccessMode] = mapped_column(Enum(AccessMode), default=AccessMode.public)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    archive_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    archive_depth_days: Mapped[int] = mapped_column(Integer, default=14)
    show_on_homepage: Mapped[bool] = mapped_column(Boolean, default=True)

    streams: Mapped[list["TournamentStream"]] = relationship(
        back_populates="tournament", cascade="all, delete-orphan", order_by="TournamentStream.sort_order"
    )
    tokens: Mapped[list["StreamAccessToken"]] = relationship(back_populates="tournament", cascade="all, delete-orphan")


class TournamentStream(Base, TimestampMixin):
    __tablename__ = "tournament_streams"

    id: Mapped[int] = mapped_column(primary_key=True)
    tournament_id: Mapped[int] = mapped_column(ForeignKey("tournaments.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(220))
    description: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[SourceType] = mapped_column(Enum(SourceType), default=SourceType.camera)
    camera_id: Mapped[int | None] = mapped_column(ForeignKey("cameras.id", ondelete="SET NULL"))
    obs_input_id: Mapped[int | None] = mapped_column(ForeignKey("obs_inputs.id", ondelete="SET NULL"))
    external_url: Mapped[str | None] = mapped_column(Text)
    playback_type: Mapped[PlaybackType] = mapped_column(Enum(PlaybackType), default=PlaybackType.hls)
    playback_url: Mapped[str | None] = mapped_column(Text)
    ome_app_name: Mapped[str] = mapped_column(String(120), default="app")
    ome_stream_name: Mapped[str | None] = mapped_column(String(180), index=True)
    is_main: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=100)
    token_required: Mapped[bool] = mapped_column(Boolean, default=False)

    tournament: Mapped[Tournament] = relationship(back_populates="streams")
    camera: Mapped[Camera | None] = relationship(back_populates="streams")
    obs_input: Mapped[ObsInput | None] = relationship(back_populates="streams")
    tokens: Mapped[list["StreamAccessToken"]] = relationship(back_populates="stream", cascade="all, delete-orphan")


class StreamAccessToken(Base):
    __tablename__ = "stream_access_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    tournament_id: Mapped[int] = mapped_column(ForeignKey("tournaments.id", ondelete="CASCADE"), index=True)
    tournament_stream_id: Mapped[int | None] = mapped_column(
        ForeignKey("tournament_streams.id", ondelete="CASCADE"), index=True
    )
    token: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    max_views: Mapped[int | None] = mapped_column(Integer)
    current_views: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tournament: Mapped[Tournament] = relationship(back_populates="tokens")
    stream: Mapped[TournamentStream | None] = relationship(back_populates="tokens")


class ArchiveRecording(Base):
    __tablename__ = "archive_recordings"

    id: Mapped[int] = mapped_column(primary_key=True)
    tournament_id: Mapped[int] = mapped_column(ForeignKey("tournaments.id", ondelete="CASCADE"), index=True)
    tournament_stream_id: Mapped[int | None] = mapped_column(ForeignKey("tournament_streams.id", ondelete="SET NULL"))
    source_type: Mapped[str] = mapped_column(String(60))
    file_path: Mapped[str] = mapped_column(Text)
    playback_url: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(60), default="created")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    value: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
