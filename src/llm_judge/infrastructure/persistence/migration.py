"""
Database migration system.

Provides migration capabilities for upgrading data storage formats,
schema changes, and data transformations.
"""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from ...domain.persistence.models import (
    EvaluationRecord,
    EvaluationMetadata,
    PersistenceConfig,
    StorageFormat,
)


class Migration:
    """Base class for data migrations."""

    def __init__(self, version: str, description: str):
        self.version = version
        self.description = description
        self.applied_at: Optional[datetime] = None

    async def up(self, storage_path: str) -> None:
        """Apply migration."""
        raise NotImplementedError

    async def down(self, storage_path: str) -> None:
        """Rollback migration."""
        raise NotImplementedError

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "version": self.version,
            "description": self.description,
            "applied_at": self.applied_at.isoformat() if self.applied_at else None,
        }


class Migration001_InitialSchema(Migration):
    """Initial schema migration."""

    def __init__(self):
        super().__init__("001", "Initial schema creation")

    async def up(self, storage_path: str) -> None:
        """Create initial schema."""
        storage_path = Path(storage_path)
        storage_path.mkdir(parents=True, exist_ok=True)

        # Create initial files
        (storage_path / "evaluations.json").touch()
        (storage_path / "evaluations_index.json").touch()
        (storage_path / "cache.json").touch()
        (storage_path / "migrations.json").touch()

    async def down(self, storage_path: str) -> None:
        """Remove initial schema."""
        storage_path = Path(storage_path)
        for file_name in [
            "evaluations.json",
            "evaluations_index.json",
            "cache.json",
            "migrations.json",
        ]:
            file_path = storage_path / file_name
            if file_path.exists():
                file_path.unlink()


class Migration002_AddMetadataFields(Migration):
    """Add metadata fields to evaluation records."""

    def __init__(self):
        super().__init__("002", "Add metadata fields to evaluation records")

    async def up(self, storage_path: str) -> None:
        """Add metadata fields."""
        storage_path = Path(storage_path)
        evaluations_file = storage_path / "evaluations.json"

        if not evaluations_file.exists():
            return

        with open(evaluations_file, "r", encoding="utf-8") as f:
            records = json.load(f)

        updated_records = []
        for record in records:
            # Add missing metadata fields
            if "metadata" not in record:
                record["metadata"] = {
                    "id": str(uuid4()),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "version": "1.0.0",
                    "tags": [],
                    "notes": None,
                    "user_id": None,
                    "session_id": None,
                    "batch_id": None,
                }
            else:
                metadata = record["metadata"]
                if "id" not in metadata:
                    metadata["id"] = str(uuid4())
                if "created_at" not in metadata:
                    metadata["created_at"] = datetime.now(timezone.utc).isoformat()
                if "updated_at" not in metadata:
                    metadata["updated_at"] = datetime.now(timezone.utc).isoformat()
                if "version" not in metadata:
                    metadata["version"] = "1.0.0"
                if "tags" not in metadata:
                    metadata["tags"] = []
                if "notes" not in metadata:
                    metadata["notes"] = None
                if "user_id" not in metadata:
                    metadata["user_id"] = None
                if "session_id" not in metadata:
                    metadata["session_id"] = None
                if "batch_id" not in metadata:
                    metadata["batch_id"] = None

            updated_records.append(record)

        with open(evaluations_file, "w", encoding="utf-8") as f:
            json.dump(updated_records, f, indent=2, ensure_ascii=False)

    async def down(self, storage_path: str) -> None:
        """Remove metadata fields."""
        storage_path = Path(storage_path)
        evaluations_file = storage_path / "evaluations.json"

        if not evaluations_file.exists():
            return

        with open(evaluations_file, "r", encoding="utf-8") as f:
            records = json.load(f)

        updated_records = []
        for record in records:
            # Remove metadata fields
            if "metadata" in record:
                del record["metadata"]
            updated_records.append(record)

        with open(evaluations_file, "w", encoding="utf-8") as f:
            json.dump(updated_records, f, indent=2, ensure_ascii=False)


class Migration003_AddCacheExpiration(Migration):
    """Add cache expiration support."""

    def __init__(self):
        super().__init__("003", "Add cache expiration support")

    async def up(self, storage_path: str) -> None:
        """Add cache expiration fields."""
        storage_path = Path(storage_path)
        cache_file = storage_path / "cache.json"

        if not cache_file.exists():
            return

        with open(cache_file, "r", encoding="utf-8") as f:
            cache = json.load(f)

        updated_cache = {}
        for key, entry in cache.items():
            # Add missing cache fields
            if "expires_at" not in entry:
                entry["expires_at"] = None
            if "access_count" not in entry:
                entry["access_count"] = 0
            if "last_accessed" not in entry:
                entry["last_accessed"] = datetime.now(timezone.utc).isoformat()

            updated_cache[key] = entry

        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(updated_cache, f, indent=2, ensure_ascii=False)

    async def down(self, storage_path: str) -> None:
        """Remove cache expiration fields."""
        storage_path = Path(storage_path)
        cache_file = storage_path / "cache.json"

        if not cache_file.exists():
            return

        with open(cache_file, "r", encoding="utf-8") as f:
            cache = json.load(f)

        updated_cache = {}
        for key, entry in cache.items():
            # Remove cache expiration fields
            if "expires_at" in entry:
                del entry["expires_at"]
            if "access_count" in entry:
                del entry["access_count"]
            if "last_accessed" in entry:
                del entry["last_accessed"]

            updated_cache[key] = entry

        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(updated_cache, f, indent=2, ensure_ascii=False)


class MigrationService:
    """Service for managing database migrations."""

    def __init__(self, storage_path: str):
        self.storage_path = Path(storage_path)
        self.migrations_file = self.storage_path / "migrations.json"
        self.migrations = self._get_available_migrations()
        self._ensure_storage_path()

    def _ensure_storage_path(self):
        """Ensure storage directory exists."""
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def _get_available_migrations(self) -> List[Migration]:
        """Get list of available migrations."""
        return [
            Migration001_InitialSchema(),
            Migration002_AddMetadataFields(),
            Migration003_AddCacheExpiration(),
        ]

    def _load_applied_migrations(self) -> List[Dict[str, Any]]:
        """Load applied migrations."""
        if not self.migrations_file.exists():
            return []

        with open(self.migrations_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_applied_migrations(self, migrations: List[Dict[str, Any]]):
        """Save applied migrations."""
        with open(self.migrations_file, "w", encoding="utf-8") as f:
            json.dump(migrations, f, indent=2, ensure_ascii=False)

    async def get_migration_status(self) -> Dict[str, Any]:
        """Get migration status."""
        applied_migrations = self._load_applied_migrations()
        applied_versions = {m["version"] for m in applied_migrations}

        available_migrations = []
        for migration in self.migrations:
            available_migrations.append(
                {
                    "version": migration.version,
                    "description": migration.description,
                    "applied": migration.version in applied_versions,
                    "applied_at": next(
                        (
                            m["applied_at"]
                            for m in applied_migrations
                            if m["version"] == migration.version
                        ),
                        None,
                    ),
                }
            )

        return {
            "total_migrations": len(self.migrations),
            "applied_migrations": len(applied_migrations),
            "pending_migrations": len(self.migrations) - len(applied_migrations),
            "migrations": available_migrations,
        }

    async def migrate_up(self, target_version: Optional[str] = None) -> List[str]:
        """Apply migrations up to target version."""
        applied_migrations = self._load_applied_migrations()
        applied_versions = {m["version"] for m in applied_migrations}

        migrations_to_apply = []
        for migration in self.migrations:
            if migration.version not in applied_versions:
                if target_version and migration.version > target_version:
                    break
                migrations_to_apply.append(migration)

        applied_versions_list = []
        for migration in migrations_to_apply:
            try:
                await migration.up(str(self.storage_path))
                migration.applied_at = datetime.now(timezone.utc)

                applied_migrations.append(migration.to_dict())
                applied_versions_list.append(migration.version)

                print(f"Applied migration {migration.version}: {migration.description}")
            except Exception as e:
                print(f"Failed to apply migration {migration.version}: {e}")
                raise

        self._save_applied_migrations(applied_migrations)
        return applied_versions_list

    async def migrate_down(self, target_version: Optional[str] = None) -> List[str]:
        """Rollback migrations down to target version."""
        applied_migrations = self._load_applied_migrations()
        applied_versions = {m["version"] for m in applied_migrations}

        migrations_to_rollback = []
        for migration in reversed(self.migrations):
            if migration.version in applied_versions:
                if target_version and migration.version <= target_version:
                    break
                migrations_to_rollback.append(migration)

        rolled_back_versions = []
        for migration in migrations_to_rollback:
            try:
                await migration.down(str(self.storage_path))

                # Remove from applied migrations
                applied_migrations = [
                    m for m in applied_migrations if m["version"] != migration.version
                ]
                rolled_back_versions.append(migration.version)

                print(
                    f"Rolled back migration {migration.version}: {migration.description}"
                )
            except Exception as e:
                print(f"Failed to rollback migration {migration.version}: {e}")
                raise

        self._save_applied_migrations(applied_migrations)
        return rolled_back_versions

    async def reset_migrations(self) -> None:
        """Reset all migrations."""
        applied_migrations = self._load_applied_migrations()
        applied_versions = {m["version"] for m in applied_migrations}

        for migration in reversed(self.migrations):
            if migration.version in applied_versions:
                try:
                    await migration.down(str(self.storage_path))
                    print(
                        f"Reset migration {migration.version}: {migration.description}"
                    )
                except Exception as e:
                    print(f"Failed to reset migration {migration.version}: {e}")

        # Clear migrations file
        self._save_applied_migrations([])

    async def create_backup(self, backup_path: Optional[str] = None) -> str:
        """Create backup of current data."""
        if not backup_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = self.storage_path / f"backup_{timestamp}"

        backup_path = Path(backup_path)
        backup_path.mkdir(parents=True, exist_ok=True)

        # Copy all data files
        for file_name in [
            "evaluations.json",
            "evaluations_index.json",
            "cache.json",
            "migrations.json",
        ]:
            source_file = self.storage_path / file_name
            if source_file.exists():
                shutil.copy2(source_file, backup_path / file_name)

        return str(backup_path)

    async def restore_backup(self, backup_path: str) -> None:
        """Restore from backup."""
        backup_path = Path(backup_path)

        if not backup_path.exists():
            raise ValueError(f"Backup path does not exist: {backup_path}")

        # Copy all data files
        for file_name in [
            "evaluations.json",
            "evaluations_index.json",
            "cache.json",
            "migrations.json",
        ]:
            source_file = backup_path / file_name
            if source_file.exists():
                shutil.copy2(source_file, self.storage_path / file_name)


class MigrationManager:
    """High-level migration manager."""

    def __init__(self, storage_path: str):
        self.migration_service = MigrationService(storage_path)

    async def initialize(self) -> None:
        """Initialize storage with migrations."""
        status = await self.migration_service.get_migration_status()

        if status["applied_migrations"] == 0:
            print("Initializing storage with migrations...")
            await self.migration_service.migrate_up()
            print("Storage initialized successfully")
        else:
            print(
                f"Storage already initialized with {status['applied_migrations']} migrations"
            )

    async def upgrade(self, target_version: Optional[str] = None) -> None:
        """Upgrade storage to latest or target version."""
        status = await self.migration_service.get_migration_status()

        if status["pending_migrations"] == 0:
            print("No pending migrations")
            return

        print(f"Applying {status['pending_migrations']} pending migrations...")
        applied = await self.migration_service.migrate_up(target_version)
        print(f"Applied {len(applied)} migrations: {', '.join(applied)}")

    async def downgrade(self, target_version: str) -> None:
        """Downgrade storage to target version."""
        print(f"Rolling back to version {target_version}...")
        rolled_back = await self.migration_service.migrate_down(target_version)
        print(f"Rolled back {len(rolled_back)} migrations: {', '.join(rolled_back)}")

    async def status(self) -> Dict[str, Any]:
        """Get migration status."""
        return await self.migration_service.get_migration_status()

    async def backup(self, backup_path: Optional[str] = None) -> str:
        """Create backup."""
        backup_path = await self.migration_service.create_backup(backup_path)
        print(f"Backup created: {backup_path}")
        return backup_path

    async def restore(self, backup_path: str) -> None:
        """Restore from backup."""
        await self.migration_service.restore_backup(backup_path)
        print(f"Restored from backup: {backup_path}")

    async def reset(self) -> None:
        """Reset all migrations."""
        print("Resetting all migrations...")
        await self.migration_service.reset_migrations()
        print("All migrations reset")
