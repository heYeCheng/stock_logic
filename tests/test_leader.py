"""Unit tests for leader identification service."""

import pytest
from decimal import Decimal

from src.market.leader import LeaderIdentificationService, LeaderRole


class TestDragonScoreCalculation:
    """Test dragon leader score calculation."""

    def setup_method(self):
        self.service = LeaderIdentificationService()

    def test_dragon_score_with_limit_ups(self):
        """Dragon score calculation with limit-ups."""
        # 3 limit-ups, no consecutive gains, not first limit
        score = self.service.calculate_dragon_score(
            limit_up_count=3,
            consecutive_gains=0,
            is_first_limit=False,
        )
        # 3 * 2 + 0 + 0 = 6
        assert score == Decimal("6")

    def test_dragon_score_with_consecutive_gains(self):
        """Dragon score calculation with consecutive gains."""
        score = self.service.calculate_dragon_score(
            limit_up_count=0,
            consecutive_gains=4,
            is_first_limit=False,
        )
        # 0 * 2 + 4 + 0 = 4
        assert score == Decimal("4")

    def test_dragon_score_with_first_limit_bonus(self):
        """Dragon score includes first-to-limit bonus."""
        score = self.service.calculate_dragon_score(
            limit_up_count=2,
            consecutive_gains=1,
            is_first_limit=True,
        )
        # 2 * 2 + 1 + 3 = 8
        assert score == Decimal("8")

    def test_dragon_score_zero_inputs(self):
        """Dragon score with zero inputs."""
        score = self.service.calculate_dragon_score(
            limit_up_count=0,
            consecutive_gains=0,
            is_first_limit=False,
        )
        assert score == Decimal("0")


class TestZhongjunScoreCalculation:
    """Test zhongjun (anchor) score calculation."""

    def setup_method(self):
        self.service = LeaderIdentificationService()

    def test_zhongjun_score_market_cap_rank(self):
        """Zhongjun score with market cap rank."""
        # Rank 1 (largest) in sector of 10 stocks
        score = self.service.calculate_zhongjun_score(
            market_cap_rank=1,
            volume_stability=0.5,
            trend_consistency=0.5,
            sector_stocks_count=10,
        )
        # cap_score = (10-1+1)/10 * 3 = 3.0
        # volume_score = 0.5 * 2 = 1.0
        # trend_score = 0.5 * 2 = 1.0
        # total = 5.0
        assert score == Decimal("5.0")

    def test_zhongjun_score_low_rank(self):
        """Zhongjun score with low market cap rank (small cap)."""
        # Rank 10 (smallest) in sector of 10 stocks
        score = self.service.calculate_zhongjun_score(
            market_cap_rank=10,
            volume_stability=0.5,
            trend_consistency=0.5,
            sector_stocks_count=10,
        )
        # cap_score = (10-10+1)/10 * 3 = 0.3
        # volume_score = 0.5 * 2 = 1.0
        # trend_score = 0.5 * 2 = 1.0
        # total = 2.3
        assert score == Decimal("2.3")

    def test_zhongjun_score_high_stability(self):
        """Zhongjun score with high volume stability and trend consistency."""
        score = self.service.calculate_zhongjun_score(
            market_cap_rank=5,
            volume_stability=0.9,
            trend_consistency=0.9,
            sector_stocks_count=10,
        )
        # cap_score = (10-5+1)/10 * 3 = 1.8
        # volume_score = 0.9 * 2 = 1.8
        # trend_score = 0.9 * 2 = 1.8
        # total = 5.4
        assert score == Decimal("5.4")

    def test_zhongjun_score_no_rank(self):
        """Zhongjun score when market cap rank is None."""
        score = self.service.calculate_zhongjun_score(
            market_cap_rank=None,
            volume_stability=0.5,
            trend_consistency=0.5,
            sector_stocks_count=10,
        )
        # cap_score = 0 (no rank data)
        # volume_score = 0.5 * 2 = 1.0
        # trend_score = 0.5 * 2 = 1.0
        # total = 2.0
        assert score == Decimal("2.0")


class TestRoleIdentification:
    """Test role identification based on scores."""

    def setup_method(self):
        self.service = LeaderIdentificationService()

    def test_role_dragon_above_threshold(self):
        """Dragon role when score above threshold."""
        role, dragon_score, zhongjun_score = self.service.identify_role(
            dragon_score=Decimal("6.0"),
            zhongjun_score=Decimal("2.0"),
        )
        assert role == LeaderRole.dragon
        assert dragon_score == Decimal("6.0")

    def test_role_zhongjun_above_threshold(self):
        """Zhongjun role when score above threshold."""
        role, dragon_score, zhongjun_score = self.service.identify_role(
            dragon_score=Decimal("3.0"),
            zhongjun_score=Decimal("5.0"),
        )
        assert role == LeaderRole.zhongjun
        assert zhongjun_score == Decimal("5.0")

    def test_role_follower_below_thresholds(self):
        """Follower role when both scores below thresholds."""
        role, dragon_score, zhongjun_score = self.service.identify_role(
            dragon_score=Decimal("4.0"),
            zhongjun_score=Decimal("2.0"),
        )
        assert role == LeaderRole.follower

    def test_role_dragon_priority_over_zhongjun(self):
        """Dragon takes priority when both above threshold."""
        role, dragon_score, zhongjun_score = self.service.identify_role(
            dragon_score=Decimal("6.0"),
            zhongjun_score=Decimal("5.0"),
        )
        assert role == LeaderRole.dragon

    def test_role_at_exact_threshold(self):
        """Role at exact threshold boundary."""
        # Exactly at dragon threshold
        role, _, _ = self.service.identify_role(
            dragon_score=Decimal("5.0"),
            zhongjun_score=Decimal("2.0"),
        )
        assert role == LeaderRole.dragon

        # Exactly at zhongjun threshold
        role, _, _ = self.service.identify_role(
            dragon_score=Decimal("4.0"),
            zhongjun_score=Decimal("3.0"),
        )
        assert role == LeaderRole.zhongjun


class TestConfidenceCalculation:
    """Test confidence calculation for role assignment."""

    def setup_method(self):
        self.service = LeaderIdentificationService()

    def test_confidence_dragon_above_threshold(self):
        """Confidence for dragon role above threshold."""
        confidence = self.service.calculate_confidence(
            role=LeaderRole.dragon,
            dragon_score=Decimal("7.5"),
            zhongjun_score=Decimal("2.0"),
        )
        # (7.5 - 5.0) / 5.0 = 0.5
        assert confidence == 0.5

    def test_confidence_dragon_at_threshold(self):
        """Confidence for dragon role at threshold."""
        confidence = self.service.calculate_confidence(
            role=LeaderRole.dragon,
            dragon_score=Decimal("5.0"),
            zhongjun_score=Decimal("2.0"),
        )
        # (5.0 - 5.0) / 5.0 = 0.0
        assert confidence == 0.0

    def test_confidence_zhongjun_above_threshold(self):
        """Confidence for zhongjun role above threshold."""
        confidence = self.service.calculate_confidence(
            role=LeaderRole.zhongjun,
            dragon_score=Decimal("3.0"),
            zhongjun_score=Decimal("4.5"),
        )
        # (4.5 - 3.0) / 3.0 = 0.5
        assert confidence == 0.5

    def test_confidence_follower(self):
        """Confidence for follower role."""
        confidence = self.service.calculate_confidence(
            role=LeaderRole.follower,
            dragon_score=Decimal("3.0"),
            zhongjun_score=Decimal("1.0"),
        )
        # dragon_dist = 5.0 - 3.0 = 2.0
        # zhongjun_dist = 3.0 - 1.0 = 2.0
        # min(2.0, 2.0) / 5.0 = 0.4
        assert confidence == 0.4

    def test_confidence_capped_at_one(self):
        """Confidence capped at 1.0 for very high scores."""
        confidence = self.service.calculate_confidence(
            role=LeaderRole.dragon,
            dragon_score=Decimal("15.0"),
            zhongjun_score=Decimal("2.0"),
        )
        # (15.0 - 5.0) / 5.0 = 2.0, but capped at 1.0
        assert confidence == 1.0


class TestLeaderIdentificationIntegration:
    """Integration tests for full identification flow."""

    def setup_method(self):
        self.service = LeaderIdentificationService()

    def test_full_flow_dragon_leader(self):
        """Full flow: strong dragon leader."""
        # Stock with 3 limit-ups, 2 consecutive gains, first to limit
        dragon_score = self.service.calculate_dragon_score(
            limit_up_count=3,
            consecutive_gains=2,
            is_first_limit=True,
        )
        zhongjun_score = self.service.calculate_zhongjun_score(
            market_cap_rank=3,
            volume_stability=0.6,
            trend_consistency=0.6,
            sector_stocks_count=10,
        )

        role, _, _ = self.service.identify_role(dragon_score, zhongjun_score)
        confidence = self.service.calculate_confidence(role, dragon_score, zhongjun_score)

        assert role == LeaderRole.dragon
        assert dragon_score == Decimal("11")  # 3*2 + 2 + 3
        assert confidence > 0

    def test_full_flow_zhongjun_anchor(self):
        """Full flow: stable zhongjun anchor."""
        # Stock with no limit-ups, but large cap (rank 1), high stability
        dragon_score = self.service.calculate_dragon_score(
            limit_up_count=0,
            consecutive_gains=0,
            is_first_limit=False,
        )
        zhongjun_score = self.service.calculate_zhongjun_score(
            market_cap_rank=1,
            volume_stability=0.8,
            trend_consistency=0.8,
            sector_stocks_count=10,
        )

        role, _, _ = self.service.identify_role(dragon_score, zhongjun_score)
        confidence = self.service.calculate_confidence(role, dragon_score, zhongjun_score)

        assert role == LeaderRole.zhongjun
        assert zhongjun_score == Decimal("6.2")  # 3.0 + 1.6 + 1.6
        assert confidence > 0

    def test_full_flow_follower(self):
        """Full flow: typical follower."""
        # Stock with weak dragon and zhongjun metrics
        dragon_score = self.service.calculate_dragon_score(
            limit_up_count=0,
            consecutive_gains=1,
            is_first_limit=False,
        )
        zhongjun_score = self.service.calculate_zhongjun_score(
            market_cap_rank=8,
            volume_stability=0.3,
            trend_consistency=0.3,
            sector_stocks_count=10,
        )

        role, _, _ = self.service.identify_role(dragon_score, zhongjun_score)
        confidence = self.service.calculate_confidence(role, dragon_score, zhongjun_score)

        assert role == LeaderRole.follower
        assert dragon_score == Decimal("1")
        # cap_score = (10-8+1)/10 * 3 = 0.9
        # volume_score = 0.3 * 2 = 0.6
        # trend_score = 0.3 * 2 = 0.6
        # total = 2.1
        assert zhongjun_score == Decimal("2.1")
