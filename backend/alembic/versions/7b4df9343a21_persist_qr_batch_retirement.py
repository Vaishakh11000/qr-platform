"""persist QR batch retirement timestamp

Revision ID: 7b4df9343a21
Revises: 1f8e33444f5d
Create Date: 2026-11-20
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7b4df9343a21"
down_revision: Union[str, Sequence[str], None] = "1f8e33444f5d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "qr_batches",
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        schema="app",
    )


def downgrade() -> None:
    op.drop_column("qr_batches", "retired_at", schema="app")
