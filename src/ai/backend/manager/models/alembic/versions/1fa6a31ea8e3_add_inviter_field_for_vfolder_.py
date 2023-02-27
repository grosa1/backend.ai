"""add inviter field for vfolder_invitations

Revision ID: 1fa6a31ea8e3
Revises: 26d0c387e764
Create Date: 2018-07-05 00:09:35.230704

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "1fa6a31ea8e3"
down_revision = "26d0c387e764"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("vfolder_invitations", sa.Column("inviter", sa.String(length=256)))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("vfolder_invitations", "inviter")
    # ### end Alembic commands ###
