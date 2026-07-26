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
    <article className="animate-fade mx-auto w-full max-w-4xl py-10 sm:py-14">
      <header className="border-b border-border/70 pb-8">
        <p className="eyebrow">{eyebrow}</p>
        <h1 className="mt-3 font-display text-4xl font-bold tracking-tight sm:text-5xl">
          {title}
        </h1>
        <p className="mt-4 max-w-3xl text-base leading-7 text-muted-foreground">
          {intro}
        </p>
      </header>
      <div className="mt-8 space-y-8">{children}</div>
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
    <section className="surface p-5 sm:p-7">
      <h2 className="font-display text-xl font-bold tracking-tight">{title}</h2>
      <div className="mt-3 space-y-3 text-sm leading-7 text-muted-foreground">
        {children}
      </div>
    </section>
  )
}
