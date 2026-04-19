# -*- coding: utf-8 -*-
"""
Sector Logic DataStore

Snapshot-based persistent storage layer with date versioning.
Enables replay, comparison, and debugging without re-fetching data.

Strict unidirectional dependency:
  Collection -> DataStore -> Analysis (read-only from DataStore)
"""

import json
import logging
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class DataStore:
    """
    Snapshot-based DataStore.

    Storage layout:
        data_root/
          snapshots/
            2026-04-14/
              macro.json
              sectors/
                CPO.json
                AI.json
              stocks/
                300502.json
                600519.json
            2026-04-15/
              ...
          checkpoints/
            collection_progress.json
    """

    def __init__(self, data_root: str = "./data/sector_logic"):
        self.data_root = Path(data_root)
        self.snapshots_dir = self.data_root / "snapshots"
        self.checkpoints_dir = self.data_root / "checkpoints"
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)

    # === Snapshot write ===

    def write_snapshot(self, d: date, key: str, data: Dict[str, Any]) -> None:
        """
        Write a snapshot for a given date and key.

        Keys are hierarchical: "macro", "sectors/CPO", "stocks/300502"
        """
        parts = key.split("/")
        if len(parts) == 1:
            # top-level key: macro.json
            path = self.snapshots_dir / d.isoformat() / f"{parts[0]}.json"
        else:
            # nested: sectors/CPO -> snapshots/2026-04-14/sectors/CPO.json
            path = self.snapshots_dir / d.isoformat() / "/".join(parts[:-1]) / f"{parts[-1]}.json"

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        logger.debug(f"[DataStore] wrote snapshot {key} for {d.isoformat()}")

    # === Snapshot read ===

    def get_snapshot(self, d: date, key: str) -> Optional[Dict[str, Any]]:
        """
        Read a snapshot for a given date and key.
        Returns None if not found.
        """
        parts = key.split("/")
        if len(parts) == 1:
            path = self.snapshots_dir / d.isoformat() / f"{parts[0]}.json"
        else:
            path = self.snapshots_dir / d.isoformat() / "/".join(parts[:-1]) / f"{parts[-1]}.json"

        if not path.exists():
            return None

        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_partial_snapshot(self, d: date, keys: List[str]) -> Dict[str, Any]:
        """
        Read multiple keys from a given date.
        Returns dict of {key: data} for found keys, missing keys omitted.
        """
        result = {}
        for key in keys:
            data = self.get_snapshot(d, key)
            if data is not None:
                result[key] = data
        return result

    # === Date listing ===

    def list_available_dates(self, key: Optional[str] = None) -> List[date]:
        """
        List all dates that have snapshot data.
        If key is provided, only return dates that have that specific key.
        """
        if not self.snapshots_dir.exists():
            return []

        dates = []
        for d_dir in sorted(self.snapshots_dir.iterdir()):
            if not d_dir.is_dir():
                continue
            try:
                d = date.fromisoformat(d_dir.name)
            except ValueError:
                continue

            if key:
                parts = key.split("/")
                if len(parts) == 1:
                    if (d_dir / f"{parts[0]}.json").exists():
                        dates.append(d)
                else:
                    if (d_dir / "/".join(parts[:-1]) / f"{parts[-1]}.json").exists():
                        dates.append(d)
            else:
                dates.append(d)

        return dates

    def has_snapshot(self, d: date, key: str) -> bool:
        """Check if a snapshot exists for a given date and key."""
        return self.get_snapshot(d, key) is not None

    # === Checkpoint (for collection resume) ===

    def write_checkpoint(self, checkpoint_name: str, data: Dict[str, Any]) -> None:
        """Write collection progress checkpoint."""
        path = self.checkpoints_dir / f"{checkpoint_name}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    def get_checkpoint(self, checkpoint_name: str) -> Optional[Dict[str, Any]]:
        """Read collection progress checkpoint."""
        path = self.checkpoints_dir / f"{checkpoint_name}.json"
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def clear_checkpoint(self, checkpoint_name: str) -> None:
        """Clear checkpoint after collection completes."""
        path = self.checkpoints_dir / f"{checkpoint_name}.json"
        if path.exists():
            path.unlink()

    # === Lifecycle state storage ===

    def save_lifecycle_state(self, logic_id: str, state: Dict[str, Any]) -> None:
        """
        Save lifecycle state for a given logic.
        Stored in snapshots/lifecycle/{logic_id}.json (latest).
        """
        path = self.snapshots_dir / "lifecycle" / f"{logic_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2, default=str)
        logger.debug(f"[DataStore] saved lifecycle state for {logic_id}")

    def get_lifecycle_state(self, logic_id: str) -> Optional[Dict[str, Any]]:
        """Load lifecycle state for a given logic. Returns None if not found."""
        path = self.snapshots_dir / "lifecycle" / f"{logic_id}.json"
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    # === Bulk operations ===

    def copy_snapshot(self, from_date: date, to_date: date, keys: Optional[List[str]] = None) -> None:
        """Copy snapshots from one date to another (useful for macro weekly data)."""
        from_date_str = from_date.isoformat()
        from_dir = self.snapshots_dir / from_date_str

        if not from_dir.exists():
            logger.warning(f"[DataStore] source date {from_date_str} has no snapshots")
            return

        if keys:
            for key in keys:
                data = self.get_snapshot(from_date, key)
                if data:
                    self.write_snapshot(to_date, key, data)
        else:
            # copy entire directory
            to_dir = self.snapshots_dir / to_date.isoformat()
            to_dir.mkdir(parents=True, exist_ok=True)
            import shutil
            for src in from_dir.rglob("*"):
                if src.is_file():
                    rel = src.relative_to(from_dir)
                    dst = to_dir / rel
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    import shutil as _shutil
                    _shutil.copy2(src, dst)

    # === Phase 0.5: New snapshot types ===

    def save_macro_state(self, d: date, macro_data: Dict[str, Any]) -> None:
        """Save L0 macro environment state snapshot."""
        self.write_snapshot(d, "macro_state", macro_data)
        logger.debug(f"[DataStore] saved macro_state for {d.isoformat()}")

    def get_macro_state(self, d: date) -> Optional[Dict[str, Any]]:
        """Load L0 macro environment state."""
        return self.get_snapshot(d, "macro_state")

    def save_sector_logics(self, d: date, sector_code: str, logics_data: Dict[str, Any]) -> None:
        """Save L1 sector logics snapshot."""
        self.write_snapshot(d, f"sector_logics/{sector_code}", logics_data)
        logger.debug(f"[DataStore] saved sector_logics/{sector_code} for {d.isoformat()}")

    def get_sector_logics(self, d: date, sector_code: str) -> Optional[Dict[str, Any]]:
        """Load L1 sector logics."""
        return self.get_snapshot(d, f"sector_logics/{sector_code}")

    def save_market_radar(self, d: date, sector_code: str, radar_data: Dict[str, Any]) -> None:
        """Save L2 market radar snapshot."""
        self.write_snapshot(d, f"market_radar/{sector_code}", radar_data)

    def save_stock_scores(self, d: date, stock_code: str, score_data: Dict[str, Any]) -> None:
        """Save L3 stock scores snapshot."""
        self.write_snapshot(d, f"stock_scores/{stock_code}", score_data)

    def save_recommendations(self, d: date, recommendations: List[Dict[str, Any]]) -> None:
        """Save L4 recommendations snapshot."""
        self.write_snapshot(d, "recommendations", {"recommendations": recommendations, "count": len(recommendations)})
