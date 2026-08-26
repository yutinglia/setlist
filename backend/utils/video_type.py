"""Classify song uploads and multi-song singing streams from title metadata."""

from __future__ import annotations

import re

# Reliable karaoke *stream* markers (not "went to karaoke" vlogs).
_STRONG_KARAOKE_KEYWORDS: tuple[str, ...] = (
    "歌回",
    "karaoke",
    "歌枠",
    "カラok",
    "歌配信",
    "カラオケ",
    "弾き語り",
    "アカペラ",
    "お歌放送",
    "唱聊",
)

# Outings / vlogs that mention karaoke but are not singing streams.
_KARAOKE_EXCLUDE_PHRASES: tuple[str, ...] = (
    "行ってみた",
    "行ってきた",
    "に行って",
    "に行った",
    "へ行った",
    "へ行って",
    "に行きたい",
    "カラオケデート",
    "体験してきた",
    "went to karaoke",
    "karaoke trip",
    "karaoke date",
)
_KARAOKE_CONTEXT_EXCLUDE_RE = re.compile(
    r"(?=.*(?:after\s*party|afterparty))"
    r"(?=.*(?:minecraft|watch(?:[- ]?along|party)|雑談))",
    flags=re.IGNORECASE,
)

# Weaker performance hints — accepted only for archived streams, not ordinary
# uploads. These cover real titles observed in the production archive without
# treating every mention of 「歌」 as a singing stream.
_WEAK_KARAOKE_KEYWORDS: tuple[str, ...] = (
    "singing",
    "sing",
    "歌う",
    "歌います",
    "歌いたい",
    "歌いまく",
    "歌って",
    "うたう",
    "うたって",
    "うたいた",
    "唱歌",
    "歌雜",
    "歌杂",
)
_ADDITIONAL_WEAK_KARAOKE_RE = re.compile(
    r"(?:"
    r"歌練|歌雑|歌雜|歌杂|練(?:練)?歌|练(?:练)?歌|唱唱|"
    r"歌わせて|歌おう|歌ゲリラ|歌リレー|"
    r"\blet['’]?s\s+sings?\b|\bsong\s+show\b|"
    r"(?:只唱|唱一些|來唱唱|来唱唱).{0,18}(?:歌|曲)"
    r")",
    flags=re.IGNORECASE,
)
_LEADING_KARAOKE_LABEL_RE = re.compile(
    r"^\s*(?:【|\[|≪)\s*karaoke\s*(?:】|\]|≫)",
    flags=re.IGNORECASE,
)
_CURRENT_MIXED_SINGING_RE = re.compile(
    r"(?:"
    r"(?:雑談|雜談|闲聊|閒聊).{0,10}(?:と|＆|&|\+).{0,10}歌|"
    r"歌.{0,10}(?:と|＆|&|\+).{0,10}(?:雑談|雜談|闲聊|閒聊)|"
    r"(?:talk|chat).{0,18}(?:sing|song)|"
    r"(?:sing|song).{0,18}(?:talk|chat)"
    r")",
    flags=re.IGNORECASE,
)
_SONG_CATALOG_KARAOKE_RE = re.compile(
    r"(?:"
    r"(?:オリ(?:ジナル)?曲|original\s+songs?).{0,40}"
    r"(?:歌う|歌います|歌って|うたう|sing(?:ing)?)|"
    r"(?:歌う|歌います|歌って|うたう|sing(?:ing)?).{0,40}"
    r"(?:オリ(?:ジナル)?曲|original\s+songs?)"
    r")",
    flags=re.IGNORECASE,
)
_LEADING_SONG_FRAME_RE = re.compile(
    r"^\s*(?:【|\[)\s*(?:歌(?:\s*/\s*song)?|song)\s*(?:】|\])",
    flags=re.IGNORECASE,
)
_MANY_SONGS_COMPLETION_RE = re.compile(
    r"(?<!\d)\d{2,3}\s*曲.{0,8}歌いき",
    flags=re.IGNORECASE,
)

# Standalone song / MV / cover uploads — never scrape setlist comments.
_SONG_KEYWORDS: tuple[str, ...] = (
    "mv",
    "cover",
    "covered by",
    "music video",
    "official video",
    "official live video",
    "official visualizer",
    "lyric video",
    "official audio",
    "original song",
    "歌ってみた",
    "歌って踊ってみた",
    "弾いてみた",
    "オリジナル曲",
    "official music video",
    "カバー",
    "翻唱",
    "カバー曲",
    "オリ曲",
    "原創曲",
    "原创曲",
    "テーマソング",
    "主題曲",
    "主题曲",
    "歌回剪輯",
    "歌回剪辑",
    "歌回純享",
    "歌回纯享",
    "歌唱剪輯",
    "歌唱剪辑",
    "歌枠切り抜き",
    "karaoke clip",
    "singing clip",
    "performance clip",
    "live cut",
    "live session",
)

# English original-song uploads often use a bare bracketed/parenthesized
# ``Original`` instead of the phrase ``original song``.
_SONG_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?:【|\[)\s*original\s*(?:】|\])", flags=re.IGNORECASE),
    re.compile(r"\(\s*original\s*\)", flags=re.IGNORECASE),
    re.compile(
        r"(?<![a-z])original(?:\s+[\w-]+){0,2}\s+song(?![a-z])",
        flags=re.IGNORECASE,
    ),
    re.compile(r"[/／]\s*original\s*(?:】|\])", flags=re.IGNORECASE),
    re.compile(
        r".+\s[-–—]\s.+\(\s*live(?:\s+from\b[^)]*)?\s*\)\s*$",
        flags=re.IGNORECASE,
    ),
)
_SHORT_SONG_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b(?:i|we)\s+(?:sang|tried\s+(?:to\s+sing|singing))\b|"
        r"\bsang\s+it\b",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"(?:【|\[)\s*(?:tried\s+singing(?:\s+and\s+dancing)?|"
        r"singing(?:\s+and\s+dancing)?|vocal\s+only\s+ver\.)"
        r"[!！.。\s]*(?:】|\])",
        flags=re.IGNORECASE,
    ),
    re.compile(r"【女性が歌う】", flags=re.IGNORECASE),
    re.compile(r"^\s*(?:[\"“『「])?singing\s+[\"“『「]", flags=re.IGNORECASE),
    re.compile(r"日常唱歌練習|唱歌默契挑戰|唱歌默契挑战", flags=re.IGNORECASE),
    re.compile(
        r"\bsing(?:-a-long|along|\s+with\s+guitar)\b",
        flags=re.IGNORECASE,
    ),
    re.compile(r"推しカメラ\s*/\s*full\s+ver\.?", flags=re.IGNORECASE),
    re.compile(
        r"(?:【|\[)\s*performance\s+video\s*(?:】|\])",
        flags=re.IGNORECASE,
    ),
)

# 3D concerts/lives are multi-song vocal performances and use the same setlist
# extraction path as karaoke archives. Requiring the marker inside brackets
# avoids recap/watchalong titles that merely mention a 3D live.
_BRACKETED_PERFORMANCE_RE = re.compile(
    r"(?:"
    r"(?:【|\[)[^】\]\r\n]{0,80}"
    r"[3３]\s*[dｄＤ]\s*(?:live|concert|showcase|"
    r"[^】\]\r\n]{0,24}performance(?:\s+live)?)"
    r"[^】\]\r\n]{0,80}(?:】|\])|"
    r"≪[^≫\r\n]{0,80}[3３]\s*[dｄＤ]\s*"
    r"(?:live|concert|showcase|[^≫\r\n]{0,24}performance(?:\s+live)?)"
    r"[^≫\r\n]{0,80}≫"
    r")",
    flags=re.IGNORECASE,
)
_THREED_DEBUT_PERFORMANCE_RE = re.compile(
    r"(?:"
    r"\b[^\r\n]{1,80}(?:['’]s)\s+[3３]\s*[dｄＤ]\s+debut\b|"
    r"[3３]\s*[dｄＤ]\s+debut.{0,80}"
    r"(?:sing(?:ing)?|music|concert|live|stage|歌|ライブ|ステージ)"
    r")",
    flags=re.IGNORECASE,
)
_PERFORMANCE_RE = re.compile(
    r"(?:"
    r"\b(?:birthday|anniversary|acoustic|music|solo|one[- ]man|"
    r"special|spacial)\s+live\b|"
    r"\blive\s+(?:music\s+stream|tour)\b|"
    r"\bsong\s+recital\b|"
    r"\b(?:concert|youtube\s+music\s+weekend)\b|"
    r"生(?:演奏|歌).*ライブ|音楽ライブ|"
    r"(?:誕生日|バースデー|周年(?:記念)?|ワンマン|ソロ|ミニ|コンセプト|"
    r"スペシャル|プチロル?)ライブ|"
    r"ライブツアー|コンサート|"
    r"アンコール\s*[3３]\s*[dｄＤ]\s*live|"
    r"[#＃][^\s#＃]{1,40}[3３]\s*[dｄＤ]\s*ライブ|"
    r"演唱[會会]|音[樂乐][會会]"
    r")",
    flags=re.IGNORECASE,
)
_MINI_LIVE_RE = re.compile(
    r"(?:\bmini\s*live\b|ミニライブ|プチロル?ライブ|"
    r"youtube\s+music\s+weekend)",
    flags=re.IGNORECASE,
)
_PERFORMANCE_EXCLUDE_RE = re.compile(
    r"(?:"
    r"\b(?:re)?watch(?:ing|[- ]?a[- ]?long|along|party)?\b|"
    r"同時(?:視聴|試聴)|一緒に(?:観|見)(?:よう|る)|"
    r"振り返り|振返り|recap|looking\s+back|"
    r"after\s*(?:talk|live)|aftertalk|アフター(?:トーク|ライブ)|"
    r"\bfree\s*talk\b|\bfreetalk\b|\bchat(?:ting)?\b|雑談|"
    r"\b(?:teaser|trailer|preview|digest|highlights?|coming\s+soon|"
    r"pre\W*concert|before\s+(?:the\s+)?concert|"
    r"unbox(?:ing)?|merch|game|gaming|ring\s*fit|documentary|"
    r"behind\s+the\s+scenes|vcr)\b|"
    r"\b(?:reaction|rehearsal|review|countdown|memories)\b|"
    r"\b(?:concert|live)\s+announcements?\b|"
    r"\bannouncements?\s+(?:for|about)\b|"
    r"直前(?:トーク|雑談)?|ダイジェスト|ドキュメンタリー|ゲーム|"
    r"開箱|开箱|"
    r"花絮|感謝名單|感谢名单"
    r")",
    flags=re.IGNORECASE,
)
_PROMOTIONAL_VIDEO_RE = re.compile(
    r"(?:"
    r"\bcoming\s+soon\b|"
    r"\bblu[- ]?ray\s+release\b|"
    r"\b(?:karaoke|singing|microphone|mic)\s+tests?\b|"
    r"(?:予告|預告|预告|告知)\s*(?:pv|映像|動画)|"
    r"(?:歌回|karaoke|concert|live)\s*(?:の|[-:：｜|])?\s*"
    r"(?:予告|預告|预告)|"
    r"(?:予告|預告|预告)\s*(?:の|[-:：｜|])?\s*"
    r"(?:歌回|karaoke|concert|live)|"
    r"(?:演唱[會会]|音[樂乐][會会]).{0,24}(?:預告|预告)|"
    r"(?:預告|预告).{0,24}(?:演唱[會会]|音[樂乐][會会])"
    r")",
    flags=re.IGNORECASE,
)
_NON_SINGING_TOPIC_RE = re.compile(
    r"(?:"
    r"(?:karaoke|concert)\s+(?:set\s*list\s+)?"
    r"(?:planning|reaction|review|rehearsal)|"
    r"(?:planning|reaction|review|rehearsal)\s+"
    r"(?:a\s+|the\s+|my\s+)?(?:karaoke|concert)|"
    r"my\s+concert\s+memories"
    r")",
    flags=re.IGNORECASE,
)
_SETLIST_PLANNING_RE = re.compile(
    r"(?:"
    r"(?:雑談|雜談|闲聊|閒聊|作業|工作|会議|會議).{0,40}"
    r"(?:セトリ|set\s*list).{0,16}(?:決め|考え|組)|"
    r"(?:セトリ|set\s*list).{0,16}(?:決め|考え|組).{0,40}"
    r"(?:雑談|雜談|闲聊|閒聊|作業|工作|会議|會議)"
    r")",
    flags=re.IGNORECASE,
)
_ONE_SONG_GAME_RE = re.compile(
    r"(?:"
    r"(?:遊戲|游戏|game|gaming|play).{0,48}"
    r"(?:只|仅|僅|only|just|and)\s*"
    r"(?:唱(?:一|1)首|sing(?:ing)?\s+(?:a|one)\s+song)"
    r")",
    flags=re.IGNORECASE,
)
_SINGER_SKILL_HASHTAG_RE = re.compile(r"[#＃]歌うま")
_NON_SINGING_REFERENCE_RE = re.compile(
    r"(?:"
    r"(?:歌枠|歌回)(?:の)?(?:振り返り|振返り|回顧|反省会|後日談)|"
    r"(?:歌枠|歌回)(?:企[劃划])?.{0,24}後日談|"
    r"歌枠打ち上げ|"
    r"chatting\s+at\s+the\s+after[- ]party\s+of\s+karaoke|"
    r"preparing\s+for.{0,32}karaoke|準備歌回|"
    r"晚上還有.{0,24}歌回.{0,24}(?:分開待機室|另開待機室)|"
    r"looking\s+back.{0,40}(?:birthday|anniversary|3\s*d|music)?\s*live|"
    r"(?:『|「|[\"“])\s*sing\s*(?:』|」|[\"”]).{0,80}"
    r"(?:同時視聴|watch\s*(?:along|party))|"
    r"(?:不能|不准).{0,10}唱歌|"
    r"(?:will\s+)?chat.{0,20}(?:today|now).{0,30}"
    r"sing.{0,10}(?:anoth(?:a|er)|some\s+other)\s+tim|"
    r"歌回名稱腦力激盪|歌回名称脑力激荡|發想歌回主題|发想歌回主题|"
    r"【\s*雑談\s*】.{0,80}カラオケとお酒|"
    r"【\s*睡前雜談\s*】.{0,100}(?:最近|久違).{0,40}歌回|"
    r"【\s*one\s+hand\s+clapping\s*】|"
    r"(?:[#＃]?歌うま).{0,20}(?:宇宙人狼|人狼|among\s+us)|"
    r"集会.{0,32}歌も歌う|"
    r"(?:唱歌|singing)？.{0,30}(?:恐遊|game|gaming)？.{0,30}"
    r"(?:聊天|chat)？"
    r")",
    flags=re.IGNORECASE,
)
_LEADING_BRACKET_LABEL_RE = re.compile(r"^\s*(?:【([^】]+)】|\[([^\]]+)\])")
_SC_MARKER_RE = re.compile(
    r"(?:スパチャ|super\s*chat|(?<![a-z])s\s*c(?![a-z]))",
    flags=re.IGNORECASE,
)
_CURRENT_SINGING_LABEL_RE = re.compile(
    r"(?:歌枠|歌回|歌[雜杂]|karaoke|singing)",
    flags=re.IGNORECASE,
)
_SC_REFERENCE_RE = re.compile(
    r"(?:"
    r"(?:superchats?|スパチャ).{0,40}(?:from|の).{0,24}"
    r"(?:karaoke|歌枠|歌回)|"
    r"(?:歌枠|歌回)(?<![a-z])s\s*c(?![a-z])"
    r")",
    flags=re.IGNORECASE,
)

# Some creators append ``【KARAOKE/Vsinger[/Vtuber]】`` as a role/category
# boilerplate even on games, talk, and watchalong streams. Only suppress that
# suffix when the remaining title has an explicit non-singing activity and no
# independent singing marker.
_TRAILING_KARAOKE_ROLE_RE = re.compile(
    r"(?:"
    r"【\s*karaoke\s*/\s*v?singer(?:\s*/\s*vtuber)?\s*"
    r"(?:】\s*){1,2}$|"
    r"(?:\s*[░|｜]\s*)?(?:歌[雜杂]\s*[|｜]\s*)?"
    r"(?:singing(?:\s*[＆&]\s*chatting)?|"
    r"chatting\s*[＆&]\s*singing)\s*stream"
    r"(?:\s*【[^】\r\n]{1,80}】)?\s*$|"
    r"【\s*#?歌枠\s*/\s*#?v?singer\s*】\s*$"
    r")",
    flags=re.IGNORECASE,
)
_NON_SINGING_ACTIVITY_RE = re.compile(
    r"(?:"
    r"同時(?:視聴|試聴)|watch\s*(?:along|party)|"
    r"(?<![a-z])talk(?![a-z])|(?<![a-z])chat(?![a-z])|"
    r"雑談|雜談|スパチャ読み|superchat|"
    r"トモコレ|it\s+takes\s+two|ゲーム実況|ゲーム|"
    r"(?<![a-z])game(?:s|play|ing)?(?![a-z])|遊戲|"
    r"開箱|开箱|捏臉|刮刮樂|春聯|鳴潮|blue\s+protocol|"
    r"作業|工作|喝喝酒|拍立得|喉嚨不舒服|振り返り|"
    r"[#＃]重要告知|頻道調整|频道调整"
    r")",
    flags=re.IGNORECASE,
)

VIDEO_TYPE_KARAOKE = "karaoke"
VIDEO_TYPE_SONG = "song"
VIDEO_TYPE_OTHER = "other"

# yt-dlp statuses that are not safe archive records. ``post_live`` is the
# short processing window after a broadcast ends; comments/duration may still
# be incomplete, so discovery waits for ``was_live``.
ACTIVE_LIVE_STATUSES = frozenset({"is_live", "is_upcoming", "post_live"})

# General archives normally meet this floor. Confirmed ``was_live`` records
# and explicit mini lives may be shorter because those formats commonly run
# 5-20 minutes.
KARAOKE_MIN_DURATION_SECONDS = 20 * 60
SHORT_LIVE_KARAOKE_MIN_DURATION_SECONDS = 5 * 60

# Standalone song / MV / cover uploads are usually short.
SONG_MAX_DURATION_SECONDS = 10 * 60


def _title_has_keyword(title: str, keyword: str) -> bool:
    """Case-insensitive substring match; ASCII keywords use word boundaries."""
    if not title or not keyword:
        return False
    # CJK / mixed keywords: plain casefold substring is enough.
    if any(ord(ch) > 127 for ch in keyword):
        return keyword.casefold() in title.casefold()
    pattern = rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])"
    return re.search(pattern, title, flags=re.IGNORECASE) is not None


def _title_has_any(title: str, keywords: tuple[str, ...]) -> bool:
    return any(_title_has_keyword(title, kw) for kw in keywords)


def is_non_singing_reference_title(title: str) -> bool:
    """True when singing words only refer to a different event or activity."""
    if not title:
        return False
    leading = _LEADING_BRACKET_LABEL_RE.match(title)
    label = (
        next((part for part in leading.groups() if part is not None), "")
        if leading is not None
        else ""
    )
    explicit_current_label = bool(
        re.search(r"歌枠|歌回", label, flags=re.IGNORECASE)
        and re.search(r"予告|預告|预告", label, flags=re.IGNORECASE) is None
    )
    if (
        (_PROMOTIONAL_VIDEO_RE.search(title) is not None and not explicit_current_label)
        or _NON_SINGING_TOPIC_RE.search(title) is not None
        or _SETLIST_PLANNING_RE.search(title) is not None
        or _ONE_SONG_GAME_RE.search(title) is not None
        or _NON_SINGING_REFERENCE_RE.search(title) is not None
        or _SC_REFERENCE_RE.search(title) is not None
    ):
        return True

    if leading is None:
        return False
    remainder = title[leading.end() :]
    return bool(
        _SC_MARKER_RE.search(label)
        and _CURRENT_SINGING_LABEL_RE.search(label) is None
        and _CURRENT_SINGING_LABEL_RE.search(remainder)
    )


def is_karaoke_outing_title(title: str) -> bool:
    """True for karaoke mentions whose actual topic is not a singing stream."""
    if not title:
        return False
    if (
        _LEADING_KARAOKE_LABEL_RE.search(title) is not None
        and _CURRENT_MIXED_SINGING_RE.search(title) is not None
    ):
        return False
    folded = title.casefold()
    return (
        any(phrase.casefold() in folded for phrase in _KARAOKE_EXCLUDE_PHRASES)
        or _KARAOKE_CONTEXT_EXCLUDE_RE.search(title) is not None
    )


def is_strong_karaoke_title(title: str) -> bool:
    """True for karaoke *stream* titles; excludes karaoke outing vlogs."""
    if not title:
        return False
    if is_non_singing_reference_title(title):
        return False
    # 歌枠 / 歌回 still win even if the title also jokes about 行ってみた.
    has_definitive = _title_has_any(title, ("歌枠", "歌回", "歌配信"))
    if is_karaoke_outing_title(title) and not has_definitive:
        return False
    bracketed_performance = (
        _BRACKETED_PERFORMANCE_RE.search(title) is not None
        and _PERFORMANCE_EXCLUDE_RE.search(title) is None
    )
    threed_debut_performance = (
        _THREED_DEBUT_PERFORMANCE_RE.search(title) is not None
        and _PERFORMANCE_EXCLUDE_RE.search(title) is None
    )
    performance = (
        _PERFORMANCE_RE.search(title) is not None
        and _PERFORMANCE_EXCLUDE_RE.search(title) is None
    )
    return (
        _title_has_any(title, _STRONG_KARAOKE_KEYWORDS)
        or _LEADING_SONG_FRAME_RE.search(title) is not None
        or _MANY_SONGS_COMPLETION_RE.search(title) is not None
        or bracketed_performance
        or threed_debut_performance
        or performance
    )


def is_weak_karaoke_title(title: str) -> bool:
    if is_karaoke_outing_title(title):
        return False
    if is_non_singing_reference_title(title):
        return False
    content_title = _SINGER_SKILL_HASHTAG_RE.sub("", title)
    return bool(
        _title_has_any(content_title, _WEAK_KARAOKE_KEYWORDS)
        or _ADDITIONAL_WEAK_KARAOKE_RE.search(content_title)
    )


def is_karaoke_title(title: str) -> bool:
    """True when the title looks like a karaoke / singing stream record."""
    return is_strong_karaoke_title(title) or is_weak_karaoke_title(title)


def is_song_title(title: str) -> bool:
    """True when the title looks like a standalone song / MV / cover."""
    return _title_has_any(title, _SONG_KEYWORDS) or any(
        pattern.search(title) for pattern in _SONG_PATTERNS
    )


def is_short_song_performance_title(title: str) -> bool:
    """True for explicit one-off vocal performance titles, before duration gating."""
    return any(pattern.search(title) for pattern in _SHORT_SONG_PATTERNS)


def is_non_singing_branded_title(title: str) -> bool:
    """True when a trailing karaoke role tag conflicts with the real topic."""
    if not title or _TRAILING_KARAOKE_ROLE_RE.search(title) is None:
        return False
    content_title = _TRAILING_KARAOKE_ROLE_RE.sub(" ", title)
    has_independent_singing_marker = is_strong_karaoke_title(
        content_title
    ) or is_weak_karaoke_title(content_title)
    return (
        not has_independent_singing_marker
        and _NON_SINGING_ACTIVITY_RE.search(content_title) is not None
    )


def _karaoke_live_status_ok(live_status: str | None) -> bool:
    """Soft confirm for *weak* karaoke only: unknown OK; known non-archives rejected.

    Strong title markers (歌枠 / KARAOKE / …) do not use this — Videos-tab VODs
    and reuploads are often ``not_live`` even when they are karaoke archives.
    """
    if live_status is None or live_status == "":
        return True
    return live_status == "was_live"


def _karaoke_duration_ok(
    duration: float | int | None,
    *,
    live_status: str | None,
    title: str,
) -> bool:
    """Soft confirm: unknown OK; known short clips rejected."""
    if duration is None:
        return True
    try:
        seconds = float(duration)
    except (TypeError, ValueError):
        return True
    minimum = (
        SHORT_LIVE_KARAOKE_MIN_DURATION_SECONDS
        if (live_status or "").casefold() == "was_live"
        or _MINI_LIVE_RE.search(title) is not None
        else KARAOKE_MIN_DURATION_SECONDS
    )
    return seconds >= minimum


def _song_duration_ok(duration: float | int | None) -> bool:
    """Soft confirm: unknown OK; known long videos rejected.

    When duration is present, standalone songs must be shorter than
    ``SONG_MAX_DURATION_SECONDS`` (default 10 minutes).
    """
    if duration is None:
        return True
    try:
        seconds = float(duration)
    except (TypeError, ValueError):
        return True
    return seconds <= SONG_MAX_DURATION_SECONDS


def is_song_video(
    title: str,
    *,
    duration: float | int | None = None,
) -> bool:
    """Standalone song/MV/cover: title keywords + soft short-duration confirm."""
    if _PROMOTIONAL_VIDEO_RE.search(title) is not None:
        return False
    return (
        is_song_title(title) or is_short_song_performance_title(title)
    ) and _song_duration_ok(duration)


def is_karaoke_stream(
    title: str,
    *,
    live_status: str | None = None,
    duration: float | int | None = None,
) -> bool:
    """True only for karaoke stream archives worth setlist comment scraping.

    Priority:
    1. Strong stream/performance keywords (歌枠 / KARAOKE / 弾き語り /
       bracketed 3D LIVE / …) + soft duration confirm (``live_status`` is
       ignored — strong titles are reliable enough)
    2. Song/MV/cover keywords → never karaoke (no comment scrape)
    3. Weak singing phrases + soft ``was_live`` / duration confirms

    Outing titles like 「カラオケ行ってみた」 are excluded.
    """
    if (live_status or "").casefold() in ACTIVE_LIVE_STATUSES:
        return False
    if not _karaoke_duration_ok(duration, live_status=live_status, title=title):
        return False
    if is_non_singing_reference_title(title):
        return False
    if is_non_singing_branded_title(title):
        return False
    if is_strong_karaoke_title(title):
        return True
    if is_song_title(title) and _SONG_CATALOG_KARAOKE_RE.search(title) is None:
        return False
    if not _karaoke_live_status_ok(live_status):
        return False
    return is_weak_karaoke_title(title)


def should_scrape_comments(
    title: str,
    *,
    live_status: str | None = None,
    duration: float | int | None = None,
    stored_type: str | None = None,
) -> bool:
    """Whether this video should have comments fetched for setlist extraction.

    Re-evaluates from title/metadata. ``stored_type == song`` always blocks.
    """
    if (stored_type or "").lower() == VIDEO_TYPE_SONG:
        return False
    return is_karaoke_stream(title, live_status=live_status, duration=duration)


def classify_video_type(
    title: str,
    *,
    live_status: str | None = None,
    duration: float | int | None = None,
) -> str:
    """Return ``karaoke``, ``song``, or ``other``.

    Karaoke: strong stream/performance keywords + a soft duration floor when
    duration is known (5 minutes for confirmed archives and explicit mini
    lives, otherwise 20). Weak singing phrases also need soft ``was_live``.
    Song: MV/cover/official/… keywords + soft ``< 10 min``.
    Missing duration does not block either class (flat-extract gaps).
    """
    if is_karaoke_stream(title, live_status=live_status, duration=duration):
        return VIDEO_TYPE_KARAOKE
    if is_song_video(title, duration=duration):
        return VIDEO_TYPE_SONG
    # A short non-live upload with an otherwise strong singing marker is a
    # standalone performance/clip, not a multi-song archive to scrape.
    if (
        (live_status or "").casefold() != "was_live"
        and is_strong_karaoke_title(title)
        and _PERFORMANCE_EXCLUDE_RE.search(title) is None
        and _PROMOTIONAL_VIDEO_RE.search(title) is None
        and _song_duration_ok(duration)
        and duration is not None
    ):
        return VIDEO_TYPE_SONG
    return VIDEO_TYPE_OTHER
