# -*- coding: utf-8 -*-
"""
SectorLogicSkillLoader: loads skill files from ~/.gstack/skills/sector-logic/.

Independent from existing SkillManager. Specialized for sector logic frameworks,
risk templates, and logic type definitions.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .schemas import Framework, RiskTemplate, LogicTypeSkill

logger = logging.getLogger(__name__)


class SectorLogicSkillLoader:
    """
    Loads sector-logic skill files.

    Skill directory structure (inner-cohesion by logic type):
    ~/.gstack/skills/sector-logic/
    ├── logics/{类型}/
    │   ├── definition.md
    │   ├── framework.json
    │   └── risk-template.json
    ├── macro/
    ├── stock/
    ├── lifecycle/
    └── composite/
    """

    def __init__(self, skill_dir: str = "~/.gstack/skills/sector-logic"):
        self.skill_dir = Path(skill_dir).expanduser()
        self._cache: Dict[str, Any] = {}

        # Validate directory exists
        if not self.skill_dir.exists():
            logger.warning(f"[SectorLogicSkillLoader] skill directory not found: {self.skill_dir}")
            self.skill_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"[SectorLogicSkillLoader] created skill directory: {self.skill_dir}")

    def load_logic_type(self, category: str) -> Optional[LogicTypeSkill]:
        """
        Load logic type skill (Markdown).

        Args:
            category: Logic type name (e.g., "产业趋势")

        Returns:
            LogicTypeSkill object or None if not found
        """
        cache_key = f"logic_type:{category}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        path = self.skill_dir / "logics" / category / "definition.md"
        if not path.exists():
            logger.warning(f"[SectorLogicSkillLoader] logic type not found: {category}")
            return None

        content = path.read_text(encoding="utf-8")
        skill = self._parse_logic_type(content, category)

        if skill:
            self._cache[cache_key] = skill

        return skill

    def load_framework(self, category: str) -> Optional[Framework]:
        """
        Load evaluation framework skill (JSON).

        Args:
            category: Logic type name (e.g., "产业趋势")

        Returns:
            Framework object or None if not found/invalid
        """
        cache_key = f"framework:{category}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        path = self.skill_dir / "logics" / category / "framework.json"
        if not path.exists():
            logger.warning(f"[SectorLogicSkillLoader] framework not found: {category}")
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            framework = Framework(**data)
            self._cache[cache_key] = framework
            logger.info(f"[SectorLogicSkillLoader] loaded framework: {category}")
            return framework

        except json.JSONDecodeError as e:
            logger.error(f"[SectorLogicSkillLoader] invalid JSON for {category}: {e}")
            return None
        except Exception as e:
            logger.error(f"[SectorLogicSkillLoader] validation error for {category}: {e}")
            return None

    def load_risk_template(self, category: str) -> Optional[RiskTemplate]:
        """
        Load risk template skill (JSON).

        Args:
            category: Logic type name (e.g., "产业趋势")

        Returns:
            RiskTemplate object or None if not found/invalid
        """
        cache_key = f"risk_template:{category}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        path = self.skill_dir / "logics" / category / "risk-template.json"
        if not path.exists():
            logger.warning(f"[SectorLogicSkillLoader] risk template not found: {category}")
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            risk_template = RiskTemplate(**data)
            self._cache[cache_key] = risk_template
            logger.info(f"[SectorLogicSkillLoader] loaded risk template: {category}")
            return risk_template

        except json.JSONDecodeError as e:
            logger.error(f"[SectorLogicSkillLoader] invalid JSON for {category}: {e}")
            return None
        except Exception as e:
            logger.error(f"[SectorLogicSkillLoader] validation error for {category}: {e}")
            return None

    def list_logic_types(self) -> List[str]:
        """
        List all available logic types.

        Returns:
            List of logic type names
        """
        logics_dir = self.skill_dir / "logics"
        if not logics_dir.exists():
            return []

        return [d.name for d in logics_dir.iterdir() if d.is_dir()]

    def list_frameworks(self) -> List[str]:
        """
        List all available frameworks.

        Returns:
            List of framework names
        """
        logics_dir = self.skill_dir / "logics"
        if not logics_dir.exists():
            return []

        return [d.name for d in logics_dir.iterdir() if (d / "framework.json").exists()]

    def list_risk_templates(self) -> List[str]:
        """
        List all available risk templates.

        Returns:
            List of risk template names
        """
        logics_dir = self.skill_dir / "logics"
        if not logics_dir.exists():
            return []

        return [d.name for d in logics_dir.iterdir() if (d / "risk-template.json").exists()]

    def load_lifecycle_config(self, config_name: str) -> Optional[Dict[str, Any]]:
        """
        Load a lifecycle configuration JSON file.

        Args:
            config_name: Config file name (e.g., "state-machine.json")

        Returns:
            Dict with config data or None if not found
        """
        cache_key = f"lifecycle:{config_name}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        path = self.skill_dir / "lifecycle" / config_name
        if not path.exists():
            logger.warning(f"[SectorLogicSkillLoader] lifecycle config not found: {config_name}")
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._cache[cache_key] = data
            return data
        except Exception as e:
            logger.error(f"[SectorLogicSkillLoader] failed to load {config_name}: {e}")
            return None

    def load_macro_config(self, config_name: str) -> Optional[Dict[str, Any]]:
        """Load a macro configuration JSON file."""
        cache_key = f"macro:{config_name}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        path = self.skill_dir / "macro" / config_name
        if not path.exists():
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._cache[cache_key] = data
            return data
        except Exception as e:
            logger.error(f"[SectorLogicSkillLoader] failed to load {config_name}: {e}")
            return None

    def load_stock_config(self, config_name: str) -> Optional[Dict[str, Any]]:
        """Load a stock configuration JSON file."""
        cache_key = f"stock:{config_name}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        path = self.skill_dir / "stock" / config_name
        if not path.exists():
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._cache[cache_key] = data
            return data
        except Exception as e:
            logger.error(f"[SectorLogicSkillLoader] failed to load {config_name}: {e}")
            return None

    def load_composite_config(self, config_name: str) -> Optional[Dict[str, Any]]:
        """Load a composite configuration JSON file."""
        cache_key = f"composite:{config_name}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        path = self.skill_dir / "composite" / config_name
        if not path.exists():
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._cache[cache_key] = data
            return data
        except Exception as e:
            logger.error(f"[SectorLogicSkillLoader] failed to load {config_name}: {e}")
            return None

    def _load_json_model(
        self,
        relative_path: str,
        model_class: Optional[type] = None,
    ) -> Optional[Any]:
        """
        Load a JSON file from the skill directory and optionally parse it with a model.

        Args:
            relative_path: Relative path within skill_dir (e.g., "lifecycle/state-machine.json")
            model_class: Optional Pydantic model or class with __init__(**kwargs) to parse into

        Returns:
            Parsed model instance or raw dict, or None if file not found/invalid
        """
        cache_key = f"json:{relative_path}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        path = self.skill_dir / relative_path
        if not path.exists():
            logger.warning(f"[SectorLogicSkillLoader] file not found: {relative_path}")
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if model_class:
                # Try to instantiate the model with the data
                try:
                    instance = model_class(**data)
                    self._cache[cache_key] = instance
                    return instance
                except Exception:
                    # Model instantiation failed, return raw dict
                    self._cache[cache_key] = data
                    return data

            self._cache[cache_key] = data
            return data

        except json.JSONDecodeError as e:
            logger.error(f"[SectorLogicSkillLoader] invalid JSON for {relative_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"[SectorLogicSkillLoader] failed to load {relative_path}: {e}")
            return None

    def clear_cache(self) -> None:
        """Clear the internal cache."""
        self._cache.clear()
        logger.info("[SectorLogicSkillLoader] cache cleared")

    def _parse_logic_type(self, content: str, category: str) -> Optional[LogicTypeSkill]:
        """
        Parse Markdown content into LogicTypeSkill.

        Extracts frontmatter and content sections.
        """
        try:
            lines = content.split("\n")

            # Extract frontmatter
            if not lines[0].strip() == "---":
                logger.error(f"[SectorLogicSkillLoader] missing frontmatter delimiter for {category}")
                return None

            frontmatter_end = 0
            for i, line in enumerate(lines[1:], start=1):
                if line.strip() == "---":
                    frontmatter_end = i
                    break

            if frontmatter_end == 0:
                logger.error(f"[SectorLogicSkillLoader] unclosed frontmatter for {category}")
                return None

            # Parse frontmatter (simple key: value extraction)
            frontmatter = {}
            for line in lines[1:frontmatter_end]:
                if ":" in line:
                    key, value = line.split(":", 1)
                    frontmatter[key.strip()] = value.strip()

            # Extract content sections
            full_content = "\n".join(lines[frontmatter_end + 1:])

            # Extract definition (核心定义 section)
            definition = self._extract_section(full_content, "核心定义")

            # Extract typical scenarios (典型场景 section)
            typical_scenarios = self._extract_list_section(full_content, "典型场景")

            # Extract duration (持续时间 section)
            duration = self._extract_section(full_content, "持续时间")

            # Extract rules (判定规则 section)
            rules = self._extract_list_section(full_content, "判定规则")

            return LogicTypeSkill(
                name=frontmatter.get("name", category),
                category="logic-type",
                version=frontmatter.get("version", "1.0"),
                definition=definition,
                typical_scenarios=typical_scenarios,
                duration=duration,
                rules=rules,
            )

        except Exception as e:
            logger.error(f"[SectorLogicSkillLoader] parse error for {category}: {e}")
            return None

    def _extract_section(self, content: str, section_name: str) -> Optional[str]:
        """Extract a section's content from Markdown."""
        lines = content.split("\n")
        in_section = False
        section_lines = []

        for line in lines:
            if line.startswith(f"## {section_name}"):
                in_section = True
                continue
            elif line.startswith("## "):
                if in_section:
                    break
            elif in_section:
                section_lines.append(line)

        return "\n".join(section_lines).strip() if section_lines else None

    def _extract_list_section(self, content: str, section_name: str) -> Optional[List[str]]:
        """Extract a list section from Markdown."""
        section_content = self._extract_section(content, section_name)
        if not section_content:
            return None

        items = []
        for line in section_content.split("\n"):
            line = line.strip()
            if line.startswith("- "):
                items.append(line[2:])
            elif line[0].isdigit() and ". " in line:
                # Handle numbered lists like "1. 必须有需求侧..."
                items.append(line.split(". ", 1)[1])

        return items if items else None
