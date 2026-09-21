"""Initial foundation migration for BizPilot AI.

Revision ID: 0001_initial_foundation
Revises: None
Create Date: 2026-09-21 00:00:00.000000+00:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0001_initial_foundation"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Baseline foundation revision: establishes Alembic tracking
    # and verifies connection to authoritative PostgreSQL database.
    pass


def downgrade() -> None:
    pass
