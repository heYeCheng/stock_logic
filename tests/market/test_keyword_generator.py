"""Unit tests for keyword generator module.

Tests:
- KeywordGenerator prompt building
- KeywordGenerator JSON parsing (valid response)
- KeywordGenerator JSON parsing (malformed response)
- Keyword count validation (5-8 keywords)
- SectorKeywordService CRUD operations
- Scheduler integration
"""

import pytest
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from src.market.keyword_generator import (
    KeywordGenerator,
    SectorKeywordService,
    generate_sector_keywords_job,
)
from src.market.models import SectorKeywords


class TestKeywordGeneratorPromptBuilding:
    """Test prompt building for keyword generation."""

    def test_build_prompt_basic(self):
        """Test basic prompt with sector name and stocks."""
        generator = KeywordGenerator()

        prompt = generator._build_prompt(
            sector_name="5G 概念",
            sector_stocks=["中兴通讯", "立讯精密", "工业富联"],
            description=None,
        )

        assert "5G 概念" in prompt
        assert "中兴通讯" in prompt
        assert "立讯精密" in prompt
        assert "工业富联" in prompt
        assert "5-8 个关键词" in prompt
        assert "JSON" in prompt

    def test_build_prompt_with_description(self):
        """Test prompt with sector description."""
        generator = KeywordGenerator()

        prompt = generator._build_prompt(
            sector_name="新能源汽车",
            sector_stocks=["比亚迪", "宁德时代"],
            description="专注于新能源汽车及电池制造",
        )

        assert "新能源汽车" in prompt
        assert "比亚迪" in prompt
        assert "专注于新能源汽车及电池制造" in prompt

    def test_build_prompt_limits_stocks(self):
        """Test that prompt limits stocks to 10."""
        generator = KeywordGenerator()

        # Create 15 stocks
        stocks = [f"股票{i}" for i in range(15)]

        prompt = generator._build_prompt(
            sector_name="测试板块",
            sector_stocks=stocks,
            description=None,
        )

        # Should only include first 10 (股票 0 to 股票 9)
        # Verify all included stocks are present
        for i in range(10):
            assert f"股票{i}" in prompt, f"股票{i} should be in prompt"

        # Verify stocks 10-14 are NOT included
        for i in range(10, 15):
            assert f"股票{i}" not in prompt, f"股票{i} should NOT be in prompt"


class TestKeywordGeneratorJsonParsing:
    """Test JSON parsing from LLM responses."""

    def test_parse_valid_json(self):
        """Test parsing valid JSON response."""
        generator = KeywordGenerator()

        response = '{"keywords": ["关键词 1", "关键词 2", "关键词 3", "关键词 4", "关键词 5"]}'
        keywords = generator._parse_keywords(response)

        assert len(keywords) == 5
        assert "关键词 1" in keywords
        assert "关键词 5" in keywords

    def test_parse_json_with_surrounding_text(self):
        """Test parsing JSON embedded in text."""
        generator = KeywordGenerator()

        response = """好的，这是为您生成的关键词：
        {
            "keywords": ["关键词 1", "关键词 2", "关键词 3", "关键词 4", "关键词 5", "关键词 6"]
        }
        希望这些关键词能帮助到您。"""

        keywords = generator._parse_keywords(response)

        assert len(keywords) == 6

    def test_parse_truncates_more_than_8(self):
        """Test that more than 8 keywords are truncated."""
        generator = KeywordGenerator()

        response = '{"keywords": ["k1", "k2", "k3", "k4", "k5", "k6", "k7", "k8", "k9", "k10"]}'
        keywords = generator._parse_keywords(response)

        assert len(keywords) == 8

    def test_parse_returns_less_than_5(self):
        """Test that less than 5 keywords are still returned."""
        generator = KeywordGenerator()

        response = '{"keywords": ["关键词 1", "关键词 2", "关键词 3"]}'
        keywords = generator._parse_keywords(response)

        assert len(keywords) == 3

    def test_parse_invalid_json_returns_empty(self):
        """Test that invalid JSON returns empty list."""
        generator = KeywordGenerator()

        response = "这不是有效的 JSON 格式"
        keywords = generator._parse_keywords(response)

        assert keywords == []

    def test_parse_empty_keywords(self):
        """Test parsing response with empty keywords array."""
        generator = KeywordGenerator()

        response = '{"keywords": []}'
        keywords = generator._parse_keywords(response)

        assert keywords == []

    def test_parse_missing_keywords_key(self):
        """Test parsing response missing keywords key."""
        generator = KeywordGenerator()

        response = '{"other_field": "value"}'
        keywords = generator._parse_keywords(response)

        assert keywords == []

    def test_parse_keywords_not_list(self):
        """Test parsing response where keywords is not a list."""
        generator = KeywordGenerator()

        response = '{"keywords": "not a list"}'
        keywords = generator._parse_keywords(response)

        assert keywords == []


class TestKeywordGenerator:
    """Test KeywordGenerator class."""

    def test_generator_initialization(self):
        """Test generator initializes correctly."""
        generator = KeywordGenerator()

        assert generator.model == "claude-sonnet-4-6"
        assert generator.SYSTEM_PROMPT is not None
        assert "A 股市场分析师" in generator.SYSTEM_PROMPT

    def test_generator_custom_model(self):
        """Test generator with custom model."""
        generator = KeywordGenerator(model="custom-model")

        assert generator.model == "custom-model"

    @pytest.mark.asyncio
    async def test_generate_keywords_success(self):
        """Test successful keyword generation."""
        generator = KeywordGenerator()

        # Mock LLM response
        mock_response = '{"keywords": ["科技", "创新", "5G", "通信", "网络"]}'

        with patch.object(generator, '_call_llm', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_response

            keywords = await generator.generate_keywords(
                sector_name="5G 概念",
                sector_stocks=["中兴通讯", "立讯精密"],
            )

            assert len(keywords) == 5
            assert "科技" in keywords
            mock_call.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_keywords_empty_response(self):
        """Test generation with empty response."""
        generator = KeywordGenerator()

        with patch.object(generator, '_call_llm', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = ""

            keywords = await generator.generate_keywords(
                sector_name="测试板块",
                sector_stocks=["股票 1"],
            )

            assert keywords == []

    @pytest.mark.asyncio
    async def test_generate_keywords_error(self):
        """Test generation with error."""
        generator = KeywordGenerator()

        with patch.object(generator, '_call_llm', new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = Exception("LLM API error")

            keywords = await generator.generate_keywords(
                sector_name="测试板块",
                sector_stocks=["股票 1"],
            )

            assert keywords == []


@pytest.mark.asyncio
class TestSectorKeywordService:
    """Test SectorKeywordService class."""

    @pytest.fixture
    def mock_session_maker(self):
        """Create a mock async session maker."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.scalar_one_or_none = AsyncMock()
        mock_session.close = AsyncMock()

        # Create async context manager mock for the session
        async_session_context = AsyncMock()
        async_session_context.__aenter__ = AsyncMock(return_value=mock_session)
        async_session_context.__aexit__ = AsyncMock(return_value=None)

        # Mock the session_maker itself as an async context manager
        mock_maker = MagicMock(return_value=async_session_context)
        return mock_maker, mock_session

    @pytest.fixture
    def service(self):
        """Create SectorKeywordService instance."""
        return SectorKeywordService()

    async def test_save_keywords_new_record(self, service, mock_session_maker):
        """Test saving keywords for new sector."""
        mock_maker, mock_session = mock_session_maker

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        keywords = ["关键词 1", "关键词 2", "关键词 3", "关键词 4", "关键词 5"]

        with patch.object(service, '_get_session', return_value=mock_session):
            result = await service.save_keywords(
                sector_id="sector_5g",
                sector_name="5G 概念",
                keywords=keywords,
                source="llm",
            )

        assert result is True
        mock_session.commit.assert_called_once()

    async def test_save_keywords_update_existing(self, service, mock_session_maker):
        """Test updating existing keywords."""
        mock_maker, mock_session = mock_session_maker

        existing_record = MagicMock()
        existing_record.sector_id = "sector_5g"
        existing_record.keywords = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_record
        mock_session.execute.return_value = mock_result

        keywords = ["新关键词 1", "新关键词 2"]

        with patch.object(service, '_get_session', return_value=mock_session):
            result = await service.save_keywords(
                sector_id="sector_5g",
                sector_name="5G 概念",
                keywords=keywords,
                source="manual",
            )

        assert result is True
        assert existing_record.keywords == json.dumps(keywords, ensure_ascii=False)
        assert existing_record.generation_source == "manual"
        mock_session.commit.assert_called_once()

    async def test_save_keywords_empty_returns_false(self, service, mock_session_maker):
        """Test saving empty keywords returns False."""
        mock_maker, mock_session = mock_session_maker

        with patch.object(service, '_get_session', return_value=mock_session):
            result = await service.save_keywords(
                sector_id="sector_empty",
                sector_name="空板块",
                keywords=[],
                source="llm",
            )

        assert result is False
        mock_session.commit.assert_not_called()

    async def test_get_keywords_existing(self, service, mock_session_maker):
        """Test getting keywords for existing sector."""
        mock_maker, mock_session = mock_session_maker

        keywords_list = ["关键词 1", "关键词 2", "关键词 3"]

        mock_record = MagicMock()
        mock_record.keywords = json.dumps(keywords_list, ensure_ascii=False)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_record
        mock_session.execute.return_value = mock_result

        with patch('src.market.keyword_generator.async_session_maker', mock_maker):
            result = await service.get_keywords("sector_5g")

        assert result == keywords_list

    async def test_get_keywords_none(self, service, mock_session_maker):
        """Test getting keywords for non-existent sector."""
        mock_maker, mock_session = mock_session_maker

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        with patch('src.market.keyword_generator.async_session_maker', mock_maker):
            result = await service.get_keywords("sector_nonexistent")

        assert result is None

    async def test_get_keywords_invalid_json(self, service, mock_session_maker):
        """Test getting keywords with invalid JSON."""
        mock_maker, mock_session = mock_session_maker

        mock_record = MagicMock()
        mock_record.keywords = "invalid json"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_record
        mock_session.execute.return_value = mock_result

        with patch('src.market.keyword_generator.async_session_maker', mock_maker):
            result = await service.get_keywords("sector_invalid")

        assert result is None


@pytest.mark.asyncio
class TestGenerateSectorKeywordsJob:
    """Test scheduled keyword generation job."""

    @pytest.fixture
    def mock_services(self):
        """Create mock services."""
        with patch('src.market.keyword_generator.KeywordGenerator') as mock_gen, \
             patch('src.market.keyword_generator.SectorKeywordService') as mock_svc:

            generator = mock_gen.return_value
            service = mock_svc.return_value

            # Setup service mock
            service.get_sectors_without_keywords = AsyncMock(return_value=[
                {"sector_id": "sector_5g", "sector_name": "5G 概念"},
                {"sector_id": "sector_ev", "sector_name": "新能源汽车"},
            ])
            service.save_keywords = AsyncMock(return_value=True)

            # Setup generator mock
            generator.generate_keywords = AsyncMock(return_value=[
                "科技", "创新", "5G", "通信", "网络"
            ])

            yield generator, service

    async def test_job_runs_successfully(self, mock_services):
        """Test job runs successfully for multiple sectors."""
        generator, service = mock_services

        await generate_sector_keywords_job()

        service.get_sectors_without_keywords.assert_called_once()
        assert generator.generate_keywords.call_count == 2
        assert service.save_keywords.call_count == 2

    async def test_job_no_sectors_needed(self, mock_services):
        """Test job when no sectors need keywords."""
        generator, service = mock_services
        service.get_sectors_without_keywords.return_value = []

        await generate_sector_keywords_job()

        service.get_sectors_without_keywords.assert_called_once()
        generator.generate_keywords.assert_not_called()
        service.save_keywords.assert_not_called()

    async def test_job_generation_fails(self, mock_services):
        """Test job when keyword generation fails."""
        generator, service = mock_services
        generator.generate_keywords = AsyncMock(return_value=[])

        await generate_sector_keywords_job()

        assert generator.generate_keywords.call_count == 2
        # save_keywords should not be called when generation returns empty
        service.save_keywords.assert_not_called()

    async def test_job_save_fails(self, mock_services):
        """Test job when save fails."""
        generator, service = mock_services
        service.save_keywords = AsyncMock(return_value=False)

        await generate_sector_keywords_job()

        assert service.save_keywords.call_count == 2


class TestSectorKeywordsModel:
    """Test SectorKeywords model."""

    def test_create_model(self):
        """Test creating SectorKeywords model."""
        keywords = ["关键词 1", "关键词 2", "关键词 3", "关键词 4", "关键词 5"]

        record = SectorKeywords(
            sector_id="sector_5g",
            sector_name="5G 概念",
            keywords=json.dumps(keywords, ensure_ascii=False),
            generation_source="llm",
        )

        assert record.sector_id == "sector_5g"
        assert record.sector_name == "5G 概念"
        assert json.loads(record.keywords) == keywords
        assert record.generation_source == "llm"

    def test_model_repr(self):
        """Test model string representation."""
        record = SectorKeywords(
            sector_id="sector_test",
            sector_name="测试板块",
            keywords='["测试"]',
        )

        repr_str = repr(record)

        assert "SectorKeywords" in repr_str
        assert "sector_test" in repr_str
        assert "测试板块" in repr_str


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
