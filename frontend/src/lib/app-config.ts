/** Build-time UI capabilities. Mutating scraper controls stay hidden in prod. */
export const MANAGEMENT_UI_ENABLED =
  import.meta.env.DEV ||
  import.meta.env.VITE_MANAGEMENT_UI_ENABLED?.trim().toLowerCase() === "true"
