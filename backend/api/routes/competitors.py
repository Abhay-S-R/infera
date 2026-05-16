from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import require_database
from backend.core.database import AsyncSessionLocal
from backend.models.schemas import (
    CompetitorCreate,
    CompetitorProfileResponse,
    CompetitorResponse,
)
from backend.models.tables import Competitor
from backend.pipeline.context import get_competitor_profile

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


@router.get("/competitors/{competitor_name}/profile", response_model=CompetitorProfileResponse)
async def get_competitor_institutional_memory(
    competitor_name: str,
) -> CompetitorProfileResponse:
    """Return structured institutional memory for demo / dashboard."""
    profile = await get_competitor_profile(competitor_name)
    if not profile:
        return CompetitorProfileResponse(
            competitor_name=competitor_name,
            found=False,
        )
    return CompetitorProfileResponse(
        competitor_name=profile.competitor_name,
        shipping_record=profile.shipping_record,
        launch_history=profile.launch_history,
        hiring_signals=profile.hiring_signals,
        ceo_public_statements=profile.ceo_public_statements,
        last_assessment=profile.last_assessment,
        updated_at=profile.updated_at,
        found=True,
    )


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
