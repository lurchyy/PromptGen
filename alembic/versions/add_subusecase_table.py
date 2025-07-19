"""add sub_use_cases table\n\nRevision ID: add_subusecase_table\nRevises: 7097a447f123\nCreate Date: 2025-07-18\n"""
revision = 'add_subusecase_table'
down_revision = '7097a447f123'
branch_labels = None
depends_on = None
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.create_table(
        'sub_use_cases',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('sector_id', sa.Integer(), sa.ForeignKey('sectors.id'), nullable=False),
        sa.Column('use_case', sa.String(), nullable=False),
        sa.Column('sub_use_case', sa.String(), nullable=False),
        sa.Column('prompt', sa.Text(), nullable=False)
    )

def downgrade():
    op.drop_table('sub_use_cases')
