import json
import shutil
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List
import hashlib

from src.graph.types import KnowledgeGraph
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class GraphStorage:
    """
    Persistent storage for knowledge graphs with versioning and backup.

    Features:
    - Automatic versioning on save
    - Backup before overwrite
    - Version history tracking
    - Integrity checking via checksums
    """

    def __init__(self, storage_path: str = "knowledge_graph.json"):
        self.storage_path = Path(storage_path)
        self.versions_dir = self.storage_path.parent / "graph_versions"
        self.backups_dir = self.storage_path.parent / "graph_backups"

        # Create directories
        self.versions_dir.mkdir(parents=True, exist_ok=True)
        self.backups_dir.mkdir(parents=True, exist_ok=True)

    def save(self, graph: KnowledgeGraph, auto_version: bool = True) -> None:
        """
        Save knowledge graph with automatic backup and versioning.

        Args:
            graph: Knowledge graph to save
            auto_version: If True, automatically create a versioned copy
        """
        logger.info(f"Saving knowledge graph to {self.storage_path}")

        # Backup existing file if it exists
        if self.storage_path.exists():
            self._create_backup()

        # Prepare data
        data = graph.model_dump()
        data["metadata"]["saved_at"] = datetime.now(timezone.utc).isoformat()
        data["metadata"]["node_count"] = len(graph.nodes)
        data["metadata"]["edge_count"] = len(graph.edges)

        # Calculate checksum
        data_str = json.dumps(data, sort_keys=True)
        checksum = hashlib.sha256(data_str.encode()).hexdigest()
        data["metadata"]["checksum"] = checksum

        # Save main file
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.storage_path, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"✓ Saved graph: {len(graph.nodes)} nodes, {len(graph.edges)} edges")
        logger.info(f"  Checksum: {checksum[:16]}...")

        # Auto-version
        if auto_version:
            version = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            version_path = self.save_version(graph, version)
            logger.info(f"  Version saved: {version_path.name}")

    def load(self) -> KnowledgeGraph:
        """Load knowledge graph from storage."""
        if not self.storage_path.exists():
            logger.warning(f"No graph found at {self.storage_path}, returning empty graph")
            return KnowledgeGraph()

        logger.info(f"Loading knowledge graph from {self.storage_path}")

        with open(self.storage_path, "r") as f:
            data = json.load(f)

        # Verify checksum if present
        if "checksum" in data.get("metadata", {}):
            stored_checksum = data["metadata"]["checksum"]
            # Recalculate without the checksum field
            data_copy = data.copy()
            data_copy["metadata"] = {k: v for k, v in data["metadata"].items() if k != "checksum"}
            data_str = json.dumps(data_copy, sort_keys=True)
            calculated_checksum = hashlib.sha256(data_str.encode()).hexdigest()

            if stored_checksum != calculated_checksum:
                logger.warning(f"Checksum mismatch! File may be corrupted")
                logger.warning(f"  Stored: {stored_checksum[:16]}...")
                logger.warning(f"  Calculated: {calculated_checksum[:16]}...")

        graph = KnowledgeGraph(**data)
        logger.info(f"✓ Loaded graph: {len(graph.nodes)} nodes, {len(graph.edges)} edges")

        return graph

    def save_version(self, graph: KnowledgeGraph, version: str) -> Path:
        """Save a versioned copy of the graph."""
        version_path = self.versions_dir / f"graph_v{version}.json"

        data = graph.model_dump()
        data["version"] = version
        data["metadata"]["saved_at"] = datetime.now(timezone.utc).isoformat()
        data["metadata"]["node_count"] = len(graph.nodes)
        data["metadata"]["edge_count"] = len(graph.edges)

        with open(version_path, "w") as f:
            json.dump(data, f, indent=2)

        return version_path

    def load_version(self, version: str) -> Optional[KnowledgeGraph]:
        """Load a specific version of the graph."""
        version_path = self.versions_dir / f"graph_v{version}.json"

        if not version_path.exists():
            logger.error(f"Version {version} not found")
            return None

        logger.info(f"Loading version {version} from {version_path}")

        with open(version_path, "r") as f:
            data = json.load(f)

        return KnowledgeGraph(**data)

    def list_versions(self) -> List[dict]:
        """List all available versions."""
        versions = []

        for version_file in sorted(self.versions_dir.glob("graph_v*.json")):
            try:
                with open(version_file, "r") as f:
                    data = json.load(f)

                versions.append({
                    "version": data.get("version", version_file.stem),
                    "file": version_file.name,
                    "saved_at": data.get("metadata", {}).get("saved_at"),
                    "nodes": len(data.get("nodes", [])),
                    "edges": len(data.get("edges", [])),
                })
            except Exception as e:
                logger.warning(f"Could not read version file {version_file}: {e}")

        return versions

    def _create_backup(self) -> Optional[Path]:
        """Create a backup of the current graph file."""
        if not self.storage_path.exists():
            return None

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_path = self.backups_dir / f"{self.storage_path.stem}_backup_{timestamp}.json"

        try:
            shutil.copy2(self.storage_path, backup_path)
            logger.debug(f"Created backup: {backup_path.name}")
            return backup_path
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            return None

    def list_backups(self) -> List[Path]:
        """List all backup files."""
        return sorted(self.backups_dir.glob(f"{self.storage_path.stem}_backup_*.json"))

    def restore_backup(self, backup_file: str) -> bool:
        """Restore from a backup file."""
        backup_path = self.backups_dir / backup_file

        if not backup_path.exists():
            logger.error(f"Backup file {backup_file} not found")
            return False

        try:
            # Create a backup of the current state first
            if self.storage_path.exists():
                self._create_backup()

            shutil.copy2(backup_path, self.storage_path)
            logger.info(f"✓ Restored from backup: {backup_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to restore backup: {e}")
            return False

    def cleanup_old_backups(self, keep_count: int = 10):
        """Keep only the most recent N backups."""
        backups = self.list_backups()

        if len(backups) <= keep_count:
            return

        to_delete = backups[:-keep_count]
        for backup in to_delete:
            try:
                backup.unlink()
                logger.debug(f"Deleted old backup: {backup.name}")
            except Exception as e:
                logger.warning(f"Could not delete backup {backup.name}: {e}")
