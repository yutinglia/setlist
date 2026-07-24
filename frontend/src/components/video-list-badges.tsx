import { Badge } from "@/components/ui/badge"
import { m } from "@/paraglide/messages"

type VideoType = string | null | undefined

export function videoTypeBadge(type: VideoType): {
  label: string
  variant: "karaoke" | "song" | "muted" | "default"
} {
  switch ((type ?? "").toLowerCase()) {
    case "karaoke":
      return { label: m.badge_karaoke(), variant: "karaoke" }
    case "song":
      return { label: m.badge_song(), variant: "song" }
    case "other":
    case "video":
    case "was_live":
      return { label: m.badge_other(), variant: "muted" }
    default:
      return { label: m.badge_other(), variant: "muted" }
  }
}

type Props = {
  type: VideoType
  hasSetlist?: boolean | null | undefined
  /** When false, hide setlist badge (e.g. song videos have no comments). */
  showSetlist?: boolean
}

/** Type (+ optional setlist) badges for a video row or detail header. */
export function VideoListBadges({
  type,
  hasSetlist,
  showSetlist = true,
}: Props) {
  const kind = videoTypeBadge(type)
  const isSong = (type ?? "").toLowerCase() === "song"
  const showSetlistBadge = showSetlist && !isSong
  return (
    <span className="flex flex-wrap items-center gap-1.5">
      <Badge variant={kind.variant}>{kind.label}</Badge>
      {showSetlistBadge ? (
        <Badge variant={hasSetlist ? "success" : "muted"}>
          {hasSetlist ? m.has_setlist() : m.no_setlist()}
        </Badge>
      ) : null}
    </span>
  )
}
