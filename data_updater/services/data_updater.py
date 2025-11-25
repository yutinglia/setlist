from repositories.channel_repository import ChannelRepository
from repositories.video_repository import VideoRepository
from repositories.song_repository import SongRepository


class DataUpdater:
    """負責資料更新的業務邏輯"""

    def __init__(
        self,
        channel_repo: ChannelRepository,
        video_repo: VideoRepository,
        song_repo: SongRepository,
    ):
        self.channel_repo = channel_repo
        self.video_repo = video_repo
        self.song_repo = song_repo

    async def update(self):
        # get channel list from database
        channels = await self.channel_repo.get_all()
        print(f"Fetched {len(channels)} channels from the database.")
        print("Channels:", channels)
