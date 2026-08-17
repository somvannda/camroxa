"""merge_web_music_and_parallel_features

Revision ID: e5077c52f2b7
Revises: 084_provider_balance_events, 091_topup_purchases
Create Date: 2026-08-16 13:19:31.564602+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5077c52f2b7'
down_revision: Union[str, None] = ('084_provider_balance_events', '091_topup_purchases')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
