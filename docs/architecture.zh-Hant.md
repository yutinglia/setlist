# 後端與前端依賴架構

## 後端組裝

`backend/container.py` 是 composition root。它持有程序層級資源，包括資料庫
engine／pool、可選 cache client、驗證 service、updater 狀態與喚醒器、
YouTube operation coordinator、冷卻狀態、scraper factory、scrape executor
與可選 LLM cleaner，並以單一 SQLAlchemy session 建立 request-scoped
use-case。

`backend/deps.py` 中的 FastAPI dependency 會從 `app.state` 取得 container、
開啟 session，再提供 query 或 command service。Router 不會自行建立
repository、Redis client 或 scraper 實作。

主要邊界採用：

- service collaborator 使用 constructor injection；
- 由 composition root 選擇具體 infrastructure；
- 資料庫存取使用 repository pattern；
- HTTP use-case 使用 application／query service；
- blocking scraper 執行使用 strategy／factory adapter；
- 公開查詢的可選快取使用 cache-aside；
- 停用快取時注入 null object（`NullCacheBackend`）。

`DataUpdater`、`ChannelCreator` 與 `StoredDataReanalyzer` 仍持有 transaction
所有權。只有 commit 成功後才使快取失效；repository 仍不會 commit。

## 可選 Redis 或 Valkey

將 `CACHE_URL` 設為相容的 Redis URL 即可。Valkey 可直接使用既有 Redis
client library，因此兩者共用同一 adapter。未設定 URL 時，container 會注入
no-op backend，且不會建立任何快取連線。

公開 catalog 與 summary 查詢會序列化成經 Pydantic 驗證的 JSON。Cache key
含 schema version 與正規化參數雜湊；異動會使 catalog 與 report namespace
失效。讀取、寫入、失效與健康檢查若失敗都會 fail-open：請求改由 PostgreSQL
提供，並限制重複錯誤 log。

啟用內建的可選服務：

```bash
CACHE_URL=redis://cache:6379/0 docker compose --profile cache up -d
```

Cache 不會對主機公開 port，且不啟用持久化，因為其中只有可重建的衍生回應。

## 測試與替換

測試可用替換過的 immutable settings 與 fake 建立
`ApplicationContainer`，或只 override route 所需的窄 FastAPI provider。
單元測試使用 `MemoryCacheBackend`、注入的 scraper factory／executor 與
service fake，不修改 production module global。

## 前端

`createApiClient` 接受 base URL 與 `fetch` 實作。`main.tsx` 建立 production
instance，並透過 `ApiProvider` 與 TanStack Router context 注入。React hook
從 provider 取用，route guard 則從 router context 取用。這已足以涵蓋目前
前端 DI：TanStack Query 管理 server state、Zustand 管理 UI preference，
component 使用一般 props。
