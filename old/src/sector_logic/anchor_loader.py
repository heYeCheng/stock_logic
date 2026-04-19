# -*- coding: utf-8 -*-
"""
Anchor loader — loads and validates YAML anchor files at startup.

Anchors provide configurable parameters for LLM qualitative judgments
and rule-engine mappings. All weights, thresholds, and mappings are
loaded from anchors/ rather than hardcoded in Python.
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

logger = logging.getLogger(__name__)

# Default anchors directory: project root / anchors
DEFAULT_ANCHORS_DIR = Path(__file__).resolve().parents[2] / 'anchors'

# Schema for required fields per anchor file
ANCHOR_SCHEMAS: Dict[str, list] = {
    'macro_anchor.yaml': [],  # no strict schema, just must parse
    'logic_importance.yaml': ['levels'],
    'logic_category.yaml': ['categories'],
    'event_qualitative.yaml': ['positive_events', 'negative_events'],
    'affiliation_strength.yaml': ['levels'],
    'industry_position.yaml': ['levels'],
    'sector_keywords.yaml': [],
}

# Default values if anchor file is missing
DEFAULT_ANCHORS: Dict[str, dict] = {
    'macro_anchor.yaml': {
        'version': '1.0',
        'pmi_thresholds': {
            'strong_expansion': 52,
            'weak_expansion_low': 50,
            'contraction_low': 48,
        },
        'quadrant_multipliers': {
            'wide_credit': 1.10,
            'tight_liquidity': 0.95,
            'double_tight': 0.90,
            'wide_money': 1.05,
            'neutral': 1.00,
        },
        'clamp_range': [0.85, 1.15],
    },
    'logic_importance.yaml': {
        'version': '1.0',
        'levels': {
            'high': {'initial_strength': 0.7},
            'medium': {'initial_strength': 0.5},
            'low': {'initial_strength': 0.3},
        },
        'default': 0.5,
    },
    'logic_category.yaml': {
        'version': '1.0',
        'categories': {
            '产业趋势': {'decay_per_period': 0.02, 'period_days': 10},
            '政策驱动': {'decay_per_period': 0.05, 'period_days': 5},
            '事件驱动': {'decay_per_period': 0.05, 'period_days': 5},
            '流动性驱动': {'decay_per_period': 0.02, 'period_days': 10},
        },
    },
    'event_qualitative.yaml': {
        'version': '1.0',
        'positive_events': {
            '国家级政策发布': {'score_impact': 0.20, 'validity_days': 20},
            '龙头公司业绩超预期': {'score_impact': 0.15, 'validity_days': 10},
            '产业数据连续两月改善': {'score_impact': 0.10, 'validity_days': 15},
            '多家机构上调评级': {'score_impact': 0.05, 'validity_days': 5},
        },
        'negative_events': {
            '政策收紧监管问询': {'score_impact': -0.25, 'validity_days': 15},
            '龙头业绩暴雷': {'score_impact': -0.30, 'validity_days': 20},
            '大股东减持': {'score_impact': -0.10, 'validity_days': 10},
        },
    },
    'affiliation_strength.yaml': {
        'version': '1.0',
        'levels': {
            '主营概念': 1.0,
            '强关联': 0.8,
            '弱关联': 0.5,
        },
        'industry_default': 1.0,
    },
    'industry_position.yaml': {
        'version': '1.0',
        'levels': {
            '直接受益': 0.9,
            '间接受益': 0.6,
            '边缘受益': 0.3,
            '不受益': 0.1,
        },
        'default': 0.6,
    },
    'sector_keywords.yaml': {
        'version': '1.0',
    },
}


class AnchorLoader:
    """Loads and validates YAML anchor files."""

    def __init__(self, anchors_dir: Optional[Path] = None):
        self.anchors_dir = anchors_dir or DEFAULT_ANCHORS_DIR
        self._cache: Dict[str, dict] = {}

    def load(self, filename: str) -> dict:
        """Load a single anchor file. Returns default if file missing."""
        if filename in self._cache:
            return self._cache[filename]

        filepath = self.anchors_dir / filename
        if filepath.exists():
            with open(filepath, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            if data is None:
                data = {}
        else:
            logger.warning(f"Anchor file not found: {filepath}, using defaults")
            data = DEFAULT_ANCHORS.get(filename, {}).copy()

        self._cache[filename] = data
        return data

    def load_all(self) -> Dict[str, dict]:
        """Load all known anchor files."""
        result = {}
        for filename in ANCHOR_SCHEMAS:
            result[filename] = self.load(filename)
        return result

    def validate(self, filename: str) -> bool:
        """Validate an anchor file against its schema."""
        data = self.load(filename)
        required_fields = ANCHOR_SCHEMAS.get(filename, [])
        for field in required_fields:
            if field not in data:
                logger.error(f"Anchor {filename} missing required field: {field}")
                return False
        return True

    def validate_all(self) -> bool:
        """Validate all known anchor files. Returns True if all valid."""
        all_valid = True
        for filename in ANCHOR_SCHEMAS:
            if not self.validate(filename):
                all_valid = False
        return all_valid

    def get(self, filename: str, *keys: str, default: Any = None) -> Any:
        """Convenience: load anchor and traverse nested keys."""
        data = self.load(filename)
        for key in keys:
            if isinstance(data, dict):
                data = data.get(key, default)
            else:
                return default
        return data
