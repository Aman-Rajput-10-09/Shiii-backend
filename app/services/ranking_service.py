from datetime import datetime, timezone
from typing import List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc
from app.models.schemas import RelationshipMemory, CoupleConcern, ConcernStatus

class RankingService:
    @staticmethod
    async def get_ranked_context(
        db: AsyncSession,
        query_text: str,
        couple_id: int | None = None,
        limit: int = 3
    ) -> str:
        """
        Ranks memories based on:
        Score = Emotional Weight * Recency Factor
        """
        stmt = select(RelationshipMemory)
        if couple_id is not None:
            stmt = stmt.where((RelationshipMemory.couple_id == couple_id) | (RelationshipMemory.couple_id.is_(None)))
        stmt = stmt.order_by(desc(RelationshipMemory.emotional_weight)).limit(limit)
        result = await db.execute(stmt)
        memories = result.scalars().all()
        
        if not memories:
            return ""
            
        context_lines = [f"- {m.subject} ({m.category}): {m.memory_text}" for m in memories]
        return "\n".join(context_lines)

    @staticmethod
    async def get_unresolved_concerns(
        db: AsyncSession,
        couple_id: int | None = None
    ) -> List[CoupleConcern]:
        """
        Fetches pending concerns ordered by urgency score.
        If couple_id is provided, filters strictly for that couple.
        """
        stmt = select(CoupleConcern).where(
            CoupleConcern.status.in_([ConcernStatus.PENDING, ConcernStatus.BRIEFED])
        )
        if couple_id is not None:
            stmt = stmt.where(CoupleConcern.couple_id == couple_id)
            
        stmt = stmt.order_by(desc(CoupleConcern.urgency_score), desc(CoupleConcern.created_at))
        result = await db.execute(stmt)
        return list(result.scalars().all())

ranking_service = RankingService()
