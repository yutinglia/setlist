import type { PropsWithChildren } from "react"

import type { ApiClient } from "@/api/client"
import { ApiContext } from "@/api/context"

export function ApiProvider({
  client,
  children,
}: PropsWithChildren<{ client: ApiClient }>) {
  return <ApiContext.Provider value={client}>{children}</ApiContext.Provider>
}
