"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-21
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

user_role = postgresql.ENUM("admin", "operator", "manager", name="userrole", create_type=False)
tournament_status = postgresql.ENUM(
    "draft", "active", "finished", "archived", name="tournamentstatus", create_type=False
)
access_mode = postgresql.ENUM("public", "token", "password", name="accessmode", create_type=False)
source_type = postgresql.ENUM("camera", "obs", "external", name="sourcetype", create_type=False)
playback_type = postgresql.ENUM("hls", "ll_hls", name="playbacktype", create_type=False)


def upgrade() -> None:
    user_role.create(op.get_bind(), checkfirst=True)
    tournament_status.create(op.get_bind(), checkfirst=True)
    access_mode.create(op.get_bind(), checkfirst=True)
    source_type.create(op.get_bind(), checkfirst=True)
    playback_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("username", sa.String(120), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "cameras",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("camera_type", sa.String(60), nullable=False, server_default="generic_rtsp"),
        sa.Column("rtsp_url", sa.Text(), nullable=False),
        sa.Column("rtsp_username", sa.String(120)),
        sa.Column("rtsp_password", sa.String(255)),
        sa.Column("rtsp_transport", sa.String(20), nullable=False, server_default="automatic"),
        sa.Column("lane_from", sa.Integer()),
        sa.Column("lane_to", sa.Integer()),
        sa.Column("is_scoreboard_camera", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("ome_stream_name", sa.String(180), unique=True),
        sa.Column("preview_url", sa.Text()),
        sa.Column("last_status", sa.Text()),
        sa.Column("last_checked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "obs_inputs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("stream_key", sa.String(255), nullable=False),
        sa.Column("ingest_protocol", sa.String(30), nullable=False),
        sa.Column("ingest_url", sa.Text()),
        sa.Column("ome_stream_name", sa.String(180), unique=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_status", sa.String(60)),
        sa.Column("last_connected_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_obs_inputs_stream_key", "obs_inputs", ["stream_key"], unique=True)

    op.create_table(
        "tournaments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(220), nullable=False),
        sa.Column("slug", sa.String(220), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("date_start", sa.DateTime(timezone=True)),
        sa.Column("date_end", sa.DateTime(timezone=True)),
        sa.Column("status", tournament_status, nullable=False),
        sa.Column("poster_image", sa.Text()),
        sa.Column("is_public", sa.Boolean(), nullable=False),
        sa.Column("access_mode", access_mode, nullable=False),
        sa.Column("password_hash", sa.String(255)),
        sa.Column("archive_enabled", sa.Boolean(), nullable=False),
        sa.Column("archive_depth_days", sa.Integer(), nullable=False),
        sa.Column("show_on_homepage", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_tournaments_slug", "tournaments", ["slug"], unique=True)

    op.create_table(
        "tournament_streams",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tournament_id", sa.Integer(), sa.ForeignKey("tournaments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(220), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("source_type", source_type, nullable=False),
        sa.Column("camera_id", sa.Integer(), sa.ForeignKey("cameras.id", ondelete="SET NULL")),
        sa.Column("obs_input_id", sa.Integer(), sa.ForeignKey("obs_inputs.id", ondelete="SET NULL")),
        sa.Column("external_url", sa.Text()),
        sa.Column("playback_type", playback_type, nullable=False),
        sa.Column("playback_url", sa.Text()),
        sa.Column("ome_app_name", sa.String(120), nullable=False),
        sa.Column("ome_stream_name", sa.String(180)),
        sa.Column("is_main", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("token_required", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_tournament_streams_tournament_id", "tournament_streams", ["tournament_id"])
    op.create_index("ix_tournament_streams_ome_stream_name", "tournament_streams", ["ome_stream_name"])

    op.create_table(
        "stream_access_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tournament_id", sa.Integer(), sa.ForeignKey("tournaments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tournament_stream_id", sa.Integer(), sa.ForeignKey("tournament_streams.id", ondelete="CASCADE")),
        sa.Column("token", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("max_views", sa.Integer()),
        sa.Column("current_views", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_stream_access_tokens_token", "stream_access_tokens", ["token"], unique=True)

    op.create_table(
        "archive_recordings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tournament_id", sa.Integer(), sa.ForeignKey("tournaments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tournament_stream_id", sa.Integer(), sa.ForeignKey("tournament_streams.id", ondelete="SET NULL")),
        sa.Column("source_type", sa.String(60), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("playback_url", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("duration_seconds", sa.Integer()),
        sa.Column("size_bytes", sa.Integer()),
        sa.Column("status", sa.String(60), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "system_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(120), nullable=False),
        sa.Column("value", sa.Text()),
        sa.Column("description", sa.Text()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_system_settings_key", "system_settings", ["key"], unique=True)


def downgrade() -> None:
    op.drop_table("system_settings")
    op.drop_table("archive_recordings")
    op.drop_table("stream_access_tokens")
    op.drop_table("tournament_streams")
    op.drop_table("tournaments")
    op.drop_table("obs_inputs")
    op.drop_table("cameras")
    op.drop_table("users")
    playback_type.drop(op.get_bind(), checkfirst=True)
    source_type.drop(op.get_bind(), checkfirst=True)
    access_mode.drop(op.get_bind(), checkfirst=True)
    tournament_status.drop(op.get_bind(), checkfirst=True)
    user_role.drop(op.get_bind(), checkfirst=True)
