from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import require_database
from backend.models.database import AsyncSessionLocal
from backend.models.schemas import CompetitorCreate, CompetitorResponse
from backend.models.tables import Competitor

router = APIRouter(prefix="/api", dependencies=[Depends(require_database)])


async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


def _to_response(competitor: Competitor) -> CompetitorResponse:
    return CompetitorResponse(
        id=competitor.id,
        name=competitor.name,
        industry=competitor.industry,
        keywords=competitor.keywords or [],
        active=competitor.active,
        created_at=competitor.created_at,
    )


@router.get("/competitors", response_model=list[CompetitorResponse])
async def list_competitors(session: AsyncSession = Depends(get_session)) -> list[CompetitorResponse]:
    result = await session.execute(select(Competitor).order_by(Competitor.created_at.desc()))
    return [_to_response(c) for c in result.scalars().all()]


@router.post("/competitors", response_model=CompetitorResponse, status_code=201)
async def create_competitor(
    payload: CompetitorCreate,
    session: AsyncSession = Depends(get_session),
) -> CompetitorResponse:
    competitor = Competitor(
        name=payload.name,
        industry=payload.industry,
        keywords=payload.keywords,
        active=payload.active,
    )
    session.add(competitor)
    await session.commit()
    await session.refresh(competitor)
    return _to_response(competitor)


@router.delete("/competitors/{competitor_id}", status_code=204)
async def delete_competitor(
    competitor_id: int,
    session: AsyncSession = Depends(get_session),
) -> None:
    result = await session.execute(select(Competitor).where(Competitor.id == competitor_id))
    competitor = result.scalar_one_or_none()
    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")
    await session.delete(competitor)
    await session.commit()
