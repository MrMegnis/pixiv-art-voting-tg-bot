from sqlalchemy import (BigInteger, Boolean, Column, ForeignKey, Integer,
                        String, JSON, DateTime, UniqueConstraint)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

Base = declarative_base()


class User(Base):
    __tablename__ = 'users'
    user_id = Column(BigInteger, primary_key=True)
    username = Column(String, nullable=True)
    is_authorized = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())

    sources = relationship("Source", back_populates="owner")
    ratings = relationship("Rating", back_populates="user")
    progress = relationship("UserProgress", back_populates="user")


class Artwork(Base):
    __tablename__ = 'artworks'

    # Добавляем свой автоинкрементный ID как первичный ключ
    id = Column(Integer, primary_key=True, autoincrement=True)

    # ID поста на Pixiv больше не первичный ключ, а просто поле
    pixiv_id = Column(BigInteger, nullable=False)
    # Индекс картинки внутри поста (0 для одиночных, 0, 1, 2... для серий)
    image_index = Column(Integer, default=0, nullable=False)

    title = Column(String)
    author = Column(String)
    url = Column(String)
    other_data = Column(JSON)

    # Гарантируем, что пара (ID поста, индекс картинки) будет уникальной
    __table_args__ = (UniqueConstraint('pixiv_id', 'image_index', name='_pixiv_id_image_index_uc'),)


class Source(Base):
    __tablename__ = 'sources'
    source_id = Column(Integer, primary_key=True, autoincrement=True)
    source_type = Column(String)  # 'file' or 'query'
    name = Column(String)
    details = Column(JSON) # path for file, search params for query
    owner_id = Column(BigInteger, ForeignKey('users.user_id'), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    owner = relationship("User", back_populates="sources")
    ratings = relationship("Rating", back_populates="source")
    progress = relationship("UserProgress", back_populates="source")


class Rating(Base):
    __tablename__ = 'ratings'
    rating_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('users.user_id'), nullable=False)

    # Теперь ссылаемся на наш новый первичный ключ в таблице Artwork
    artwork_id = Column(Integer, ForeignKey('artworks.id'), nullable=False)

    source_id = Column(Integer, ForeignKey('sources.source_id'), nullable=False)
    score = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="ratings")
    artwork = relationship("Artwork", back_populates=None)
    source = relationship("Source", back_populates="ratings")

    # Уникальность оценки теперь на связку (пользователь, наша уникальная картинка)
    __table_args__ = (UniqueConstraint('user_id', 'artwork_id', name='_user_artwork_uc'),)


class UserProgress(Base):
    __tablename__ = 'user_progress'
    user_id = Column(BigInteger, ForeignKey('users.user_id'), primary_key=True)
    source_id = Column(Integer, ForeignKey('sources.source_id'), primary_key=True)

    # Теперь храним два индекса: для поста и для картинки в посте
    last_post_index = Column(Integer, default=0)
    last_image_index = Column(Integer, default=0)

    user = relationship("User", back_populates="progress")
    source = relationship("Source", back_populates="progress")