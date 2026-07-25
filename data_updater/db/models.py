from typing import Optional
import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKeyConstraint, Index, Integer, PrimaryKeyConstraint, SmallInteger, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, MappedAsDataclass, mapped_column, relationship

class Base(MappedAsDataclass, DeclarativeBase):
    pass


class Channels(Base):
    __tablename__ = 'channels'
    __table_args__ = (
        CheckConstraint('video_backfill_offset >= 1', name='chk_channels_video_backfill_offset'),
        CheckConstraint("video_backfill_status::text = ANY (ARRAY['pending'::character varying, 'running'::character varying, 'done'::character varying, 'failed'::character varying]::text[])", name='chk_channels_video_backfill_status'),
        CheckConstraint('video_scan_failures >= 0', name='ck_channels_video_scan_failures_nonnegative'),
        PrimaryKeyConstraint('id', name='channels_pkey'),
        Index('idx_channels_discovery_due', 'video_backfill_status', 'next_video_scan_at', 'video_backfill_updated_at')
    )

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    video_backfill_status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'done'::character varying"))
    video_backfill_offset: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('1'))
    video_scan_failures: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('0'))
    thumbnail_url: Mapped[Optional[str]] = mapped_column(String(500))
    raw_data: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))
    video_backfill_updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    last_video_scan_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    next_video_scan_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)

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


class ScraperState(Base):
    __tablename__ = 'scraper_state'
    __table_args__ = (
        CheckConstraint('id = 1', name='scraper_state_id_check'),
        PrimaryKeyConstraint('id', name='scraper_state_pkey')
    )

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, server_default=text('1'))
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    youtube_cooldown_until: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class Videos(Base):
    __tablename__ = 'videos'
    __table_args__ = (
        CheckConstraint("analysis_status::text = ANY (ARRAY['pending'::character varying, 'retry'::character varying, 'no_setlist'::character varying, 'done'::character varying, 'exhausted'::character varying, 'skipped'::character varying]::text[])", name='ck_videos_analysis_status'),
        CheckConstraint('analyze_attempts >= 0', name='ck_videos_analyze_attempts_nonnegative'),
        CheckConstraint('cleaning_attempts >= 0', name='ck_videos_cleaning_attempts_nonnegative'),
        CheckConstraint('playlist_position IS NULL OR playlist_position >= 1', name='ck_videos_playlist_position_positive'),
        ForeignKeyConstraint(['channel_id'], ['channels.id'], ondelete='CASCADE', name='fk_videos_channel'),
        PrimaryKeyConstraint('id', name='videos_pkey'),
        Index('idx_videos_analysis_queue', 'analysis_status', 'next_analysis_at', 'upload_date', 'playlist_position', 'id', postgresql_where="((type)::text = 'karaoke'::text)"),
        Index('idx_videos_channel_analysis', 'channel_id', 'type', 'has_song_list_comment', 'analyze_attempts'),
        Index('idx_videos_channel_upload_date', 'channel_id', 'upload_date', 'id')
    )

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    channel_id: Mapped[str] = mapped_column(String(255), nullable=False)
    analyze_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('0'))
    has_song_list_comment: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    cleaning_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('0'))
    analysis_status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'pending'::character varying"))
    upload_date: Mapped[Optional[str]] = mapped_column(String(50))
    type: Mapped[Optional[str]] = mapped_column(String(50))
    raw_data: Mapped[Optional[dict]] = mapped_column(JSONB)
    comments_raw_data: Mapped[Optional[dict]] = mapped_column(JSONB)
    last_analyzed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    song_list_comment_raw_data: Mapped[Optional[dict]] = mapped_column(JSONB)
    last_cleaned_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    cleaned_song_list_comment: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))
    next_analysis_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    playlist_position: Mapped[Optional[int]] = mapped_column(Integer)

    channel: Mapped['Channels'] = relationship('Channels', back_populates='videos')
    songs: Mapped[list['Songs']] = relationship('Songs', back_populates='video')


class Songs(Base):
    __tablename__ = 'songs'
    __table_args__ = (
        ForeignKeyConstraint(['video_id'], ['videos.id'], ondelete='CASCADE', name='fk_songs_video'),
        PrimaryKeyConstraint('id', name='songs_pkey'),
        Index('idx_songs_title_trgm', 'title', postgresql_ops={'title': 'gin_trgm_ops'}, postgresql_using='gin'),
        Index('idx_songs_video_id_id', 'video_id', 'id')
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    video_id: Mapped[str] = mapped_column(String(255), nullable=False)
    analyzed_by_llm: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    timestamp: Mapped[Optional[str]] = mapped_column(String(50))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))

    video: Mapped['Videos'] = relationship('Videos', back_populates='songs')
