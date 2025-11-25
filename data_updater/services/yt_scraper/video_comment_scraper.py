import yt_dlp
from typing import Any


class YouTubeVideoCommentScraper:
    def __init__(self, video_url: str) -> None:
        self.video_url = video_url

    def get_video_top_comments(self, max_comments: int) -> list[dict[str, Any]]:

        ydl_opts = {
            "skip_download": True,
            "getcomments": True,
            "quiet": True,
            # speed limit
            "sleep_interval": 1,
            "max_sleep_interval": 2,
            "extractor_args": {
                "youtube": {
                    # max-comments, max-parents, max-replies, max-replies-per-thread
                    "max_comments": [str(max_comments), str(max_comments), "0", "0"],
                    "comment_sort": ["top"],
                }
            },
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(self.video_url, download=False)
            comments = info.get("comments", [])
            return comments
