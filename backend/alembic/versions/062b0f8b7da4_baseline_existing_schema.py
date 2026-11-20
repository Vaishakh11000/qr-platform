"""baseline existing schema

Revision ID: 062b0f8b7da4
Revises: 6f9381ecbfee
Create Date: 2026-11-12 13:41:02.920304

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '062b0f8b7da4'
down_revision: Union[str, Sequence[str], None] = '6f9381ecbfee'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
