import { useEffect, useRef } from "react"

/** Redirect an out-of-range offset page after the server reports a new total. */
export function useClampPage(
  page: number,
  total: number | undefined,
  pageSize: number,
  onPageChange: (page: number) => void,
) {
  const callbackRef = useRef(onPageChange)
  callbackRef.current = onPageChange

  useEffect(() => {
    if (total === undefined || page <= 0) return
    const lastPage = Math.max(0, Math.ceil(total / pageSize) - 1)
    if (page > lastPage) {
      callbackRef.current(lastPage)
    }
  }, [page, pageSize, total])
}
