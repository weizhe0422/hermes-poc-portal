"""baseline - 空基準 migration，證明 Migration Pipeline 可運作（P-M0）

Revision ID: 0001_baseline
Revises:
Create Date: 2026-07-18

"""
from typing import Sequence, Union

revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
