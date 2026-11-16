"""Compare the live database schema with the registered SQLAlchemy models."""

import app.db.models  # noqa: F401
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

from app.db.base import Base, engine


def main() -> int:
    with engine.connect() as connection:
        migration_context = MigrationContext.configure(
            connection,
            opts={"compare_type": True},
        )
        differences = compare_metadata(migration_context, Base.metadata)

    if differences:
        print(
            f"Schema differs from the Phase 1-9 baseline "
            f"({len(differences)} difference(s)); do not stamp this database."
        )
        return 1

    print("Database schema matches the Phase 1-9 baseline; stamping is safe.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
