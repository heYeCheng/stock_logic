# -*- coding: utf-8 -*-
"""
FrameworkCache: caches evaluation frameworks by logic type.

同类型板块共享同一套框架模板，大幅降低 LLM 调用成本。

Re-generate framework only when:
  1. New logic type discovered (not in predefined catalog)
  2. Existing framework fails to explain sector price behavior for 5 consecutive days
  3. User manually triggers re-generation

Skill-based: loads frameworks from ~/.gstack/skills/sector-logic/logics/{类型}/framework.json
"""

import json
import logging
from datetime import date
from typing import Any, Dict, List, Optional

from .skill_loader import SectorLogicSkillLoader

logger = logging.getLogger(__name__)


class FrameworkCache:
    """
    Caches evaluation frameworks by logic type.

    Key: logic category string (e.g., "产业趋势")
    Value: framework dict with dimensions, weights, version

    Skill-based: loads from SectorLogicSkillLoader instead of hardcoding.
    """

    def __init__(self, storage_path: Optional[str] = None, skill_loader: Optional[SectorLogicSkillLoader] = None):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self.storage_path = storage_path
        self.skill_loader = skill_loader or SectorLogicSkillLoader()

        # Load frameworks from skill files
        self._load_from_skills()

        # Load persisted cache if available (for backward compatibility)
        if self.storage_path:
            self._load_from_disk()

    def _load_from_skills(self) -> None:
        """Load frameworks from skill files."""
        for category in self.skill_loader.list_logic_types():
            framework = self.skill_loader.load_framework(category)
            if framework:
                # Convert Pydantic model to dict for backward compatibility
                self._cache[category] = {
                    "logic_type": framework.logic_type,
                    "dimensions": [
                        {
                            "name": dim.name,
                            "weight": dim.weight,
                            "data_source": dim.data_source,
                            "scoring_prompt": dim.scoring_prompt,
                        }
                        for dim in framework.dimensions
                    ],
                    "version": framework.version,
                    "metadata": framework.metadata,
                    "failure_count": 0,
                }
                logger.info(f"[FrameworkCache] loaded framework for {category} from skill file")

    def get(self, category: str) -> Optional[Dict[str, Any]]:
        """Get cached framework for a logic category."""
        return self._cache.get(category)

    def put(self, category: str, framework: Dict[str, Any]) -> None:
        """Cache a new or updated framework."""
        self._cache[category] = framework
        if self.storage_path:
            self._save()

    def invalidate(self, category: str) -> None:
        """Invalidate a cached framework (e.g., after 5 consecutive failures)."""
        if category in self._cache:
            del self._cache[category]
            logger.info(f"[FrameworkCache] invalidated framework for {category}")

    def increment_failure(self, category: str, max_failures: int = 5) -> bool:
        """
        Increment failure count for a framework.
        Returns True if framework should be invalidated.
        """
        framework = self._cache.get(category)
        if not framework:
            return True

        framework["failure_count"] = framework.get("failure_count", 0) + 1
        if framework["failure_count"] >= max_failures:
            self.invalidate(category)
            return True
        return False

    def reset_failure(self, category: str) -> None:
        """Reset failure count when framework performs well."""
        framework = self._cache.get(category)
        if framework:
            framework["failure_count"] = 0

    def list_categories(self) -> List[str]:
        """List all cached framework categories."""
        return list(self._cache.keys())

    def _load_from_disk(self) -> None:
        """Load cached frameworks from disk (backward compatibility)."""
        import os
        if os.path.exists(self.storage_path):
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for category, framework in data.items():
                    if category not in self._cache:
                        # Only load from disk if not already loaded from skills
                        self._cache[category] = framework
                        logger.info(f"[FrameworkCache] loaded framework for {category} from disk")

    def _save(self) -> None:
        """Persist cached frameworks to disk."""
        import os
        os.makedirs(os.path.dirname(self.storage_path) or ".", exist_ok=True)
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(self._cache, f, ensure_ascii=False, indent=2, default=str)
