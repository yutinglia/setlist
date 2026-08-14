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

管理員頻道 ingest 具有可持續復原的冷卻 fallback。正常狀態下，
`ChannelCreator` 仍會在 request 內同步解析；shared 或資料庫冷卻啟用時，
則只把正規化網址寫入 `channel_ingest_queue`，該 transaction 不呼叫 YouTube，
也不使公開快取失效。之後的 updater cycle 會先在既有程序內／PostgreSQL
YouTube lock 與管理員節流下依 FIFO 解析 pending row。建立頻道與完成 queue
row 共用同一 transaction；遇到封鎖時記錄嘗試與全域冷卻但保留 pending，
取消或崩潰則 rollback 整筆工作以便重試。

## 可選 Redis 或 Valkey

將 `CACHE_URL` 設為相容的 Redis URL 即可。Valkey 可直接使用既有 Redis
client library，因此兩者共用同一 adapter。未設定 URL 時，container 會注入
no-op backend，且不會建立任何快取連線。

公開 search、catalog 與 summary 查詢會序列化成經 Pydantic 驗證的 JSON。
Cache key 含 schema version 與正規化參數雜湊；只有會改變公開資料的 commit
才會使三個 namespace 失效，沒有工作的 channel 與單純 cooldown commit
不會清空快取。
搜尋、catalog、report 分別使用 15 分鐘、1 小時、5 分鐘的 stale-data 安全
上限。讀取、寫入、失效與健康檢查若失敗都會 fail-open：請求改由 PostgreSQL
提供、短暫 backoff 以避免重複 cache timeout，並限制重複錯誤 log。
Invalidation 失敗的 namespace 會持續 bypass，直到清除成功，因此延長 TTL
不會讓已 commit 異動之前的舊回應重新出現。API 啟動時也會以 fail-open 方式
清除 namespace，涵蓋前一個 process 留下的 key。

| Namespace | 公開 GET endpoint | 預設 TTL |
| --- | --- | --- |
| `search` | `/v1/songs/search`、`/v1/songs/suggestions` | 15 分鐘 |
| `catalog` | 歌曲、貢獻者、頻道、影片與影片歌曲的瀏覽／詳細資料 route | 1 小時 |
| `report` | `/v1/report/summary` | 5 分鐘 |

`/v1/health` 維持即時查詢；驗證與 updater status 回應為 `no-store`，mutation
永遠不做 response cache。帶有效管理員 session 的 API 回應也由 middleware
加入 `Cache-Control: no-store`。Frontend proxy 不會替 `/v1` 增加 HTTP
response cache；Valkey 是共用 server-side cache，TanStack Query 則管理每個
browser 的 server-state cache。

啟用內建的可選服務：

```bash
CACHE_URL=redis://cache:6379/0 docker compose --profile cache up -d
```

Cache 不會對主機公開 port，且不啟用持久化，因為其中只有可重建的衍生回應。
內建 128 MiB 容器會設定 Valkey `maxmemory=80mb`、`allkeys-lru` 與 5% 的
client 總記憶體限制，先淘汰可重建 key，再接近容器上限，且不依賴 swap。

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

首頁 hero 與頂部 compact 搜尋共用 `SearchForm` 的建議 combobox，包括
debounce、鍵盤操作與 ARIA 狀態。首頁 route 不渲染 compact 頂部搜尋，因此只
保留 hero 搜尋控制項。
