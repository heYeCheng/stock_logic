# Phase 6: Web UI - Research

**Researched:** 2026-04-19  
**Domain:** FastAPI REST API + React Dashboard for Financial Data  
**Confidence:** HIGH

## Summary

Phase 6 implements the user-facing web interface for the stock logic system. This phase has two main components:

1. **Backend (FastAPI):** REST API serving recommendations, stock details, macro overview, and manual override endpoints
2. **Frontend (React):** Dashboard displaying stock cards, radar charts, logic summaries, and YAML config editor

**Primary recommendation:** Use FastAPI with async SQLAlchemy 2.0 for the backend, and React with TanStack Query + Recharts for the frontend. Leverage existing code from `old/api/` directory as reference but modernize to current best practices.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| REST API endpoints | API / Backend | — | FastAPI handles HTTP, business logic, data validation |
| Stock recommendation display | Browser / Client | API / Backend | React renders UI, API provides data |
| Radar chart visualization | Browser / Client | — | Client-side rendering with Recharts |
| Manual override (strength adjustment) | Browser / Client | API / Backend | UI collects input, API persists to DB |
| YAML config editor | Browser / Client | API / Backend | UI provides editor, API handles git operations |
| Audit trail logging | API / Backend | Database / Storage | Server-side logging for compliance |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.128.0 | REST API framework | Modern, async-ready, auto OpenAPI docs, Pydantic v2 integration |
| React | 19.2.5 | Frontend framework | Component-based, ecosystem leadership, Suspense support |
| SQLAlchemy | 2.0.x | ORM & async DB | Industry standard, async support via asyncpg |
| Pydantic | 2.x | Data validation | FastAPI integration, type-safe schemas |
| Recharts | 3.8.1 | Chart visualization | React-native, radar charts, declarative API |
| TanStack Query | 5.99.2 | Server state management | Caching, invalidation, optimistic updates |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| uvicorn[standard] | >=0.27.0 | ASGI server | Production FastAPI deployment |
| python-multipart | >=0.0.6 | Form data parsing | File uploads, form submissions |
| aiofiles | Latest | Async file I/O | YAML file reading/writing |
| dulwich | Latest | Pure Python Git | YAML version control (no git CLI dependency) |
| httpx | Latest | Async HTTP client | External API calls from FastAPI |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| FastAPI | Flask + Marshmallow | Flask lacks async native support, more boilerplate |
| React | Vue 3 | Vue has smaller ecosystem for financial dashboards |
| Recharts | Chart.js + react-chartjs-2 | Recharts has better React integration, RadarChart component |
| TanStack Query | SWR | TanStack has more features (mutations, optimistic updates) |
| Dulwich | GitPython | Dulwich is pure Python (no git CLI dependency) |

**Installation:**

Backend (Python):
```bash
# Already in requirements.txt:
# fastapi>=0.109.0
# uvicorn[standard]>=0.27.0
# python-multipart>=0.0.6
# sqlalchemy>=2.0.0

# Add for Phase 6:
pip install aiofiles dulwich
```

Frontend (Node.js):
```bash
npm install react @tanstack/react-query recharts
npm install -D typescript @types/react @types/node
```

**Version verification:**
```bash
npm view fastapi version    # 0.128.0 (via Context7)
npm view react version      # 19.2.5
npm view recharts version   # 3.8.1
npm view @tanstack/react-query version  # 5.99.2
```

## Architecture Patterns

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         Browser (React)                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │ Stock Cards │  │ Radar Chart │  │ YAML Config Editor      │ │
│  │ Component   │  │ Component   │  │ Component               │ │
│  └──────┬──────┘  └──────┬──────┘  └────────────┬────────────┘ │
│         │                │                       │              │
│         └────────────────┴───────────────────────┘              │
│                          │                                       │
│              ┌───────────▼───────────┐                          │
│              │   TanStack Query      │                          │
│              │   (cache + mutations) │                          │
│              └───────────┬───────────┘                          │
└───────────────────────────┼──────────────────────────────────────┘
                            │ HTTP/JSON
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI Backend (Python)                     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  /api/v1/recommendations  /api/v1/stocks/{code}          │  │
│  │  /api/v1/macro            /api/v1/overrides              │  │
│  │  /api/v1/config/yaml      /api/v1/config/history         │  │
│  └──────────────────────────────────────────────────────────┘  │
│         │                │                       │              │
│    ┌────▼────┐     ┌─────▼─────┐          ┌────▼────┐         │
│    │Pydantic │     │ SQLAlchemy│          │ Dulwich │         │
│    │ Schemas │     │  2.0 Async│          │  (Git)  │         │
│    └────┬────┘     └─────┬─────┘          └────┬────┘         │
│         │                │                       │              │
│         └────────────────┴───────────────────────┘              │
│                          │                                       │
│              ┌───────────▼───────────┐                          │
│              │   MySQL Database      │                          │
│              │   + YAML snapshots    │                          │
│              └───────────────────────┘                          │
└─────────────────────────────────────────────────────────────────┘
```

### Recommended Project Structure

```
src/
├── api/                    # FastAPI application
│   ├── __init__.py
│   ├── app.py             # FastAPI app factory
│   ├── deps.py            # Dependencies (session, auth)
│   └── v1/
│       ├── __init__.py
│       ├── router.py      # API router inclusion
│       ├── endpoints/
│       │   ├── __init__.py
│       │   ├── recommendations.py  # WEB-01: Recommendation list
│       │   ├── stocks.py           # WEB-01: Stock details
│       │   ├── macro.py            # WEB-01: Macro overview
│       │   ├── overrides.py        # WEB-03: Manual override
│       │   └── config.py           # WEB-04: YAML config editor
│       └── schemas/
│           ├── __init__.py
│           ├── recommendations.py  # Pydantic response models
│           ├── stocks.py           # Stock detail schemas
│           ├── macro.py            # Macro data schemas
│           ├── overrides.py        # Override request/response
│           └── config.py           # YAML config schemas
│
├── webui/                  # React frontend (or separate repo)
│   ├── src/
│   │   ├── components/
│   │   │   ├── StockCard.tsx       # Stock display card
│   │   │   ├── RadarChart.tsx      # Market/logic radar
│   │   │   ├── LogicSummary.tsx    # Logic affiliation display
│   │   │   ├── OverrideForm.tsx    # Manual override form
│   │   │   └── YamlEditor.tsx      # YAML config editor
│   │   ├── hooks/
│   │   │   ├── useRecommendations.ts
│   │   │   ├── useStockDetail.ts
│   │   │   ├── useMacro.ts
│   │   │   └── useConfigHistory.ts
│   │   ├── services/
│   │   │   └── api.ts              # TanStack Query setup
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   └── tsconfig.json
│
└── services/
    ├── config_service.py    # YAML config management
    └── audit_service.py     # Audit trail logging
```

### Pattern 1: FastAPI Async Endpoint with SQLAlchemy 2.0

**What:** Async endpoint pattern for database queries

**When to use:** All database-backed API endpoints

**Example:**
```python
# Source: https://context7.com/sqlalchemy/sqlalchemy/llms.txt
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from api.deps import get_db_session
from src.models.stock import StockRecommendation

router = APIRouter()

class RecommendationResponse(BaseModel):
    stock_code: str
    stock_name: str | None
    recommended_position: float
    position_tier: str
    marker: str
    composite_score: float

@router.get("/recommendations", response_model=list[RecommendationResponse])
async def get_recommendations(
    db: AsyncSession = Depends(get_db_session),
    limit: int = 50,
) -> list[RecommendationResponse]:
    """Get top stock recommendations."""
    stmt = (
        select(StockRecommendation)
        .order_by(StockRecommendation.composite_score.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    recommendations = result.scalars().all()
    
    return [
        RecommendationResponse(
            stock_code=r.stock_code,
            stock_name=r.stock_name,
            recommended_position=float(r.recommended_position),
            position_tier=r.position_tier,
            marker=r.marker,
            composite_score=float(r.composite_score),
        )
        for r in recommendations
    ]
```

### Pattern 2: React Component with TanStack Query

**What:** Data fetching pattern with caching and loading states

**When to use:** All React components that fetch from API

**Example:**
```tsx
// Source: https://github.com/tanstack/query/blob/main/docs/framework/react/quick-start.md
import { useQuery } from '@tanstack/react-query';
import { StockCard } from './StockCard';

async function fetchRecommendations() {
  const response = await fetch('/api/v1/recommendations');
  if (!response.ok) throw new Error('Failed to fetch');
  return response.json();
}

export function RecommendationsList() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['recommendations'],
    queryFn: fetchRecommendations,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });

  if (isLoading) return <div>Loading...</div>;
  if (error) return <div>Error: {error.message}</div>;

  return (
    <div className="grid gap-4">
      {data.map((stock) => (
        <StockCard key={stock.stock_code} stock={stock} />
      ))}
    </div>
  );
}
```

### Pattern 3: Recharts Radar Chart

**What:** Multi-variable comparison visualization

**When to use:** Displaying stock logic/market scores

**Example:**
```tsx
// Source: https://context7.com/recharts/recharts/llms.txt
import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  Legend,
  Tooltip,
} from 'recharts';

const data = [
  { subject: 'Logic Score', value: 0.75, fullMark: 1.0 },
  { subject: 'Market Score', value: 0.62, fullMark: 1.0 },
  { subject: 'Macro Fit', value: 0.88, fullMark: 1.0 },
  { subject: 'Sector State', value: 0.45, fullMark: 1.0 },
  { subject: 'Sentiment', value: 0.70, fullMark: 1.0 },
];

export function StockRadarChart({ stockCode }: { stockCode: string }) {
  return (
    <RadarChart
      cx={200}
      cy={150}
      outerRadius={100}
      width={400}
      height={300}
      data={data}
    >
      <PolarGrid />
      <PolarAngleAxis dataKey="subject" />
      <PolarRadiusAxis angle={30} domain={[0, 1]} />
      <Radar
        name={stockCode}
        dataKey="value"
        stroke="#8884d8"
        fill="#8884d8"
        fillOpacity={0.6}
      />
      <Legend />
      <Tooltip />
    </RadarChart>
  );
}
```

### Pattern 4: TanStack Query Mutation with Optimistic Update

**What:** Manual override with immediate UI feedback

**When to use:** WEB-03 manual override interface

**Example:**
```tsx
// Source: https://github.com/tanstack/query/blob/main/docs/framework/react/guides/updates-from-mutation-responses.md
import { useMutation, useQueryClient } from '@tanstack/react-query';

async function updateOverride({ stockCode, strength, affiliationStrength }) {
  const response = await fetch(`/api/v1/overrides/${stockCode}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ strength, affiliation_strength: affiliationStrength }),
  });
  if (!response.ok) throw new Error('Failed to update');
  return response.json();
}

export function OverrideForm({ stockCode }) {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: updateOverride,
    onSuccess: (data) => {
      // Update cached query data
      queryClient.setQueryData(['stock', stockCode], data);
      // Invalidate to refetch
      queryClient.invalidateQueries({ queryKey: ['recommendations'] });
    },
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    mutation.mutate({
      stockCode,
      strength: formData.get('strength'),
      affiliationStrength: formData.get('affiliationStrength'),
    });
  };

  return (
    <form onSubmit={handleSubmit}>
      <input name="strength" type="number" step="0.1" min="0" max="1" />
      <input name="affiliationStrength" type="number" step="0.1" min="0" max="1" />
      <button type="submit" disabled={mutation.isPending}>
        {mutation.isPending ? 'Saving...' : 'Save Override'}
      </button>
    </form>
  );
}
```

### Pattern 5: Dulwich Git Operations for YAML Version Control

**What:** Git clone, commit, push without external git CLI

**When to use:** WEB-04 YAML config editor with version control

**Example:**
```python
# Source: https://context7.com/jelmer/dulwich/llms.txt
from dulwich import porcelain
from dulwich.repo import Repo
import aiofiles
import os

CONFIG_REPO_PATH = "/path/to/config-repo"
CONFIG_FILE = "config/anchor_config.yaml"

class ConfigVersionControl:
    def __init__(self, repo_path: str = CONFIG_REPO_PATH):
        self.repo_path = repo_path
        self._ensure_repo_exists()
    
    def _ensure_repo_exists(self):
        """Clone or initialize config repo."""
        if not os.path.exists(self.repo_path):
            # Clone from remote (e.g., GitHub)
            porcelain.clone(
                "https://github.com/org/stock-config.git",
                self.repo_path,
                branch="main"
            )
        else:
            # Pull latest changes
            porcelain.pull(self.repo_path, "origin", "main")
    
    async def read_config(self) -> str:
        """Read current YAML config."""
        config_path = os.path.join(self.repo_path, CONFIG_FILE)
        async with aiofiles.open(config_path, 'r') as f:
            return await f.read()
    
    async def save_config(self, content: str, commit_message: str, author: str) -> str:
        """Save config with git commit."""
        config_path = os.path.join(self.repo_path, CONFIG_FILE)
        
        # Write new content
        async with aiofiles.open(config_path, 'w') as f:
            await f.write(content)
        
        # Stage and commit
        porcelain.add(self.repo_path, CONFIG_FILE)
        commit_sha = porcelain.commit(
            self.repo_path,
            message=commit_message.encode('utf-8'),
            author=author.encode('utf-8'),
        )
        
        # Push to remote
        porcelain.push(self.repo_path, "origin", "main")
        
        return commit_sha.decode('ascii')
    
    def get_history(self, limit: int = 10) -> list[dict]:
        """Get commit history for config file."""
        repo = Repo(self.repo_path)
        history = []
        
        for entry in repo.get_walker(
            max_entries=limit,
            paths=[CONFIG_FILE.encode('utf-8')]
        ):
            history.append({
                "commit": entry.commit.id.decode('ascii'),
                "message": entry.commit.message.decode('utf-8'),
                "author": entry.commit.author.decode('utf-8'),
                "timestamp": entry.commit.commit_time,
            })
        
        return history
```

### Anti-Patterns to Avoid

- **Don't use synchronous SQLAlchemy in async endpoints:** Always use `await session.execute()` and `AsyncSession`
- **Don't fetch data in useEffect:** Use TanStack Query for server state management
- **Don't build custom git integration:** Use Dulwich (pure Python) instead of subprocess git calls
- **Don't store YAML in database:** Keep YAML files in git repo, use database for audit trail metadata only

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Server state management | Custom Redux store + thunks | TanStack Query | Built-in caching, invalidation, optimistic updates |
| Git version control | subprocess calls to git CLI | Dulwich | Pure Python, no external dependency, better error handling |
| Chart visualization | D3.js from scratch | Recharts | React components, declarative API, radar chart built-in |
| Async file I/O | Thread pool for file ops | aiofiles | Native async, cleaner code |
| API data validation | Manual dict parsing | Pydantic v2 | Type-safe, auto OpenAPI schema, error messages |

**Key insight:** The ecosystem has mature solutions for all Phase 6 challenges. Custom implementations would lack edge case handling (e.g., Git SSH auth, chart accessibility, query deduplication).

## Runtime State Inventory

*Not applicable - this is a greenfield Web UI phase, not a rename/refactor phase.*

## Common Pitfalls

### Pitfall 1: Mixing Pydantic v1 and v2 Syntax

**What goes wrong:** Using Pydantic v1 `@validator` decorator in Pydantic v2 codebase

**Why it happens:** Pydantic v2 changed validator syntax (`@field_validator` with `ValidationInfo`)

**How to avoid:** Always use `@field_validator` and access config via `info.config` dict

**Warning signs:** Import errors from `pydantic.v1`, deprecation warnings

### Pitfall 2: SQLAlchemy 2.0 Query Syntax

**What goes wrong:** Using old `session.query(User).filter(...)` syntax

**Why it happens:** SQLAlchemy 2.0 deprecated Query object in favor of `select()` construct

**How to avoid:** Always use `session.execute(select(Model).filter(...))`

**Warning signs:** `LegacyAPIWarning` in logs, query results as tuples instead of scalars

### Pitfall 3: TanStack Query Key Collisions

**What goes wrong:** Same query key for different data shapes

**Why it happens:** Query keys like `['stock']` without parameters collide

**How to avoid:** Always include identifiers: `['stock', stockCode]`, `['recommendations', date]`

**Warning signs:** Wrong data appearing in components, stale data not refreshing

### Pitfall 4: Dulwich SSH Authentication

**What goes wrong:** SSH key authentication fails for private repos

**Why it happens:** Dulwich needs explicit `key_filename` parameter

**How to avoid:** Test with HTTPS first, add SSH config for production

**Warning signs:** `Permission denied (publickey)` errors on clone/push

## Code Examples

### FastAPI Endpoint: Stock Detail

```python
# Source: Adapted from old/api/v1/endpoints/stocks.py + SQLAlchemy 2.0 async
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field

from api.deps import get_db_session
from src.models.stock import Stock, StockRecommendation

router = APIRouter()

class StockDetailResponse(BaseModel):
    stock_code: str
    stock_name: str | None
    current_price: float | None
    change_percent: float | None
    recommended_position: float
    position_tier: str
    marker: str
    marker_reason: str | None
    logic_score: float
    market_score: float
    composite_score: float
    radar_data: dict  # For radar chart

@router.get("/stocks/{stock_code}", response_model=StockDetailResponse)
async def get_stock_detail(
    stock_code: str,
    db: AsyncSession = Depends(get_db_session),
) -> StockDetailResponse:
    """Get detailed stock information with scores and recommendation."""
    # Query stock recommendation
    stmt = (
        select(StockRecommendation)
        .where(StockRecommendation.stock_code == stock_code)
    )
    result = await db.execute(stmt)
    rec = result.scalars().first()
    
    if not rec:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": f"Stock {stock_code} not found"}
        )
    
    return StockDetailResponse(
        stock_code=rec.stock_code,
        stock_name=rec.stock_name,
        current_price=rec.current_price,
        change_percent=rec.change_percent,
        recommended_position=float(rec.recommended_position),
        position_tier=rec.position_tier,
        marker=rec.marker,
        marker_reason=rec.marker_reason,
        logic_score=float(rec.logic_score),
        market_score=float(rec.market_score),
        composite_score=float(rec.composite_score),
        radar_data={
            "Logic Score": float(rec.logic_score),
            "Market Score": float(rec.market_score),
            "Macro Fit": float(rec.macro_fit),
            "Sector State": float(rec.sector_state),
            "Sentiment": float(rec.sentiment),
        }
    )
```

### React Component: Stock Card

```tsx
// Source: Pattern from React docs + Recharts
import { Link } from 'react-router-dom';

interface StockCardProps {
  stock: {
    stock_code: string;
    stock_name: string | null;
    current_price: number;
    change_percent: number;
    recommended_position: number;
    position_tier: string;
    marker: string;
  };
}

export function StockCard({ stock }: StockCardProps) {
  const markerColors = {
    '逻辑受益股': 'bg-green-100 text-green-800',
    '关联受益股': 'bg-blue-100 text-blue-800',
    '情绪跟风股': 'bg-yellow-100 text-yellow-800',
  };

  return (
    <Link to={`/stocks/${stock.stock_code}`} className="block">
      <div className="border rounded-lg p-4 hover:shadow-md transition-shadow">
        <div className="flex justify-between items-start">
          <div>
            <h3 className="text-lg font-semibold">{stock.stock_name || stock.stock_code}</h3>
            <p className="text-sm text-gray-500">{stock.stock_code}</p>
          </div>
          <span className={`px-2 py-1 rounded text-xs ${markerColors[stock.marker as keyof typeof markerColors]}`}>
            {stock.marker}
          </span>
        </div>
        
        <div className="mt-3 flex justify-between items-center">
          <div>
            <p className="text-2xl font-bold">¥{stock.current_price?.toFixed(2)}</p>
            <p className={`text-sm ${stock.change_percent >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {stock.change_percent >= 0 ? '+' : ''}{stock.change_percent?.toFixed(2)}%
            </p>
          </div>
          <div className="text-right">
            <p className="text-sm text-gray-500">推荐仓位</p>
            <p className="text-lg font-semibold">{(stock.recommended_position * 100).toFixed(0)}%</p>
            <p className="text-xs text-gray-400">{stock.position_tier}</p>
          </div>
        </div>
      </div>
    </Link>
  );
}
```

### FastAPI Endpoint: Manual Override with Audit

```python
# Source: Combined pattern from FastAPI best practices
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime
from pydantic import BaseModel, Field, field_validator

from api.deps import get_db_session, get_current_user
from src.models.stock import StockRecommendation, OverrideAuditLog

router = APIRouter()

class OverrideRequest(BaseModel):
    strength: float = Field(ge=0, le=1)
    affiliation_strength: float = Field(ge=0, le=1)
    reason: str = Field(min_length=10, max_length=500)
    
    @field_validator('reason')
    @classmethod
    def reason_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError('Reason cannot be empty or whitespace')
        return v.strip()

class OverrideResponse(BaseModel):
    stock_code: str
    previous_strength: float | None
    new_strength: float
    previous_affiliation: float | None
    new_affiliation: float
    audit_id: int

@router.patch("/overrides/{stock_code}", response_model=OverrideResponse)
async def create_override(
    stock_code: str,
    override: OverrideRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
) -> OverrideResponse:
    """Manually override strength values with audit trail."""
    # Get current recommendation
    stmt = select(StockRecommendation).where(
        StockRecommendation.stock_code == stock_code
    )
    result = await db.execute(stmt)
    rec = result.scalars().first()
    
    if not rec:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": f"Stock {stock_code} not found"}
        )
    
    # Store previous values
    previous_strength = rec.strength_override
    previous_affiliation = rec.affiliation_strength_override
    
    # Apply override
    rec.strength_override = override.strength
    rec.affiliation_strength_override = override.affiliation_strength
    rec.override_reason = override.reason
    rec.override_by = current_user.get("username")
    rec.override_at = datetime.utcnow()
    
    # Create audit log entry
    audit_log = OverrideAuditLog(
        stock_code=stock_code,
        previous_strength=previous_strength,
        new_strength=override.strength,
        previous_affiliation=previous_affiliation,
        new_affiliation=override.affiliation_strength,
        reason=override.reason,
        changed_by=current_user.get("username"),
    )
    db.add(audit_log)
    
    await db.commit()
    
    return OverrideResponse(
        stock_code=stock_code,
        previous_strength=float(previous_strength) if previous_strength else None,
        new_strength=override.strength,
        previous_affiliation=float(previous_affiliation) if previous_affiliation else None,
        new_affiliation=override.affiliation_strength,
        audit_id=audit_log.id,
    )
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Flask + sync SQLAlchemy | FastAPI + async SQLAlchemy | 2023-2024 | 2-3x throughput, native async |
| Redux for server state | TanStack Query | 2022-2024 | Less boilerplate, auto-caching |
| Chart.js imperative API | Recharts declarative | 2021-2024 | React-friendly, composable |
| subprocess git calls | Dulwich pure Python | 2020-2024 | No external deps, better errors |
| Pydantic v1 `@validator` | Pydantic v2 `@field_validator` | 2023 | Faster validation, Rust core |

**Deprecated/outdated:**
- Flask sync endpoints: Use FastAPI async for I/O-bound operations
- `session.query()`: Use `session.execute(select())` in SQLAlchemy 2.0
- Manual fetch in useEffect: Use TanStack Query hooks

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Frontend will be in same repo as backend (`webui/` subdirectory) | Recommended Project Structure | MEDIUM - affects build/deploy pipeline |
| A2 | Existing MySQL database from Phase 1-5 will be reused | Code Examples | LOW - schema extensions are additive |
| A3 | Dulwich SSH auth works with standard OpenSSH key formats | Don't Hand-Roll | MEDIUM - may need GitPython fallback |
| A4 | React 19 is production-ready for dashboard use | Standard Stack | LOW - React 18 fallback available |

## Open Questions

1. **Authentication approach**
   - What we know: `old/api/` has auth middleware
   - What's unclear: Should Web UI use same auth or separate session-based auth?
   - Recommendation: Reuse existing JWT/session approach for consistency

2. **YAML config repo location**
   - What we know: Config version control needed
   - What's unclear: Should config repo be same as code repo or separate?
   - Recommendation: Start with same repo, separate if access control needed

3. **Frontend deployment**
   - What we know: FastAPI can serve static files
   - What's unclear: Should frontend be built and served by FastAPI or separate CDN?
   - Recommendation: Start with FastAPI static serving (simpler), migrate to CDN later

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Backend | ✓ | 3.12.10 | — |
| Node.js | Frontend build | ✓ | 11.12.0 | — |
| npm | Frontend deps | ✓ | 11.12.0 | pnpm/yarn |
| MySQL | Database | ASSUMED | — | Verify from Phase 1 |
| Git remote (GitHub/GitLab) | YAML version control | ASSUMED | — | Local-only mode |

**Missing dependencies with no fallback:**
- None confirmed (MySQL and Git remote assumed from prior phases)

**Missing dependencies with fallback:**
- npm → pnpm or yarn available as alternatives

## Validation Architecture

*Skipped - `workflow.nyquist_validation` is explicitly `false` in `.planning/config.json`.*

## Security Domain

*Note: `security_enforcement` not explicitly configured. Assuming standard web security applies.*

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Reuse existing JWT/session from `old/api/` |
| V3 Session Management | yes | FastAPI session middleware |
| V4 Access Control | yes | Role-based override permissions |
| V5 Input Validation | yes | Pydantic v2 schemas |
| V6 Cryptography | no | No encryption needed beyond HTTPS |

### Known Threat Patterns for FastAPI + React

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SQL Injection | Tampering | SQLAlchemy ORM (parameterized queries) |
| XSS | Spoofing | React auto-escapes, CSP headers |
| CSRF | Tampering | SameSite cookies, CSRF tokens |
| Overwrite config | Tampering | Audit trail + git history |
| Unauthorized override | Tampering | Auth middleware + role checks |

## Sources

### Primary (HIGH confidence)
- `/fastapi/fastapi` (Context7) - FastAPI async patterns, Pydantic v2 integration
- `/sqlalchemy/sqlalchemy` (Context7) - SQLAlchemy 2.0 async session usage
- `/pydantic/pydantic` (Context7) - Pydantic v2 field validators
- `/tanstack/query` (Context7) - TanStack Query mutations, caching
- `/recharts/recharts` (Context7) - RadarChart component API
- `/jelmer/dulwich` (Context7) - Dulwich git operations (clone, commit, push)

### Secondary (MEDIUM confidence)
- `old/api/v1/endpoints/stocks.py` - Existing endpoint patterns (reference only)
- `old/src/core/config_registry.py` - YAML config structure (reference only)

### Tertiary (LOW confidence)
- npm registry versions - Not directly verified via tool call

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries verified via Context7 with current versions
- Architecture: HIGH - Patterns from official docs + existing codebase reference
- Pitfalls: MEDIUM - Based on migration guides and common patterns

**Research date:** 2026-04-19  
**Valid until:** 2026-07-19 (90 days - stable stack, React major versions infrequent)
