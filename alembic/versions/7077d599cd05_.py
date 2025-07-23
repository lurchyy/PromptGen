"""empty message

Revision ID: 7077d599cd05
Revises: add_prompt_model_column_to_prompt, add_prompt_model_column_to_subusecase
Create Date: 2025-07-20 21:21:09.068612

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7077d599cd05'
down_revision: Union[str, Sequence[str], None] = ('add_prompt_model_column_to_prompt', 'add_prompt_model_column_to_subusecase')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
