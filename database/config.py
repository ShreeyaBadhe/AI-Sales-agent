from dataclasses import dataclass
from typing import Optional


@dataclass
class DatabaseConfig:
    """Database configuration settings."""

    db_name: str
    db_path: str
    schema_path: Optional[str] = None
    products_path: Optional[str] = None


# Default configuration
DEFAULT_CONFIG = DatabaseConfig(
    db_name="store.db",
    db_path="database/db/store.db",
    schema_path="database/db/schemas.sql",
    products_path="database/db/products.json",
)
