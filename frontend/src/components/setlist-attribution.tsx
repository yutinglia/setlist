import { ExternalLink, MessageSquareText } from "lucide-react"

import {
  youtubeChannelUrl,
  youtubeCommentUrl,
} from "@/lib/youtube"
import { cn } from "@/lib/utils"
import { m } from "@/paraglide/messages"

export function SetlistAttribution({
  author,
  authorId,
  commentId,
  videoId,
  className,
}: {
  author: string | null | undefined
  authorId: string | null | undefined
  commentId: string | null | undefined
  videoId: string
  className?: string
}) {
  if (!author) return null

  return (
    <div
      className={cn(
        "flex min-w-0 flex-wrap items-center gap-x-1.5 text-xs text-muted-foreground",
        className,
      )}
    >
      <MessageSquareText className="size-3.5 shrink-0" aria-hidden />
      <span className="shrink-0">{m.setlist_credit_prefix()}</span>
      {authorId ? (
        <a
          href={youtubeChannelUrl(authorId)}
          target="_blank"
          rel="noreferrer"
          className="inline-flex min-h-11 min-w-0 items-center truncate rounded-lg px-1 font-semibold text-foreground underline-offset-2 hover:bg-secondary hover:text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {author}
        </a>
      ) : (
        <span className="truncate font-semibold text-foreground">{author}</span>
      )}
      {commentId ? (
        <a
          href={youtubeCommentUrl(videoId, commentId)}
          target="_blank"
          rel="noreferrer"
          className="grid size-11 shrink-0 place-items-center rounded-xl text-muted-foreground transition-colors hover:bg-secondary hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          aria-label={m.setlist_source_comment()}
          title={m.setlist_source_comment()}
        >
          <ExternalLink className="size-3.5" aria-hidden />
        </a>
      ) : null}
    </div>
  )
}
