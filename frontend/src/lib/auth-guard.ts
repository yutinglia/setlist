import type { QueryClient } from "@tanstack/react-query"
import { redirect } from "@tanstack/react-router"

import { authSessionQueryOptions } from "@/api/hooks"

export async function requireAdminRoute({
  context,
  location,
}: {
  context: { queryClient: QueryClient }
  location: { href: string }
}) {
  try {
    const session = await context.queryClient.ensureQueryData(
      authSessionQueryOptions,
    )
    if (session.authenticated && session.role === "admin") {
      return
    }
  } catch {
    // The login page will surface API/configuration errors.
  }
  const returnTo = location.href.startsWith("/") ? location.href : "/"
  throw redirect({
    to: "/admin/login",
    search: { returnTo },
  })
}

export async function requireManagementRoute(
  args: Parameters<typeof requireAdminRoute>[0],
) {
  const session = await args.context.queryClient
    .ensureQueryData(authSessionQueryOptions)
    .catch(() => null)
  if (
    session?.authenticated &&
    session.role === "admin" &&
    session.management_enabled
  ) {
    return
  }
  if (session?.authenticated && session.role === "admin") {
    throw redirect({ to: "/channels" })
  }
  return requireAdminRoute(args)
}
