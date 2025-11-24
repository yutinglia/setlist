import yt_dlp
from models.channel import YouTubeChannel


class YouTubeChannelScraper:
    def __init__(self) -> None:
        self.channel: YouTubeChannel | None = None

    def get_channel_info(self, channel_url: str) -> YouTubeChannel:
        ydl_opts = {
            "skip_download": True,
            "playlist_items": "0",
            "extract_flat": True,
            # "quiet": True,
            # speed limit
            "sleep_interval": 1,
            "max_sleep_interval": 2,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(channel_url, download=False)

            print(info.keys())

            # get channel avatar thumbnail, id = avatar_uncropped
            thumbnail_url = ""
            thumbnails = info.get("thumbnails", [])
            for thumb in thumbnails:
                if thumb.get("id") == "avatar_uncropped":
                    thumbnail_url = thumb.get("url", "")
                    break

            self.channel = YouTubeChannel(
                channel_id=info.get("id", ""),
                name=info.get("uploader", ""),
                url=channel_url,
                thumbnail_url=thumbnail_url,
                raw_data=info,
            )

            return self.channel
