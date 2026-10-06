from alembic import op
import sqlalchemy as sa

revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # For a first local run, use backend/seed.py. This migration scaffold is intentionally kept
    # explicit so a production team can generate PostgreSQL-specific migrations after choosing DB policy.
    pass

def downgrade():
    pass
