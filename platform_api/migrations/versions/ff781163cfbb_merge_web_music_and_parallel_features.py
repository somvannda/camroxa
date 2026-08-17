"""merge_web_music_and_parallel_features

Revision ID: ff781163cfbb
Revises: fffddbe8fbb3
Create Date: 2026-08-16 13:24:16.515745+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ff781163cfbb'
down_revision: Union[str, None] = 'fffddbe8fbb3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
