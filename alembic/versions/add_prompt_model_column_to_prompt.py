"""add model column to prompts\n\nRevision ID: add_prompt_model_column_to_prompt\nRevises: 7097a447f123\nCreate Date: 2025-07-20\n"""
revision = 'add_prompt_model_column_to_prompt'
down_revision = '7097a447f123'
branch_labels = None
depends_on = None
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.add_column('prompts', sa.Column('model', sa.String(), nullable=False, server_default='gpt'))
    op.create_index('ix_prompts_model', 'prompts', ['model'])

def downgrade():
    op.drop_index('ix_prompts_model', table_name='prompts')
    op.drop_column('prompts', 'model')
