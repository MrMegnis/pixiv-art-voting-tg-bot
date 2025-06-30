import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload

from .models import User, Artwork, Source, Rating, UserProgress

# --- User Functions ---

async def get_or_create_user(session: AsyncSession, user_id: int, username: str = None):
    """Получает пользователя из БД или создает нового, если его нет."""
    stmt = select(User).where(User.user_id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        user = User(user_id=user_id, username=username)
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user

async def authorize_user(session: AsyncSession, user_id: int):
    """Авторизует пользователя."""
    stmt = select(User).where(User.user_id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if user:
        user.is_authorized = True
        await session.commit()
    return user

# --- Source and Artwork Functions ---

async def add_file_source(session: AsyncSession, filename: str, filepath: str, owner_id: int):
    """Добавляет новый источник типа 'file'."""
    source_details = {'path': filepath}
    new_source = Source(
        source_type='file',
        name=filename,
        details=source_details,
        owner_id=owner_id
    )
    session.add(new_source)
    await session.commit()
    return new_source

async def get_all_file_sources(session: AsyncSession):
    """Получает все АКТИВНЫЕ источники типа 'file'."""
    stmt = select(Source).where(
        Source.source_type == 'file',
        Source.is_active == True  # Добавляем это условие
    ).order_by(Source.name)
    result = await session.execute(stmt)
    return result.scalars().all()

async def get_user_file_sources(session: AsyncSession, owner_id: int):
    """Получает все АКТИВНЫЕ файлы, загруженные пользователем."""
    stmt = select(Source).where(
        Source.owner_id == owner_id,
        Source.source_type == 'file',
        Source.is_active == True  # Добавляем это условие
    )
    result = await session.execute(stmt)
    return result.scalars().all()

async def get_user_query_sources(session: AsyncSession, owner_id: int):
    """Получает все АКТИВНЫЕ запросы, созданные пользователем."""
    stmt = select(Source).where(
        Source.owner_id == owner_id,
        Source.source_type == 'query',
        Source.is_active == True
    )
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_source_by_id(session: AsyncSession, source_id: int):
    stmt = select(Source).where(Source.source_id == source_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def delete_source_by_owner(session: AsyncSession, source_id: int, owner_id: int):
    """
    Выполняет "мягкое удаление": помечает источник как неактивный.
    """
    # Находим источник, который нужно "удалить"
    stmt = select(Source).where(Source.source_id == source_id, Source.owner_id == owner_id)
    result = await session.execute(stmt)
    source_to_deactivate = result.scalar_one_or_none()

    if source_to_deactivate:
        # Вместо удаления, просто меняем флаг и сохраняем
        source_to_deactivate.is_active = False
        await session.commit()
        return True

    return False


async def get_or_create_artwork(session: AsyncSession, formatted_art: dict, image_index: int):
    """Находит или создает запись для КОНКРЕТНОЙ КАРТИНКИ из поста."""
    pixiv_id = formatted_art['id']
    stmt = select(Artwork).where(Artwork.pixiv_id == pixiv_id, Artwork.image_index == image_index)
    result = await session.execute(stmt)
    artwork = result.scalar_one_or_none()

    if not artwork:
        artwork = Artwork(
            pixiv_id=pixiv_id,
            image_index=image_index,
            title=formatted_art.get('title'),
            author=formatted_art.get('author'),
            url=formatted_art.get('url'),
            # В other_data кладем все, включая URL всех картинок серии
            other_data=formatted_art
        )
        session.add(artwork)
        await session.commit()
        await session.refresh(artwork)
    return artwork

# --- Rating and Progress Functions ---

async def add_rating(session: AsyncSession, user_id: int, artwork_id: int, source_id: int, score: int):
    """Добавляет новую оценку."""
    new_rating = Rating(
        user_id=user_id,
        artwork_id=artwork_id,
        source_id=source_id,
        score=score
    )
    session.add(new_rating)
    await session.commit()
    return new_rating

async def check_user_rating_for_artwork(session: AsyncSession, user_id: int, artwork_id: int):
    """Проверяет оценку по НОВОМУ уникальному ID картинки."""
    stmt = select(Rating).where(Rating.user_id == user_id, Rating.artwork_id == artwork_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None

async def get_user_progress(session: AsyncSession, user_id: int, source_id: int):
    """Получает прогресс пользователя по источнику."""
    stmt = select(UserProgress).where(UserProgress.user_id == user_id, UserProgress.source_id == source_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()

async def update_user_progress(session: AsyncSession, user_id: int, source_id: int, post_index: int, image_index: int):
    """Обновляет или создает прогресс пользователя с двумя индексами."""
    progress = await get_user_progress(session, user_id, source_id)
    if progress:
        progress.last_post_index = post_index
        progress.last_image_index = image_index
    else:
        progress = UserProgress(
            user_id=user_id,
            source_id=source_id,
            last_post_index=post_index,
            last_image_index=image_index
        )
        session.add(progress)
    await session.commit()
    return progress

async def get_user_ratings_for_export(session: AsyncSession, user_id: int):
    """Получает все оценки пользователя для экспорта."""
    stmt = select(Rating).where(Rating.user_id == user_id).options(
        # Добавляем selectinload(Rating.user), чтобы сразу подгрузить данные пользователя
        selectinload(Rating.user),
        selectinload(Rating.artwork),
        selectinload(Rating.source)
    )
    result = await session.execute(stmt)
    return result.scalars().all()

async def add_query_source(session: AsyncSession, name: str, query_details: dict, owner_id: int):
    """Добавляет новый источник типа 'query'."""
    new_source = Source(
        source_type='query',
        name=name,
        details=query_details,
        owner_id=owner_id
    )
    session.add(new_source)
    await session.commit()
    await session.refresh(new_source)
    return new_source

async def get_all_ratings_for_export(session: AsyncSession):
    """Получает все оценки всех пользователей для экспорта."""
    stmt = select(Rating).options(
        # Здесь эта строка уже была, но для консистентности оставляем
        selectinload(Rating.user),
        selectinload(Rating.artwork),
        selectinload(Rating.source)
    ).order_by(Rating.user_id, Rating.created_at)
    result = await session.execute(stmt)
    return result.scalars().all()