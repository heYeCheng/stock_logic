# -*- coding: utf-8 -*-
"""
Pydantic schemas for Sector Logic Skills.

Used by SectorLogicSkillLoader to validate skill files.
"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional, Literal, Dict, Any


class Dimension(BaseModel):
    """Evaluation dimension for a logic type framework."""

    name: str
    weight: float = Field(..., ge=0, le=1)
    data_source: str
    scoring_prompt: Optional[str] = None


class Framework(BaseModel):
    """Framework schema for evaluating a logic type."""

    logic_type: str
    version: int
    dimensions: List[Dimension]
    metadata: Optional[Dict[str, Any]] = None

    @validator('dimensions')
    def weights_must_sum_to_one(cls, v):
        """Validate that dimension weights sum to approximately 1.0."""
        total = sum(d.weight for d in v)
        if not 0.95 <= total <= 1.05:
            raise ValueError(f"Dimension weights must sum to ~1.0, got {total}")
        if len(v) != 5:
            raise ValueError(f"Framework must have exactly 5 dimensions, got {len(v)}")
        return v


class RiskFactor(BaseModel):
    """Risk factor definition."""

    risk: str
    source: str
    trigger_prompt: str
    action: str
    suggestion: Literal["观察", "减仓", "离场"]


class RiskTemplate(BaseModel):
    """Risk template schema for a logic type."""

    logic_type: str
    version: int
    risk_factors: List[RiskFactor]

    @validator('risk_factors')
    def must_have_risk_factors(cls, v):
        """Validate that risk template has at least one risk factor."""
        if not v:
            raise ValueError("Risk template must have at least one risk factor")
        return v


class LogicTypeSkill(BaseModel):
    """Logic type skill schema (Markdown frontmatter)."""

    name: str
    category: Literal["logic-type"]
    version: str
    definition: Optional[str] = None
    typical_scenarios: Optional[List[str]] = None
    duration: Optional[str] = None
    rules: Optional[List[str]] = None
