from typing import Optional
import datetime

from sqlalchemy import Boolean, DateTime, ForeignKeyConstraint, Index, Integer, PrimaryKeyConstraint, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, MappedAsDataclass, mapped_column, relationship

class Base(MappedAsDataclass, DeclarativeBase):
    pass


class Channels(Base):
    __tablename__ = 'channels'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='channels_pkey'),
    )

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    thumbnail_url: Mapped[Optional[str]] = mapped_column(String(500))
    raw_data: Mapped[Optional[dict]] = mapped_column(JSONB)
    video_backfill_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'done'")
    )
    video_backfill_offset: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text('1')
    )
    video_backfill_updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime
    )
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))

    videos: Mapped[list['Videos']] = relationship('Videos', back_populates='channel')


class FlywaySchemaHistory(Base):
    __tablename__ = 'flyway_schema_history'
    __table_args__ = (
        PrimaryKeyConstraint('installed_rank', name='flyway_schema_history_pk'),
        Index('flyway_schema_history_s_idx', 'success')
    )

    installed_rank: Mapped[int] = mapped_column(Integer, primary_key=True)
    description: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    script: Mapped[str] = mapped_column(String(1000), nullable=False)
    installed_by: Mapped[str] = mapped_column(String(100), nullable=False)
    installed_on: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text('now()'))
    execution_time: Mapped[int] = mapped_column(Integer, nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    version: Mapped[Optional[str]] = mapped_column(String(50))
    checksum: Mapped[Optional[int]] = mapped_column(Integer)


class Videos(Base):
    __tablename__ = 'videos'
    __table_args__ = (
        ForeignKeyConstraint(['channel_id'], ['channels.id'], ondelete='CASCADE', name='fk_videos_channel'),
        PrimaryKeyConstraint('id', name='videos_pkey')
    )

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    channel_id: Mapped[str] = mapped_column(String(255), nullable=False)
    upload_date: Mapped[Optional[str]] = mapped_column(String(50))
    type: Mapped[Optional[str]] = mapped_column(String(50))
    raw_data: Mapped[Optional[dict]] = mapped_column(JSONB)
    comments_raw_data: Mapped[Optional[dict]] = mapped_column(JSONB)
    analyze_attempts: Mapped[Optional[int]] = mapped_column(Integer, server_default=text('0'))
    last_analyzed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    has_song_list_comment: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=text('false'))
    song_list_comment_raw_data: Mapped[Optional[dict]] = mapped_column(JSONB)
    cleaning_attempts: Mapped[Optional[int]] = mapped_column(Integer, server_default=text('0'))
    last_cleaned_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    cleaned_song_list_comment: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))

    channel: Mapped['Channels'] = relationship('Channels', back_populates='videos')
    songs: Mapped[list['Songs']] = relationship('Songs', back_populates='video')


class Songs(Base):
    __tablename__ = 'songs'
    __table_args__ = (
        ForeignKeyConstraint(['video_id'], ['videos.id'], ondelete='CASCADE', name='fk_songs_video'),
        PrimaryKeyConstraint('id', name='songs_pkey'),
        Index('idx_songs_title_trgm', 'title', postgresql_using='gin'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    video_id: Mapped[str] = mapped_column(String(255), nullable=False)
    timestamp: Mapped[Optional[str]] = mapped_column(String(50))
    analyzed_by_llm: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=text('false'))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))

    video: Mapped['Videos'] = relationship('Videos', back_populates='songs')
