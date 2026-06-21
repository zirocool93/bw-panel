"""camera rtsp transport

Revision ID: 0002_camera_rtsp_transport
Revises: 0001_initial
Create Date: 2026-06-22
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_camera_rtsp_transport"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cameras",
        sa.Column("rtsp_transport", sa.String(20), nullable=False, server_default="automatic"),
    )
    op.alter_column("cameras", "last_status", type_=sa.Text(), existing_type=sa.String(60))


def downgrade() -> None:
    op.alter_column("cameras", "last_status", type_=sa.String(60), existing_type=sa.Text())
    op.drop_column("cameras", "rtsp_transport")
