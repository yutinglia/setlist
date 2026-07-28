# Setlist 後端

後端是 FastAPI 服務，負責查詢 PostgreSQL catalog，並執行有節流的 yt-dlp
匯入及分析 pipeline。PostgreSQL 是唯一真實來源；Redis 或 Valkey 只能選擇性
快取公開讀取回應，不是啟動或正確性所必需。

匯入路徑刻意以 `backend/` 為工作目錄根目錄，因此下列指令需在此目錄執行。

## 本機開發

先從 repository 根目錄啟動並 migrate PostgreSQL：

```bash
docker compose -f docker-compose.dev.yml up -d db flyway
```

接著安裝並啟動 API：

```bash
python -m pip install -r requirements-dev.txt
APP_ENV=dev BACKGROUND_UPDATER_ENABLED=false \
  uvicorn main:app --host 0.0.0.0 --port 8000
```

PowerShell 請先設定環境變數：

```powershell
$env:APP_ENV = "dev"
$env:BACKGROUND_UPDATER_ENABLED = "false"
uvicorn main:app --host 0.0.0.0 --port 8000
```

健康檢查是 `GET /v1/health`；開發環境可使用 `/docs` 查看 OpenAPI。除非已設定
`ADMIN_PASSWORD_HASH` 與 `SESSION_SECRET`，否則管理員登入仍會 fail-closed。

不啟動週期迴圈、只執行一次與 production 相同的 updater 路徑：

```bash
python run_updater_once.py
```

## 架構與依賴注入

`container.ApplicationContainer` 是 composition root，持有 process 範圍資源及
policy，並以單一 SQLAlchemy session 建立 request 範圍 service。

```text
FastAPI route
  -> deps.py dependency provider
    -> query/use-case service
      -> repository 或 infrastructure port
        -> PostgreSQL / Redis-compatible cache / yt-dlp
```

主要設計邊界如下：

- app factory 與 composition root 管理資源生命週期及 wiring；
- authentication、repository、cache、scraper factory/executor、updater
  status、cooldown 與 operation coordinator 全部採 constructor injection；
- SQL 存取與 mapping 使用 repository pattern；
- application query/service layer 讓 route 不需知道 cache 序列化細節；
- 同步 yt-dlp 元件外層採 factory 與 strategy pattern；
- 可選回應快取採 cache-aside 與 null object；
- `DataUpdater`、`ChannelCreator`、`StoredDataReanalyzer` 明確持有 transaction。

具體 infrastructure 的選擇應留在 `container.py`。測試應經由 constructor、
`ApplicationContainer` 或窄範圍 FastAPI dependency override 注入 fake，不應
修改 process global。

詳細依賴及替換規則請見[架構指南](../docs/architecture.zh-Hant.md)。

## 可選 Redis 或 Valkey 快取

`CACHE_URL` 保持空白（預設值）時會注入 `NullCacheBackend`，不建立任何 cache
連線，所有讀取直接查詢 PostgreSQL。

若要使用內建 Valkey，請從 repository 根目錄執行：

```bash
CACHE_URL=redis://cache:6379/0 docker compose --profile cache up -d
```

PowerShell：

```powershell
$env:CACHE_URL = "redis://cache:6379/0"
docker compose --profile cache up -d
```

Cache service 只存在於內部網路，且因只保存可重建的衍生回應而停用持久化。
應用程式會：

- 快取公開 catalog 與 summary query；
- 將快取 JSON 重新驗證成 Pydantic DTO；
- mutation 成功 commit 後使 catalog/report namespace 失效；
- cache 讀、寫、失效或健康檢查失敗時，繼續由 PostgreSQL 提供資料；
- 在 `/v1/health` 回報 `disabled`、`ok` 或 `unavailable`。

相關設定：

| 變數 | 預設值 | 用途 |
| --- | --- | --- |
| `CACHE_URL` | 空白 | Redis-compatible URL；空白即停用 |
| `CACHE_KEY_PREFIX` | `setlist` | 各 deployment 的 key namespace |
| `CACHE_DEFAULT_TTL_SECONDS` | `60` | 公開回應 TTL |
| `CACHE_CONNECT_TIMEOUT_SECONDS` | `1` | 初次連線 timeout |
| `CACHE_SOCKET_TIMEOUT_SECONDS` | `1` | Cache operation timeout |

不得快取 authenticated response；這些回應必須維持 `Cache-Control: no-store`。

## 測試與檢查

Unit test 使用注入的 fake，不需要 Redis／Valkey：

```bash
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
```

當 `TEST_DATABASE_URL` 指向已 migrate 的測試資料庫時，才會執行 PostgreSQL
integration test。`services/yt_scraper/test.py` 是手動 live-network smoke
script，刻意不屬於 pytest。

Cache 測試使用 `MemoryCacheBackend` 及故障 fake，涵蓋 hit、正規化 key、
invalidation 與 fail-open。真實 Redis 或 Valkey adapter 實作相同的
`CacheBackend` port，因此不需修改 query service 即可替換。

## 目錄

```text
backend/
├── main.py                 # app factory 與 background-worker lifespan
├── container.py            # composition root 與 dependency wiring
├── config.py               # 經驗證的環境設定 snapshot
├── deps.py                 # FastAPI dependency provider
├── db/                     # engine/session factory 與 generated ORM
├── models/                 # Pydantic API/domain DTO
├── repositories/           # SQL 讀寫；不 commit
├── routers/v1/             # 薄 HTTP adapter
├── services/               # use case、policy、port 與 adapter
├── tests/                  # pytest unit 與 PostgreSQL integration test
├── run_updater_once.py     # one-shot updater entry point
└── reanalyze_stored_data.py
```

資料庫 schema 變更必須從 `../db/migrations/` 開始；generated `db/models.py`
不是 schema 的唯一真實來源。
