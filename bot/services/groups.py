from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from bot.models import Group


async def list_groups(session: AsyncSession) -> list[Group]:
    stmt = select(Group).options(joinedload(Group.faculty)).order_by(Group.name)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_group(session: AsyncSession, group_id: int) -> Group | None:
    stmt = select(Group).options(joinedload(Group.faculty)).where(Group.id == group_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
