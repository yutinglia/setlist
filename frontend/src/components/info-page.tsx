import type { ReactNode } from "react"

export function InfoPage({
  eyebrow,
  title,
  intro,
  children,
}: {
  eyebrow: string
  title: string
  intro: string
  children: ReactNode
}) {
  return (
    <article className="animate-fade mx-auto w-full max-w-6xl py-7 sm:py-10 lg:py-12">
      <header className="relative isolate overflow-hidden rounded-3xl border border-border/80 bg-card px-6 py-8 sm:px-9 sm:py-10 lg:px-12 lg:py-14">
        <div className="pointer-events-none absolute -top-28 -right-20 -z-10 size-72 rounded-full bg-primary/10 blur-3xl" />
        <div className="max-w-3xl">
          <p className="eyebrow">{eyebrow}</p>
          <h1 className="page-title mt-3">{title}</h1>
          <p className="page-intro mt-5">{intro}</p>
        </div>
      </header>
      <div className="surface mt-6 divide-y divide-border/75 overflow-hidden">
        {children}
      </div>
    </article>
  )
}

export function InfoSection({
  title,
  children,
}: {
  title: string
  children: ReactNode
}) {
  return (
    <section className="grid gap-4 px-5 py-7 sm:px-8 sm:py-9 lg:grid-cols-[minmax(11rem,0.36fr)_minmax(0,1fr)] lg:gap-10 lg:px-10">
      <h2 className="text-xl font-bold tracking-[-0.02em] sm:text-2xl">
        {title}
      </h2>
      <div className="space-y-4 text-[0.95rem] leading-7 text-muted-foreground">
        {children}
      </div>
    </section>
  )
}
