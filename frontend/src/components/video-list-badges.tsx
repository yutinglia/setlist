import { Badge } from "@/components/ui/badge"
import { m } from "@/paraglide/messages"

type VideoType = string | null | undefined

function typeBadge(type: VideoType): {
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
  hasSetlist: boolean | null | undefined
}

/** Type + setlist badges for a channel video row. */
export function VideoListBadges({ type, hasSetlist }: Props) {
  const kind = typeBadge(type)
  return (
    <span className="flex flex-wrap items-center gap-1.5">
      <Badge variant={kind.variant}>{kind.label}</Badge>
      <Badge variant={hasSetlist ? "success" : "muted"}>
        {hasSetlist ? m.has_setlist() : m.no_setlist()}
      </Badge>
    </span>
  )
}
