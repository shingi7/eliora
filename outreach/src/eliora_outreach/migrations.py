from .db import Database


def migrate(database: Database) -> None:
    """Run the small, explicit local schema migration set."""
    database.create()
