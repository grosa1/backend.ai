"""add_clone_allowed_to_vfolders

Revision ID: d463fc5d6109
Revises: 0d553d59f369
Create Date: 2020-09-01 16:57:55.339619

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision = "d463fc5d6109"
down_revision = "0d553d59f369"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("vfolders", sa.Column("clone_allowed", sa.Boolean(), nullable=True))
    op.execute(text("UPDATE vfolders SET clone_allowed = false"))
    op.alter_column("vfolders", "clone_allowed", nullable=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("vfolders", "clone_allowed")
    # ### end Alembic commands ###
