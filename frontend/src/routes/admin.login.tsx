import { createFileRoute, redirect } from "@tanstack/react-router"
import { KeyRound, LogIn, ShieldCheck } from "lucide-react"
import { useState, type FormEvent } from "react"

import { ApiError } from "@/api/client"
import { authSessionQueryOptions, useLogin } from "@/api/hooks"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { PageMetadata } from "@/components/page-metadata"
import { loginSearchSchema } from "@/lib/search-schemas"
import { m } from "@/paraglide/messages"

export const Route = createFileRoute("/admin/login")({
  validateSearch: loginSearchSchema,
  beforeLoad: async ({ context }) => {
    const session = await context.queryClient
      .ensureQueryData(authSessionQueryOptions(context.api))
      .catch(() => null)
    if (session?.authenticated && session.role === "admin") {
      throw redirect({ to: "/status" })
    }
  },
  component: AdminLoginPage,
})

function safeReturnTo(value: string | undefined): string {
  if (!value?.startsWith("/") || value.startsWith("//")) return "/status"
  return value
}

function AdminLoginPage() {
  const { returnTo } = Route.useSearch()
  const login = useLogin()
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError("")
    try {
      await login.mutateAsync({ username: username.trim(), password })
      window.location.assign(safeReturnTo(returnTo))
    } catch (caught) {
      setPassword("")
      if (caught instanceof ApiError && caught.status === 429) {
        setError(m.auth_rate_limited())
      } else if (caught instanceof ApiError && caught.status === 503) {
        setError(m.auth_not_configured())
      } else {
        setError(m.auth_invalid())
      }
    }
  }

  return (
    <section className="animate-fade mx-auto flex w-full max-w-5xl flex-1 items-center py-10 sm:py-16 lg:py-20">
      <PageMetadata
        path="/admin/login"
        title={`${m.auth_login_heading()} | Setlist`}
        description={m.auth_login_hint()}
        noIndex
      />
      <div className="surface grid w-full overflow-hidden md:grid-cols-[minmax(17rem,0.85fr)_minmax(0,1.15fr)]">
        <div className="relative isolate overflow-hidden border-b border-border bg-secondary/50 px-6 py-8 md:border-r md:border-b-0 md:px-8 md:py-10 lg:px-10 lg:py-14">
          <div className="pointer-events-none absolute -top-24 -left-20 -z-10 size-64 rounded-full bg-primary/15 blur-3xl" />
          <span className="grid size-12 place-items-center rounded-2xl bg-primary text-primary-foreground shadow-lg">
            <ShieldCheck className="size-5" aria-hidden />
          </span>
          <p className="eyebrow mt-8">{m.auth_admin_only()}</p>
          <h1 className="mt-3 text-3xl font-bold tracking-[-0.035em] sm:text-4xl">
            {m.auth_login_heading()}
          </h1>
          <p className="mt-4 max-w-sm text-sm leading-7 text-muted-foreground">
            {m.auth_login_hint()}
          </p>
        </div>

        <form
          className="space-y-6 bg-card p-6 sm:p-8 lg:p-12"
          onSubmit={(event) => void handleSubmit(event)}
        >
          <div>
            <label className="text-sm font-semibold" htmlFor="admin-username">
              {m.auth_username()}
            </label>
            <Input
              id="admin-username"
              name="username"
              autoComplete="username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              maxLength={128}
              className="mt-2"
              disabled={login.isPending}
              autoFocus
              required
            />
          </div>
          <div>
            <label className="text-sm font-semibold" htmlFor="admin-password">
              {m.auth_password()}
            </label>
            <div className="relative mt-2">
              <KeyRound
                className="pointer-events-none absolute top-1/2 left-3.5 size-4 -translate-y-1/2 text-muted-foreground"
                aria-hidden
              />
              <Input
                id="admin-password"
                name="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                maxLength={256}
                className="pl-10"
                disabled={login.isPending}
                required
              />
            </div>
          </div>

          {error ? (
            <p
              className="rounded-xl bg-destructive/10 px-4 py-3 text-sm text-destructive"
              role="alert"
            >
              {error}
            </p>
          ) : null}

          <Button
            type="submit"
            size="lg"
            className="w-full"
            disabled={login.isPending || !username.trim() || !password}
          >
            <LogIn aria-hidden />
            {login.isPending ? m.auth_signing_in() : m.auth_sign_in()}
          </Button>
        </form>
      </div>
    </section>
  )
}
