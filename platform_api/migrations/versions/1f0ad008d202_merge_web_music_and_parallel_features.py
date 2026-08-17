"""merge_web_music_and_parallel_features

Revision ID: 1f0ad008d202
Revises: ff781163cfbb
Create Date: 2026-08-16 13:30:24.705741+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1f0ad008d202'
down_revision: Union[str, None] = 'ff781163cfbb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
