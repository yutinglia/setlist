from utils.scraper import YouTubeScraper
from utils.comment_analyzer import CommentAnalyzer

def test() -> None:
    video_url = "https://www.youtube.com/watch?v=u0MoCudW5eM"
    scraper = YouTubeScraper(video_url)
    comments = scraper.get_video_top_comments(max_comments=15)
    print(f"Top {len(comments)} comments fetched successfully.")
    analyzer = CommentAnalyzer(comments, minimum_timestamp_count=5)
    has_song_list = analyzer.has_song_list_comment()
    print(f"Has song list comment: {has_song_list}")
    if has_song_list:
        print("Song list comment text:")
        print(analyzer.song_list_comment.get("text", ""))
        song_list = analyzer.extract_song_list()
        print("Extracted Song List:")
        for song in song_list:
            print(f"- {song.title} at {song.timestamp}")

if __name__ == "__main__":
    test()
