"""Link each rotated refresh token to its successor (SEC-P1 F3 follow-up).

Revision ID: 0017_refresh_token_successor
Revises: 0016_org_invitations
Create Date: 2026-10-09 00:00:00.000000+00:00

Lets the refresh service tell a lost rotation response (the page was reloaded or left while a
refresh was in flight, so the browser never stored the new cookie) from a replayed stolen token.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0017_refresh_token_successor"
down_revision: Union[str, None] = "0016_org_invitations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("refresh_tokens", sa.Column("replaced_by_token_id", sa.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_refresh_tokens_replaced_by_token_id_refresh_tokens",
        "refresh_tokens",
        "refresh_tokens",
        ["replaced_by_token_id"],
        ["id"],
    )  # NO ACTION, like every auth foreign key (Founder Option A: no cascading deletes)


def downgrade() -> None:
    op.drop_constraint("fk_refresh_tokens_replaced_by_token_id_refresh_tokens", "refresh_tokens", type_="foreignkey")
    op.drop_column("refresh_tokens", "replaced_by_token_id")
