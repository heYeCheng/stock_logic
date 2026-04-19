"""Unit tests for stock-sector mapping service.

Tests:
- StockSectorMapping model creation
- StockSectorService CRUD operations
- Affiliation strength validation
- TushareFetcher sector/concept constituent methods (mocked)
"""

import pytest
from decimal import Decimal
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.market.models import StockSectorMapping
from src.market.sector_mapping import StockSectorService


class TestStockSectorMappingModel:
    """Test StockSectorMapping model."""

    def test_create_mapping(self):
        """Test creating a basic mapping."""
        mapping = StockSectorMapping(
            stock_code="000001.SZ",
            sector_id="industry_bank",
            sector_type="industry",
            sector_name="银行",
            affiliation_strength=Decimal("1.0"),
            is_primary=True,
        )

        assert mapping.stock_code == "000001.SZ"
        assert mapping.sector_id == "industry_bank"
        assert mapping.sector_type == "industry"
        assert mapping.sector_name == "银行"
        assert mapping.affiliation_strength == Decimal("1.0")
        assert mapping.is_primary is True

    def test_mapping_repr(self):
        """Test mapping string representation."""
        mapping = StockSectorMapping(
            stock_code="000001.SZ",
            sector_id="industry_bank",
            sector_type="industry",
            sector_name="银行",
            affiliation_strength=Decimal("0.85"),
        )

        repr_str = repr(mapping)
        assert "StockSectorMapping" in repr_str
        assert "000001.SZ" in repr_str
        assert "industry_bank" in repr_str

    def test_affiliation_strength_range(self):
        """Test affiliation strength values."""
        # Valid strengths
        valid_strengths = [
            Decimal("0.50"),  # Minimum
            Decimal("0.75"),  # Middle
            Decimal("1.00"),  # Maximum
        ]
        for strength in valid_strengths:
            mapping = StockSectorMapping(
                stock_code="000001.SZ",
                sector_id="test",
                affiliation_strength=strength,
            )
            assert mapping.affiliation_strength == strength

    def test_primary_sector_flag(self):
        """Test primary sector flag."""
        primary = StockSectorMapping(
            stock_code="000001.SZ",
            sector_id="industry_bank",
            is_primary=True,
        )
        secondary = StockSectorMapping(
            stock_code="000001.SZ",
            sector_id="concept_5g",
            is_primary=False,
        )

        assert primary.is_primary is True
        assert secondary.is_primary is False


class TestAffiliationStrengthValidation:
    """Test affiliation strength validation."""

    def test_validate_valid_strength(self):
        """Test validation of valid strengths."""
        service = StockSectorService()

        # Test boundary values
        assert service.validate_affiliation_strength(Decimal("0.50")) is True
        assert service.validate_affiliation_strength(Decimal("1.00")) is True
        assert service.validate_affiliation_strength(Decimal("0.75")) is True

    def test_validate_invalid_strength(self):
        """Test validation of invalid strengths."""
        service = StockSectorService()

        # Test out of range values
        assert service.validate_affiliation_strength(Decimal("0.49")) is False
        assert service.validate_affiliation_strength(Decimal("1.01")) is False
        assert service.validate_affiliation_strength(Decimal("0.0")) is False
        assert service.validate_affiliation_strength(Decimal("2.0")) is False


@pytest.mark.asyncio
class TestStockSectorServiceCRUD:
    """Test StockSectorService CRUD operations."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock async session."""
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        session.scalar_one_or_none = AsyncMock()
        session.close = AsyncMock()
        return session

    @pytest.fixture
    def service(self):
        """Create StockSectorService instance."""
        return StockSectorService()

    async def test_update_sector_mappings(self, service, mock_session):
        """Test updating sector mappings for a stock."""
        mappings = [
            {
                "sector_id": "industry_bank",
                "sector_type": "industry",
                "sector_name": "银行",
                "affiliation_strength": Decimal("1.0"),
                "is_primary": True,
            },
            {
                "sector_id": "concept_5g",
                "sector_type": "concept",
                "sector_name": "5G 概念",
                "affiliation_strength": Decimal("0.8"),
                "is_primary": False,
            },
        ]

        mock_result = MagicMock()
        mock_session.execute.return_value = mock_result

        await service.update_sector_mappings("000001.SZ", mappings, mock_session)

        # Verify delete was called
        assert mock_session.execute.called
        # Verify commit was called
        mock_session.commit.assert_called_once()

    async def test_update_sector_mappings_invalid_strength(self, service, mock_session):
        """Test that invalid affiliation strength raises error."""
        mappings = [
            {
                "sector_id": "industry_bank",
                "sector_type": "industry",
                "affiliation_strength": Decimal("0.3"),  # Invalid: below 0.5
            },
        ]

        with pytest.raises(ValueError, match="Invalid affiliation_strength"):
            await service.update_sector_mappings("000001.SZ", mappings, mock_session)

    async def test_get_stock_sectors(self, service, mock_session):
        """Test getting all sectors for a stock."""
        mock_result = MagicMock()
        mock_scalar = MagicMock()
        mock_scalar.all.return_value = [
            StockSectorMapping(
                stock_code="000001.SZ",
                sector_id="industry_bank",
                sector_type="industry",
                sector_name="银行",
                affiliation_strength=Decimal("1.0"),
                is_primary=True,
            ),
        ]
        mock_result.scalars.return_value = mock_scalar
        mock_session.execute.return_value = mock_result

        sectors = await service.get_stock_sectors("000001.SZ", mock_session)

        assert len(sectors) == 1
        assert sectors[0].sector_id == "industry_bank"
        assert sectors[0].is_primary is True

    async def test_get_sector_stocks(self, service, mock_session):
        """Test getting all stocks in a sector."""
        mock_result = MagicMock()
        mock_scalar = MagicMock()
        mock_scalar.all.return_value = ["000001.SZ", "000002.SZ", "600000.SH"]
        mock_result.scalars.return_value = mock_scalar
        mock_session.execute.return_value = mock_result

        stocks = await service.get_sector_stocks("industry_bank", mock_session)

        assert len(stocks) == 3
        assert "000001.SZ" in stocks
        assert "000002.SZ" in stocks

    async def test_get_primary_sector(self, service, mock_session):
        """Test getting primary sector for a stock."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = StockSectorMapping(
            stock_code="000001.SZ",
            sector_id="industry_bank",
            is_primary=True,
        )
        mock_session.execute.return_value = mock_result

        primary = await service.get_primary_sector("000001.SZ", mock_session)

        assert primary is not None
        assert primary.sector_id == "industry_bank"
        assert primary.is_primary is True

    async def test_get_primary_sector_none(self, service, mock_session):
        """Test getting primary sector when none exists."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        primary = await service.get_primary_sector("000001.SZ", mock_session)

        assert primary is None

    async def test_get_max_affiliation_strength(self, service, mock_session):
        """Test getting maximum affiliation strength."""
        mock_result = MagicMock()
        mock_scalar = MagicMock()
        mock_scalar.all.return_value = [Decimal("0.8"), Decimal("1.0"), Decimal("0.6")]
        mock_result.scalars.return_value = mock_scalar
        mock_session.execute.return_value = mock_result

        max_strength = await service.get_max_affiliation_strength("000001.SZ", mock_session)

        assert max_strength == Decimal("1.0")

    async def test_get_max_affiliation_strength_no_mappings(self, service, mock_session):
        """Test getting max strength when no mappings exist."""
        mock_result = MagicMock()
        mock_scalar = MagicMock()
        mock_scalar.all.return_value = []
        mock_result.scalars.return_value = mock_scalar
        mock_session.execute.return_value = mock_result

        max_strength = await service.get_max_affiliation_strength("000001.SZ", mock_session)

        assert max_strength == Decimal("0.0")


@pytest.mark.asyncio
class TestTushareSectorConstituents:
    """Test TushareFetcher sector constituent methods."""

    @pytest.fixture
    def mock_fetcher(self):
        """Create TushareFetcher with mocked API."""
        with patch('src.data.tushare_fetcher.requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "code": 0,
                "data": {
                    "items": [
                        ["000001.SZ", "平安银行"],
                        ["000002.SZ", "万科 A"],
                        ["600000.SH", "浦发银行"],
                    ],
                    "fields": ["ts_code", "index_name"],
                },
            }
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            from src.data.tushare_fetcher import TushareFetcher
            fetcher = TushareFetcher()
            fetcher._call_api = MagicMock(return_value={
                "code": 0,
                "data": {
                    "items": [
                        ["000001.SZ", "银行"],
                        ["000002.SZ", "银行"],
                        ["600000.SH", "银行"],
                    ],
                    "fields": ["ts_code", "index_name"],
                },
            })
            return fetcher

    async def test_fetch_sector_constituents(self, mock_fetcher):
        """Test fetching industry sector constituents."""
        result = await mock_fetcher.fetch_sector_constituents("industry_bank")

        assert len(result) == 3
        assert result[0]["stock_code"] == "000001.SZ"
        assert result[0]["sector_type"] == "industry"
        assert result[0]["is_primary"] is True
        assert result[0]["affiliation_strength"] == Decimal("1.0")

    async def test_fetch_concept_constituents(self, mock_fetcher):
        """Test fetching concept sector constituents."""
        mock_fetcher._call_api = MagicMock(return_value={
            "code": 0,
            "data": {
                "items": [
                    ["000001.SZ", "5G 概念"],
                    ["000009.SZ", "5G 概念"],
                ],
                "fields": ["ts_code", "concept_name"],
            },
        })

        result = await mock_fetcher.fetch_concept_constituents("concept_5g")

        assert len(result) == 2
        assert result[0]["stock_code"] == "000001.SZ"
        assert result[0]["sector_type"] == "concept"
        assert result[0]["is_primary"] is False
        assert result[0]["affiliation_strength"] == Decimal("0.8")

    async def test_fetch_empty_sector(self, mock_fetcher):
        """Test fetching empty sector."""
        mock_fetcher._call_api = MagicMock(return_value={
            "code": 0,
            "data": {"items": [], "fields": []},
        })

        result = await mock_fetcher.fetch_sector_constituents("empty_sector")

        assert result == []

    async def test_fetch_error_returns_empty(self, mock_fetcher):
        """Test that fetch errors return empty list."""
        mock_fetcher._call_api = MagicMock(side_effect=Exception("API error"))

        result = await mock_fetcher.fetch_sector_constituents("invalid_sector")

        assert result == []
