# -*- coding: utf-8 -*-
"""
EventScoreboard: L1 event-driven logic scoring for Phase 0.5.

Rule-engine calculates logic strength from events — LLM never assigns scores.
Supports event deduplication, validity windows, and decay.
"""

import hashlib
import logging
import re
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def normalize_text(text: str) -> str:
    """Normalize text for dedup: full-width→half-width, remove punctuation, lowercase."""
    if not text:
        return ""
    # Full-width to half-width
    result = []
    for ch in text:
        code = ord(ch)
        if 0xFF01 <= code <= 0xFF5E:
            result.append(chr(code - 0xFEE0))
        elif code == 0x3000:
            result.append(' ')
        else:
            result.append(ch)
    text = ''.join(result)
    # Remove punctuation and lowercase
    text = re.sub(r'[^\w\s]', '', text)
    return text.lower()


def edit_distance(s1: str, s2: str) -> int:
    """Levenshtein distance."""
    if len(s1) < len(s2):
        return edit_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)

    prev_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (c1 != c2)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row

    return prev_row[-1]


def compute_event_hash(logic_id: str, event_date: date, event_type: str, summary: str) -> str:
    """Compute deterministic event hash for dedup."""
    content = f"{logic_id}|{event_date}|{event_type}|{summary[:20]}"
    return hashlib.sha256(content.encode()).hexdigest()


class EventScoreboard:
    """
    L1 Event Scoreboard (Phase 0.5).

    Calculates logic strength from events using rule engine.
    """

    def __init__(self, event_repo, logic_repo, anchor_loader=None, llm_client=None):
        self.event_repo = event_repo
        self.logic_repo = logic_repo
        self.anchor_loader = anchor_loader
        self.llm_client = llm_client
        self._anchor_cache = {}

    def _get_anchor(self, key: str) -> dict:
        if key not in self._anchor_cache:
            if self.anchor_loader:
                self._anchor_cache[key] = self.anchor_loader.load(key)
            else:
                self._anchor_cache[key] = {}
        return self._anchor_cache[key]

    def add_event(self, logic_id: str, event_type: str, direction: str,
                  summary: str, event_date: date) -> bool:
        """
        Add an event with deduplication. Returns True if inserted.
        """
        # Normalize and check edit distance
        normalized = normalize_text(summary)
        threshold = 5 if len(normalized) >= 10 else 2

        # Check existing events for edit distance dedup
        existing_events = self.event_repo.get_events_by_date_range(
            logic_id, event_date, event_date
        )
        for existing in existing_events:
            if existing.event_type == event_type:
                existing_normalized = normalize_text(existing.summary)
                if edit_distance(normalized, existing_normalized) < threshold:
                    logger.debug(f"[EventScoreboard] Edit distance dedup: {summary[:30]}")
                    return False

        # Compute hash
        event_hash = compute_event_hash(logic_id, event_date, event_type, summary)

        # Look up score_impact and validity from anchors
        event_config = self._get_event_config(event_type, direction)
        if event_config is None:
            logger.warning(f"[EventScoreboard] Unknown event_type: {event_type}")
            return False

        score_impact = event_config['score_impact']
        validity_days = event_config['validity_days']
        expire_date = event_date + timedelta(days=validity_days)

        # Insert
        inserted = self.event_repo.add_event(
            logic_id=logic_id,
            event_type=event_type,
            direction=direction,
            score_impact=score_impact,
            event_date=event_date,
            expire_date=expire_date,
            summary=summary,
            event_hash=event_hash,
        )

        if inserted and self.logic_repo:
            self.logic_repo.update_last_event(logic_id, event_date)

        return inserted

    def _get_event_config(self, event_type: str, direction: str) -> Optional[dict]:
        """Look up event config from anchors."""
        anchor = self._get_anchor('event_qualitative.yaml')
        events_dict = anchor.get('positive_events' if direction == 'positive' else 'negative_events', {})
        return events_dict.get(event_type)

    def calculate_strength(self, logic_id: str, current_date: date = None) -> float:
        """
        Calculate logic strength via daily full recalculation.

        strength = initial_strength + Σ(valid_event_impacts) - Σ(decay_steps × decay_rate)
        Clamped to [0.15, 0.95].
        """
        if current_date is None:
            current_date = date.today()

        if not self.logic_repo:
            return 0.5

        logic = self.logic_repo.get_by_id(logic_id)
        if not logic:
            return 0.5

        # Get valid events
        valid_events = self.event_repo.get_valid_events(logic_id, current_date)

        # Sum valid event impacts
        event_sum = sum(e.score_impact for e in valid_events)

        # Calculate decay
        decay_amount = self._calculate_decay(logic, current_date)

        # Final strength
        strength = logic.initial_strength + event_sum - decay_amount
        strength = max(0.15, min(0.95, strength))

        # Update in repo
        self.logic_repo.update_strength(logic_id, strength)
        return round(strength, 4)

    def _calculate_decay(self, logic, current_date: date) -> float:
        """
        Calculate decay based on trading days without new events.

        Sliding window from last_event_date.
        """
        if not logic.last_event_date:
            return 0.0

        # Get category decay config
        category_anchor = self._get_anchor('logic_category.yaml')
        categories = category_anchor.get('categories', {})
        cat_config = categories.get(logic.category, {'decay_per_period': 0.02, 'period_days': 10})

        decay_per_period = cat_config['decay_per_period']
        period_days = cat_config['period_days']

        # Count days since last event
        days_since = (current_date - logic.last_event_date).days
        # Approximate trading days: ~5/7 of calendar days
        trading_days_since = int(days_since * 5 / 7)

        if trading_days_since < period_days:
            return 0.0

        decay_periods = trading_days_since // period_days
        return decay_periods * decay_per_period

    def daily_recalculate(self, current_date: date = None) -> Dict[str, float]:
        """Recalculate strengths for all active logics."""
        if current_date is None:
            current_date = date.today()

        if not self.logic_repo:
            return {}

        # Get all active logics
        all_logics = self.logic_repo.get_by_sector('')  # Get all if sector_code is empty
        results = {}

        # If get_by_sector('') doesn't work, we need a get_all method
        # For now, use calculate_strength per logic_id from events
        from src.storage import engine
        from src.sector_logic.db_schema import LogicModel
        from sqlalchemy import select
        from sqlalchemy.orm import Session

        with Session(engine) as session:
            stmt = select(LogicModel).where(LogicModel.is_active == True)
            logics = session.scalars(stmt).all()

        for logic in logics:
            strength = self.calculate_strength(logic.logic_id, current_date)
            results[logic.logic_id] = strength

        logger.info(f"[EventScoreboard] Recalculated {len(results)} logic strengths")
        return results

    def extract_events(self, sector_code: str, news_items: List[str],
                       active_logics: List[dict]) -> int:
        """
        Extract events from news via LLM and associate to logics.

        Phase 0.5: keyword matching — if event summary contains logic title keywords, associate.

        Returns: count of events added
        """
        if not self.llm_client:
            logger.warning("[EventScoreboard] No LLM client, cannot extract events")
            return 0

        # Build event types string from anchors
        anchor = self._get_anchor('event_qualitative.yaml')
        event_types = " / ".join(list(anchor.get('positive_events', {}).keys()) +
                                  list(anchor.get('negative_events', {}).keys()))

        news_text = "\n".join(f"- {item}" for item in news_items)
        prompt = f"""基于以下新闻/公告/数据摘要，提取与板块 {sector_code} 相关的结构化事件：

输入信息：{news_text}

对每条相关信息，输出：
1. event_type: "{event_types}" 或 "其他"
2. direction: "positive" 或 "negative"
3. summary: 一句话摘要（不超过50字）
4. event_date: 事件日期（YYYY-MM-DD）

输出严格JSON数组。"""

        try:
            import json
            if hasattr(self.llm_client, 'chat'):
                import asyncio
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Running in async context
                    async def _chat():
                        return await self.llm_client.chat(
                            messages=[{"role": "user", "content": prompt}],
                            response_format={"type": "json_object"},
                        )
                    response = loop.run_until_complete(_chat())
                else:
                    response = asyncio.run(self.llm_client.chat(
                        messages=[{"role": "user", "content": prompt}],
                        response_format={"type": "json_object"},
                    ))
                raw_text = response.get("content", "")
            else:
                return 0

            raw_text = raw_text.strip()
            if raw_text.startswith("```"):
                raw_text = raw_text.split("```json", 1)[-1].split("```")[0].strip()

            events = json.loads(raw_text)
            if not isinstance(events, list):
                events = [events]

            added = 0
            for event in events:
                event_type = event.get('event_type', '其他')
                direction = event.get('direction', 'positive')
                summary = event.get('summary', '')
                event_date_str = event.get('event_date', '')

                if not summary or not event_date_str:
                    continue

                try:
                    event_date = date.fromisoformat(event_date_str)
                except ValueError:
                    continue

                # Associate to logic via keyword matching (Phase 0.5)
                associated_logic_id = None
                for logic in active_logics:
                    title_keywords = logic.get('title', '')
                    if any(kw in summary for kw in title_keywords.split()):
                        associated_logic_id = logic['logic_id']
                        break

                if associated_logic_id:
                    if self.add_event(associated_logic_id, event_type, direction, summary, event_date):
                        added += 1
                else:
                    logger.debug(f"[EventScoreboard] Event not associated to any logic: {summary[:30]}")

            return added

        except Exception as e:
            logger.error(f"[EventScoreboard] Event extraction failed: {e}")
            return 0
