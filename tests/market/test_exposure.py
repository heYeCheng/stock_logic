"""Unit tests for exposure coefficient calculation.

Tests:
- ExposureCalculator.calculate_exposure() - single stock-logic pair
- ExposureCalculator.calculate_batch_exposure() - batch calculation
- Edge cases: empty keywords, no sector mappings, zero overlap
- Affiliation strength weighting
- Keyword overlap calculations
"""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from src.market.exposure import ExposureCalculator, ExposureQueries
from src.market.models import StockSectorMapping
from src.logic.models import LogicModel


class TestExposureCalculatorSingle:
    """Test single stock-logic exposure calculation."""

    def test_full_keyword_match(self):
        """Test exposure with 100% keyword match."""
        calculator = ExposureCalculator()

        stock_keywords = {"5G", "communication", "telecom"}
        logic_keywords = {"5G", "communication", "telecom"}

        sector_affiliations = [
            StockSectorMapping(
                stock_code="000001.SZ",
                sector_id="concept_5g",
                sector_type="concept",
                affiliation_strength=Decimal("0.8"),
            ),
        ]

        exposure = calculator.calculate_exposure(
            stock_keywords,
            sector_affiliations,
            logic_keywords,
        )

        # logic_match_score = 3/3 = 1.0
        # exposure = 0.8 * 1.0 = 0.8
        assert exposure == Decimal("0.8")

    def test_partial_keyword_match(self):
        """Test exposure with partial keyword match."""
        calculator = ExposureCalculator()

        stock_keywords = {"5G", "communication", "telecom"}
        logic_keywords = {"5G", "AI", "cloud"}

        sector_affiliations = [
            StockSectorMapping(
                stock_code="000001.SZ",
                sector_id="concept_5g",
                sector_type="concept",
                affiliation_strength=Decimal("1.0"),
            ),
        ]

        exposure = calculator.calculate_exposure(
            stock_keywords,
            sector_affiliations,
            logic_keywords,
        )

        # logic_match_score = 1/3 = 0.333...
        # exposure = 1.0 * 0.333... = 0.333...
        assert abs(float(exposure) - 0.333333) < 0.001

    def test_no_keyword_match(self):
        """Test exposure with zero keyword overlap."""
        calculator = ExposureCalculator()

        stock_keywords = {"bank", "finance", "insurance"}
        logic_keywords = {"5G", "AI", "cloud"}

        sector_affiliations = [
            StockSectorMapping(
                stock_code="000001.SZ",
                sector_id="industry_bank",
                sector_type="industry",
                affiliation_strength=Decimal("1.0"),
            ),
        ]

        exposure = calculator.calculate_exposure(
            stock_keywords,
            sector_affiliations,
            logic_keywords,
        )

        # logic_match_score = 0/3 = 0
        # exposure = 1.0 * 0 = 0
        assert exposure == Decimal("0")

    def test_no_sector_mappings(self):
        """Test exposure when stock has no sector mappings."""
        calculator = ExposureCalculator()

        stock_keywords = {"5G", "communication"}
        logic_keywords = {"5G", "communication"}

        exposure = calculator.calculate_exposure(
            stock_keywords,
            [],  # No sector mappings
            logic_keywords,
        )

        # max_affiliation = 0
        # exposure = 0 * 1.0 = 0
        assert exposure == Decimal("0")

    def test_empty_stock_keywords(self):
        """Test exposure when stock has no keywords."""
        calculator = ExposureCalculator()

        stock_keywords = set()
        logic_keywords = {"5G", "AI"}

        sector_affiliations = [
            StockSectorMapping(
                stock_code="000001.SZ",
                sector_id="concept_5g",
                affiliation_strength=Decimal("0.8"),
            ),
        ]

        exposure = calculator.calculate_exposure(
            stock_keywords,
            sector_affiliations,
            logic_keywords,
        )

        # logic_match_score = 0 (empty stock keywords)
        assert exposure == Decimal("0")

    def test_empty_logic_keywords(self):
        """Test exposure when logic has no keywords."""
        calculator = ExposureCalculator()

        stock_keywords = {"5G", "AI"}
        logic_keywords = set()

        sector_affiliations = [
            StockSectorMapping(
                stock_code="000001.SZ",
                sector_id="concept_5g",
                affiliation_strength=Decimal("0.8"),
            ),
        ]

        exposure = calculator.calculate_exposure(
            stock_keywords,
            sector_affiliations,
            logic_keywords,
        )

        # logic_match_score = 0 (empty logic keywords)
        assert exposure == Decimal("0")

    def test_multiple_sector_mappings_max_strength(self):
        """Test exposure uses max affiliation strength across multiple sectors."""
        calculator = ExposureCalculator()

        stock_keywords = {"5G", "communication"}
        logic_keywords = {"5G", "communication"}

        sector_affiliations = [
            StockSectorMapping(
                stock_code="000001.SZ",
                sector_id="industry_telecom",
                sector_type="industry",
                affiliation_strength=Decimal("0.7"),
            ),
            StockSectorMapping(
                stock_code="000001.SZ",
                sector_id="concept_5g",
                sector_type="concept",
                affiliation_strength=Decimal("1.0"),  # Max strength
            ),
            StockSectorMapping(
                stock_code="000001.SZ",
                sector_id="concept_iot",
                sector_type="concept",
                affiliation_strength=Decimal("0.6"),
            ),
        ]

        exposure = calculator.calculate_exposure(
            stock_keywords,
            sector_affiliations,
            logic_keywords,
        )

        # max_affiliation = 1.0 (max of 0.7, 1.0, 0.6)
        # logic_match_score = 2/2 = 1.0
        # exposure = 1.0 * 1.0 = 1.0
        assert exposure == Decimal("1.0")

    def test_exposure_capped_at_one(self):
        """Test exposure is capped at 1.0."""
        calculator = ExposureCalculator()

        stock_keywords = {"5G", "AI", "cloud", "tech"}
        logic_keywords = {"5G", "AI"}  # All logic keywords match

        sector_affiliations = [
            StockSectorMapping(
                stock_code="000001.SZ",
                sector_id="concept_5g",
                affiliation_strength=Decimal("1.0"),
            ),
        ]

        exposure = calculator.calculate_exposure(
            stock_keywords,
            sector_affiliations,
            logic_keywords,
        )

        # max_affiliation = 1.0
        # logic_match_score = 2/2 = 1.0
        # exposure = 1.0 * 1.0 = 1.0 (capped)
        assert exposure == Decimal("1.0")

    def test_affiliation_strength_weighting(self):
        """Test different affiliation strength values affect exposure."""
        calculator = ExposureCalculator()

        stock_keywords = {"5G"}
        logic_keywords = {"5G"}

        # Test with different strengths
        strengths = [
            (Decimal("0.5"), Decimal("0.5")),  # Minimum strength
            (Decimal("0.75"), Decimal("0.75")),  # Medium strength
            (Decimal("1.0"), Decimal("1.0")),  # Maximum strength
        ]

        for strength, expected_exposure in strengths:
            sector_affiliations = [
                StockSectorMapping(
                    stock_code="000001.SZ",
                    sector_id="concept_5g",
                    affiliation_strength=strength,
                ),
            ]

            exposure = calculator.calculate_exposure(
                stock_keywords,
                sector_affiliations,
                logic_keywords,
            )

            assert exposure == expected_exposure


class TestExposureCalculatorBatch:
    """Test batch exposure calculation."""

    def test_batch_exposure_two_stocks_two_logics(self):
        """Test batch calculation for 2 stocks and 2 logics."""
        calculator = ExposureCalculator()

        stock_keywords_map = {
            "000001.SZ": {"5G", "communication"},
            "000002.SZ": {"bank", "finance"},
        }

        sector_mappings_map = {
            "000001.SZ": [
                StockSectorMapping(
                    stock_code="000001.SZ",
                    sector_id="concept_5g",
                    affiliation_strength=Decimal("0.8"),
                ),
            ],
            "000002.SZ": [
                StockSectorMapping(
                    stock_code="000002.SZ",
                    sector_id="industry_bank",
                    affiliation_strength=Decimal("1.0"),
                ),
            ],
        }

        logics = [
            LogicModel(
                logic_id="logic_5g_001",
                logic_name="5G Development",
                logic_family="technology",
                keywords=["5G", "communication"],
            ),
            LogicModel(
                logic_id="logic_finance_001",
                logic_name="Financial Reform",
                logic_family="policy",
                keywords=["bank", "finance"],
            ),
        ]

        result = calculator.calculate_batch_exposure(
            stock_keywords_map,
            sector_mappings_map,
            logics,
        )

        # Check structure
        assert len(result) == 2
        assert "000001.SZ" in result
        assert "000002.SZ" in result

        # 000001.SZ: 5G stock
        assert result["000001.SZ"]["logic_5g_001"] == Decimal("0.8")  # 0.8 * 1.0
        assert result["000001.SZ"]["logic_finance_001"] == Decimal("0")  # No match

        # 000002.SZ: Bank stock
        assert result["000002.SZ"]["logic_5g_001"] == Decimal("0")  # No match
        assert result["000002.SZ"]["logic_finance_001"] == Decimal("1.0")  # 1.0 * 1.0

    def test_batch_exposure_empty_stock_keywords(self):
        """Test batch calculation with empty stock keywords."""
        calculator = ExposureCalculator()

        stock_keywords_map = {
            "000001.SZ": set(),  # No keywords
        }

        sector_mappings_map = {
            "000001.SZ": [
                StockSectorMapping(
                    stock_code="000001.SZ",
                    sector_id="concept_5g",
                    affiliation_strength=Decimal("0.8"),
                ),
            ],
        }

        logics = [
            LogicModel(
                logic_id="logic_5g_001",
                logic_name="5G Development",
                logic_family="technology",
                keywords=["5G"],
            ),
        ]

        result = calculator.calculate_batch_exposure(
            stock_keywords_map,
            sector_mappings_map,
            logics,
        )

        assert result["000001.SZ"]["logic_5g_001"] == Decimal("0")

    def test_batch_exposure_no_sector_mappings(self):
        """Test batch calculation when stock has no sector mappings."""
        calculator = ExposureCalculator()

        stock_keywords_map = {
            "000001.SZ": {"5G"},
        }

        sector_mappings_map = {}  # No mappings for this stock

        logics = [
            LogicModel(
                logic_id="logic_5g_001",
                logic_name="5G Development",
                logic_family="technology",
                keywords=["5G"],
            ),
        ]

        result = calculator.calculate_batch_exposure(
            stock_keywords_map,
            sector_mappings_map,
            logics,
        )

        assert result["000001.SZ"]["logic_5g_001"] == Decimal("0")

    def test_batch_exposure_logic_no_keywords(self):
        """Test batch calculation when logic has no keywords."""
        calculator = ExposureCalculator()

        stock_keywords_map = {
            "000001.SZ": {"5G"},
        }

        sector_mappings_map = {
            "000001.SZ": [
                StockSectorMapping(
                    stock_code="000001.SZ",
                    sector_id="concept_5g",
                    affiliation_strength=Decimal("0.8"),
                ),
            ],
        }

        logics = [
            LogicModel(
                logic_id="logic_empty",
                logic_name="Empty Logic",
                logic_family="test",
                keywords=None,  # No keywords
            ),
        ]

        result = calculator.calculate_batch_exposure(
            stock_keywords_map,
            sector_mappings_map,
            logics,
        )

        assert result["000001.SZ"]["logic_empty"] == Decimal("0")


@pytest.mark.asyncio
class TestExposureQueries:
    """Test exposure query methods."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock async session."""
        session = AsyncMock()
        session.execute = AsyncMock()
        session.scalar_one_or_none = AsyncMock()
        session.close = AsyncMock()
        return session

    async def test_get_stock_exposures(self, mock_session):
        """Test getting all logic exposures for a stock."""
        from datetime import date

        mock_result = MagicMock()
        mock_scalar = MagicMock()

        # Mock exposure records
        exposure1 = MagicMock()
        exposure1.logic_id = "logic_5g_001"
        exposure1.exposure_coefficient = Decimal("0.8")

        exposure2 = MagicMock()
        exposure2.logic_id = "logic_ai_001"
        exposure2.exposure_coefficient = Decimal("0.5")

        mock_scalar.all.return_value = [exposure1, exposure2]
        mock_result.scalars.return_value = mock_scalar
        mock_session.execute.return_value = mock_result

        from src.market.exposure import ExposureQueries

        exposures = await ExposureQueries.get_stock_exposures(
            "000001.SZ",
            date(2026, 4, 19),
            mock_session,
        )

        assert len(exposures) == 2
        assert exposures["logic_5g_001"] == Decimal("0.8")
        assert exposures["logic_ai_001"] == Decimal("0.5")

    async def test_get_logic_exposed_stocks(self, mock_session):
        """Test getting stocks with significant exposure to a logic."""
        from datetime import date

        mock_result = MagicMock()
        mock_scalar = MagicMock()
        mock_scalar.all.return_value = ["000001.SZ", "000002.SZ"]
        mock_result.scalars.return_value = mock_scalar
        mock_session.execute.return_value = mock_result

        from src.market.exposure import ExposureQueries

        stocks = await ExposureQueries.get_logic_exposed_stocks(
            "logic_5g_001",
            date(2026, 4, 19),
            min_exposure=Decimal("0.3"),
            session=mock_session,
        )

        assert len(stocks) == 2
        assert "000001.SZ" in stocks
        assert "000002.SZ" in stocks

    async def test_get_max_exposure_stock(self, mock_session):
        """Test getting stock with highest exposure."""
        from datetime import date

        mock_result = MagicMock()

        max_exposure = MagicMock()
        max_exposure.stock_code = "000001.SZ"
        max_exposure.exposure_coefficient = Decimal("0.95")

        mock_result.scalar_one_or_none.return_value = max_exposure
        mock_session.execute.return_value = mock_result

        from src.market.exposure import ExposureQueries

        stock = await ExposureQueries.get_max_exposure_stock(
            "logic_5g_001",
            date(2026, 4, 19),
            mock_session,
        )

        assert stock == "000001.SZ"

    async def test_get_max_exposure_stock_none(self, mock_session):
        """Test getting max exposure stock when no data exists."""
        from datetime import date

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        from src.market.exposure import ExposureQueries

        stock = await ExposureQueries.get_max_exposure_stock(
            "logic_nonexistent",
            date(2026, 4, 19),
            mock_session,
        )

        assert stock is None
