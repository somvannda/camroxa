"""merge_web_music_and_parallel_features

Revision ID: fffddbe8fbb3
Revises: e5077c52f2b7
Create Date: 2026-08-16 13:23:03.626573+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fffddbe8fbb3'
down_revision: Union[str, None] = 'e5077c52f2b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
