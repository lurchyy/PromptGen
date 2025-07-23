"""add model column to sub_use_cases\n\nRevision ID: add_prompt_model_column_to_subusecase\nRevises: add_subusecase_table\nCreate Date: 2025-07-20\n"""
revision = 'add_prompt_model_column_to_subusecase'
down_revision = 'add_subusecase_table'
branch_labels = None
depends_on = None
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.add_column('sub_use_cases', sa.Column('model', sa.String(), nullable=False, server_default='gpt'))
    op.create_index('ix_sub_use_cases_model', 'sub_use_cases', ['model'])

def downgrade():
    op.drop_index('ix_sub_use_cases_model', table_name='sub_use_cases')
    op.drop_column('sub_use_cases', 'model')
