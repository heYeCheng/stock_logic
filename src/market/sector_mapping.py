"""Stock-sector mapping service for managing industry and concept affiliations."""

from decimal import Decimal
from typing import List, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.connection import async_session_maker
from src.market.models import StockSectorMapping


class StockSectorService:
    """Service for managing stock-sector mappings.

    Provides methods to:
    - Update stock-sector mappings
    - Get sectors for a stock
    - Get stocks in a sector
    - Validate affiliation strength
    """

    @staticmethod
    def validate_affiliation_strength(strength: Decimal) -> bool:
        """Validate affiliation strength is within allowed range.

        Args:
            strength: The affiliation strength to validate (0.5-1.0)

        Returns:
            True if valid, False otherwise
        """
        return Decimal("0.5") <= strength <= Decimal("1.0")

    async def update_sector_mappings(
        self,
        stock_code: str,
        mappings: List[dict],
        session: Optional[AsyncSession] = None,
    ) -> None:
        """Update all sector mappings for a stock.

        This method deletes existing mappings and inserts new ones.

        Args:
            stock_code: The stock code (e.g., "000001.SZ")
            mappings: List of mapping dicts with keys:
                - sector_id: Sector ID
                - sector_type: "industry" or "concept"
                - sector_name: Sector name
                - affiliation_strength: 0.5-1.0 (default 1.0)
                - is_primary: Boolean (default False)
            session: Optional existing session (for transaction control)
        """
        close_session = False
        if session is None:
            session = async_session_maker()
            close_session = True

        try:
            async with session:
                # Delete old mappings
                await session.execute(
                    delete(StockSectorMapping).where(
                        StockSectorMapping.stock_code == stock_code
                    )
                )

                # Insert new mappings
                for mapping in mappings:
                    # Validate affiliation strength if provided
                    if "affiliation_strength" in mapping:
                        strength = mapping["affiliation_strength"]
                        if not self.validate_affiliation_strength(strength):
                            raise ValueError(
                                f"Invalid affiliation_strength: {strength}. "
                                "Must be between 0.5 and 1.0"
                            )

                    record = StockSectorMapping(
                        stock_code=stock_code,
                        sector_id=mapping.get("sector_id"),
                        sector_type=mapping.get("sector_type", "industry"),
                        sector_name=mapping.get("sector_name"),
                        affiliation_strength=mapping.get("affiliation_strength", Decimal("1.0")),
                        is_primary=mapping.get("is_primary", False),
                    )
                    session.add(record)

                await session.commit()
        finally:
            if close_session:
                await session.close()

    async def get_stock_sectors(
        self, stock_code: str, session: Optional[AsyncSession] = None
    ) -> List[StockSectorMapping]:
        """Get all sector mappings for a stock.

        Args:
            stock_code: The stock code
            session: Optional existing session

        Returns:
            List of StockSectorMapping records, ordered by is_primary desc
        """
        close_session = False
        if session is None:
            session = async_session_maker()
            close_session = True

        try:
            async with session:
                result = await session.execute(
                    select(StockSectorMapping)
                    .where(StockSectorMapping.stock_code == stock_code)
                    .order_by(StockSectorMapping.is_primary.desc())
                )
                return list(result.scalars().all())
        finally:
            if close_session:
                await session.close()

    async def get_sector_stocks(
        self, sector_id: str, session: Optional[AsyncSession] = None
    ) -> List[str]:
        """Get all stocks in a sector.

        Args:
            sector_id: The sector ID
            session: Optional existing session

        Returns:
            List of stock codes in the sector
        """
        close_session = False
        if session is None:
            session = async_session_maker()
            close_session = True

        try:
            async with session:
                result = await session.execute(
                    select(StockSectorMapping.stock_code).where(
                        StockSectorMapping.sector_id == sector_id
                    )
                )
                return list(result.scalars().all())
        finally:
            if close_session:
                await session.close()

    async def get_primary_sector(
        self, stock_code: str, session: Optional[AsyncSession] = None
    ) -> Optional[StockSectorMapping]:
        """Get the primary sector for a stock.

        Args:
            stock_code: The stock code
            session: Optional existing session

        Returns:
            Primary sector mapping or None if not found
        """
        close_session = False
        if session is None:
            session = async_session_maker()
            close_session = True

        try:
            async with session:
                result = await session.execute(
                    select(StockSectorMapping)
                    .where(
                        StockSectorMapping.stock_code == stock_code,
                        StockSectorMapping.is_primary == True,
                    )
                    .limit(1)
                )
                return result.scalar_one_or_none()
        finally:
            if close_session:
                await session.close()

    async def get_max_affiliation_strength(
        self, stock_code: str, session: Optional[AsyncSession] = None
    ) -> Decimal:
        """Get maximum affiliation strength across all sectors for a stock.

        Args:
            stock_code: The stock code
            session: Optional existing session

        Returns:
            Maximum affiliation strength (0.0 if no mappings)
        """
        close_session = False
        if session is None:
            session = async_session_maker()
            close_session = True

        try:
            async with session:
                result = await session.execute(
                    select(StockSectorMapping.affiliation_strength)
                    .where(StockSectorMapping.stock_code == stock_code)
                )
                strengths = result.scalars().all()

                if not strengths:
                    return Decimal("0.0")

                return max(strengths)
        finally:
            if close_session:
                await session.close()
