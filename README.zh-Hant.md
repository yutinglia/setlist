# Setlist — VTuber 歌回搜尋

[English](README.md) · [繁體中文](README.zh-Hant.md)

![Setlist 社群預覽圖](frontend/public/og.png)

Setlist 是可自行託管的 VTuber 歌回曲目搜尋索引。它會發現公開的 YouTube
封存影片、尋找附有時間戳的歌單留言、抽取歌曲名稱，並建立可直接跳到原始影片
對應時間點的搜尋連結。

本專案仍在快速開發中，並以小型公開 homelab 部署為設計目標。訪客可以搜尋及
瀏覽；單一管理員登入後，則可管理頻道、重新整理中繼資料、重新載入指定影片的
歌單，以及查看即時更新器狀態。

> 自動產生的中繼資料可能不完整或有誤。Setlist 是獨立索引，不託管影音內容，
> 且與 YouTube、Google、任何 VTuber 經紀公司、頻道或表演者均無隸屬、背書
> 或贊助關係。

## 功能特色

- 快速、可分頁的歌曲搜尋，支援頻道、內容類型與日期篩選
- 可直接跳到歌曲時間戳的 YouTube 深層連結
- 頻道、影片、歌曲詳情與資料庫摘要瀏覽
- 英文與繁體中文介面
- 優先採用置頂／上傳者留言，並支援多種時間戳格式
- 可持續復原的全頻道回填，以及保守的日常資料發現
- Tier B YouTube 節流：工作量上限、隨機延遲、重試限制、封鎖偵測與持久化冷卻
- 可選用 OpenAI 相容 API，在正規表示式抽取後進一步清理歌單
- 使用簽章 HttpOnly 工作階段與 CSRF 防護的單一管理員驗證
- 依 IP 限制訪客 API 流量，並對登入採用更嚴格的限制
- 公開的關於、服務條款、隱私權與著作權／移除請求頁面
- React 前端、FastAPI、PostgreSQL 與 Flyway 的正式環境容器

## 權限模型

| 功能 | 訪客 | 管理員 |
|------|:----:|:------:|
| 搜尋與瀏覽公開索引 | 可以 | 可以 |
| 查看摘要報告 | 可以 | 可以 |
| 輪詢即時更新器狀態 | 不可以 | 可以 |
| 新增頻道或重新整理頻道中繼資料 | 不可以 | 可以 |
| 重新載入影片歌單 | 不可以 | 可以 |

所有權限都由 API 強制執行；隱藏前端按鈕不會被當成安全邊界。

## 使用 Dev Container 快速開始

這是 Windows、macOS 與 Linux 上最簡單的開發方式。

1. 複製此倉庫，並使用 VS Code 或 Cursor 開啟。
2. 執行 **Dev Containers: Reopen in Container**。
3. 等待 PostgreSQL、Flyway、Python 相依套件與 `npm ci` 完成。
4. 開啟 <http://localhost:5173>。

API 與 UI 會自動以熱重載模式啟動。開發環境預設不啟用背景爬取，因此僅開啟
倉庫不會立刻呼叫 YouTube。

| 網址 | 用途 |
|------|------|
| <http://localhost:5173> | 搜尋介面 |
| <http://localhost:5173/admin/login> | 管理員登入 |
| <http://localhost:5173/status> | 僅限管理員的更新器狀態 |
| <http://localhost:8000/v1/health> | API 與資料庫健康狀態 |
| <http://localhost:8000/docs> | `APP_ENV=dev` 時的 OpenAPI 文件 |

容器內的日誌位於：

```text
/tmp/vtuber-karaoke-search-dev/backend.log
/tmp/vtuber-karaoke-search-dev/frontend.log
```

資料庫存取、管理員設定與生命週期細節請參考
[.devcontainer/README.md](.devcontainer/README.md)。

## 公開 homelab 部署

### 需求

- Docker Engine 與 Compose v2
- 公開網域名稱
- Caddy、Traefik 或 nginx 等 HTTPS 反向代理
- 足夠存放 PostgreSQL 資料的空間

正式環境只會將前端代理繫結至
`${FRONTEND_BIND_ADDRESS:-127.0.0.1}:${FRONTEND_PORT:-8080}`。TLS reverse
proxy 位於同一主機時請保留 loopback 預設值；若 proxy 位於另一台主機，請把
`FRONTEND_BIND_ADDRESS` 設為此伺服器的 private LAN address，並以 firewall
限制只有 proxy 能存取該 port。FastAPI 與 PostgreSQL 仍會留在 Compose
私有網路內。

### 1. 建立本機正式環境設定

```bash
cp .env.production.example .env
```

PowerShell：

```powershell
Copy-Item .env.production.example .env
```

將 `PUBLIC_SITE_URL` 設為最終的 HTTPS 來源網址，並填妥 `.env` 中所有必要的
空白值。

### 2. 產生管理員密碼雜湊

安裝執行期相依套件，再使用互動式工具：

```bash
cd backend
python -m pip install -r requirements.txt
python generate_admin_password_hash.py
cd ..
```

因為 Argon2 雜湊包含 `$`，請使用**單引號**把輸出存入 `.env`：

```dotenv
ADMIN_PASSWORD_HASH='$argon2id$...'
```

應用程式不會儲存明文密碼。

### 3. 產生獨立的工作階段簽章密鑰

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

將結果填入 `SESSION_SECRET`。請勿重複使用管理員密碼或資料庫密碼。

### 4. 啟動服務

```bash
docker compose up --build -d
docker compose ps
```

對外開放前，先驗證本機代理：

```bash
curl http://127.0.0.1:8080/v1/health
```

將 HTTPS 反向代理指向
`http://${FRONTEND_BIND_ADDRESS:-127.0.0.1}:${FRONTEND_PORT:-8080}`，並維持
`AUTH_COOKIE_SECURE=true`。內建前端會提供 SPA、套用瀏覽器安全標頭，並把
`/v1` 代理至 FastAPI。

若缺少 `PUBLIC_SITE_URL`、`DB_PASSWORD`、`ADMIN_PASSWORD_HASH` 或
`SESSION_SECRET`，Compose 會拒絕啟動。

### 自動化 homelab 部署

此公開 repo 不包含正式主機路徑、密鑰或 self-hosted 部署 job。
`v0.1.0` 這類語意版本 tag 只會在 GitHub-hosted runner 上執行
[`Build release images`](.github/workflows/release.yml) workflow。流程會先確認
tag 與 [`VERSION`](VERSION) 相符，且指向受保護 `main` 的目前 commit，再把
frontend、backend、Flyway 與 PostgreSQL 的版本化 image 發佈至 GHCR、附上
SBOM／provenance 資料，最後才建立 GitHub Release。BuildKit SBOM 與 provenance
一律和 image 一同存放於 GHCR；source repo 公開後，也會同步建立 GitHub 的簽章
attestation。

正式部署刻意由另一個私有 repo 控制。其 self-hosted runner 只會取用已發佈的
release image，不會 checkout 或執行此公開 repo 的 pull-request 程式碼。
Fork 使用者不需要私有控制面，也能使用上方的本機 Compose 說明或自選部署系統。

Production Compose 也有明確的資源上限：nginx 為 128 MiB／0.25 CPU、
API 與 scraper 為 768 MiB／1 CPU、PostgreSQL 為 512 MiB／0.75 CPU，
一次性 Flyway migration 則為 256 MiB／0.5 CPU。只有在觀察正式機一段
時間的持續用量後，才建議調整這些值。

### 版本與 release

網站 footer 顯示的版本會依以下順序解析：

1. 部署或建置時傳入的覆寫值；
2. checkout commit 上完全相符的 `v*` Git tag；
3. repo 內受版本控制的 [`VERSION`](VERSION) 檔；
4. 已同步的前端 package 版本。

最後一個 fallback 可確保 GitHub source archive 或一般
`docker compose up --build -d` 即使沒有 Git metadata 與 CI，仍會顯示目前
版本。

請從乾淨且已更新的 `main` branch 準備 release pull request：

```bash
git switch main
git pull --ff-only
node scripts/bump-version.mjs patch
# 依 script 顯示的指令推送 release/v0.0.1 並建立 pull request。
```

參數可以是 `major`、`minor`、`patch`，或更高的明確
`MAJOR.MINOR.PATCH`。Script 會同步 `VERSION`、前端 package metadata 與
lockfile，再於 `release/vX.Y.Z` branch 建立 release commit，但不會自行
push。

受保護的 pull request 通過審核並合併後，再替目前 `main` commit 建立 tag：

```bash
git switch main
git pull --ff-only
node scripts/bump-version.mjs tag
# 檢查 annotated tag，再使用 script 顯示的實際 tag：
git push origin v0.0.1
```

一般 source build 會顯示 repo 內的版本；若有 Git metadata，還會加上短 commit
SHA。Release image 則顯示乾淨的語意版本。Branch push 與 pull request 只會執行
CI，不能發佈 release 或部署正式環境。

### 部署安全檢查表

- 將 `.env` 排除於 Git，並限制可讀取它的人員。
- 只公開 TLS 反向代理；不要發布 PostgreSQL 或 FastAPI 連接埠。
- 使用獨立的隨機資料庫密碼，以及至少 32 位元組的工作階段密鑰。
- 只允許 `TRUSTED_PROXY_CIDRS` 中的確切網路提供 `X-Forwarded-For`。
- UI 與 API 應盡量使用同一來源；若必須分開，只在 `CORS_ORIGINS` 列出 UI
  的確切來源。
- 在主機或資料庫維護前備份 `vks-pgdata` volume。
- 定期檢查日誌與相依套件更新。

訪客限流資料儲存在記憶體中，並以單一 API 程序為單位。預設部署只使用一個
API worker；若要擴充成多副本，請先在外部閘道加入共享限流。

更多安全與非公開通報方式請參考 [SECURITY.md](SECURITY.md)。

## 不使用 Dev Container 的本機開發

啟動 PostgreSQL 並套用所有 Flyway migration：

```bash
docker compose -f docker-compose.dev.yml up -d db flyway
```

請從後端要求的工作目錄啟動 API：

```bash
cd backend
python -m pip install -r requirements-dev.txt
APP_ENV=dev BACKGROUND_UPDATER_ENABLED=false \
  uvicorn main:app --host 0.0.0.0 --port 8000
```

PowerShell：

```powershell
Set-Location backend
python -m pip install -r requirements-dev.txt
$env:APP_ENV = "dev"
$env:BACKGROUND_UPDATER_ENABLED = "false"
uvicorn main:app --host 0.0.0.0 --port 8000
```

在另一個終端機中執行：

```bash
cd frontend
npm ci
npm run dev
```

Vite 會將 `/v1` 代理至 `http://127.0.0.1:8000`。前端專用指令請參考
[frontend/README.md](frontend/README.md)。

## 在開發環境設定管理員

即使 `APP_ENV=dev`，管理功能仍會受到保護。若要測試：

1. 使用 `backend/generate_admin_password_hash.py` 產生 Argon2id 雜湊。
2. 在已被忽略的根目錄 `.env` 設定 `ADMIN_USERNAME`、
   `ADMIN_PASSWORD_HASH`，以及至少 32 位元組的 `SESSION_SECRET`。
3. 只有在本機 HTTP 開發期間才可使用 `AUTH_COOKIE_SECURE=false`。
4. 重新啟動或重建開發環境。

若未提供這些設定，訪客搜尋與瀏覽仍可使用，但管理員登入會以安全方式失敗。

## 加入種子頻道並執行一次更新

開發資料庫啟動後：

```bash
docker compose -f docker-compose.dev.yml exec -T db \
  psql -U vks_db_user -d vks_db < db/devscript/seed_channels.sql
```

若要執行一次和背景服務相同、且有工作量上限的更新流程，而不常駐排程器：

```bash
cd backend
python run_updater_once.py
```

只有在確定要進行爬取時才啟用長時間背景服務：

```dotenv
BACKGROUND_UPDATER_ENABLED=true
```

## API 概覽

列表端點接受 `limit`（1–100，預設 20）與 `offset`
（0–1,000,000，預設 0）。

### 公開訪客端點

| 方法 | 路徑 | 用途 |
|------|------|------|
| `GET` | `/v1/health` | API 與資料庫健康狀態 |
| `GET` | `/v1/songs/search?q=` | 搜尋歌曲，可選用頻道／類型／日期篩選 |
| `GET` | `/v1/songs/{id}` | 歌曲詳情與帶時間戳的 YouTube 連結 |
| `GET` | `/v1/channels` | 已追蹤頻道 |
| `GET` | `/v1/channels/{id}/videos` | 指定頻道的影片 |
| `GET` | `/v1/videos/{id}` | 影片中繼資料 |
| `GET` | `/v1/videos/{id}/songs` | 從指定影片抽取的歌曲 |
| `GET` | `/v1/report/summary` | 資料庫與資料流程的彙總計數 |
| `GET` | `/v1/auth/session` | 目前的訪客／管理員工作階段狀態 |
| `POST` | `/v1/auth/login` | 受限流保護的管理員登入 |

範例：

```bash
curl 'http://localhost:8000/v1/songs/search?q=Stellar&type=karaoke'
```

搜尋結果會包含類似
`https://www.youtube.com/watch?v=...&t=300s` 的 `video_url`。

### 僅限管理員的端點

| 方法 | 路徑 | 用途 |
|------|------|------|
| `POST` | `/v1/auth/logout` | 結束目前的管理員工作階段 |
| `GET` | `/v1/updater/status` | 程序內更新器與冷卻狀態 |
| `POST` | `/v1/channels` | 驗證並新增 YouTube 頻道 |
| `POST` | `/v1/channels/{id}/videos/refresh` | 重新整理中繼資料而不刪除既有歌單 |
| `POST` | `/v1/videos/{id}/songs/reload` | 重新抓取留言並執行歌單抽取 |

瀏覽器中的異動請求同時需要已簽章的管理員 Cookie 與工作階段的
`X-CSRF-Token`。

## 設定

開發環境請複製 [`.env.example`](.env.example)，Compose 正式環境則複製
[`.env.production.example`](.env.production.example)。範例檔只含空值或
佔位內容。

重要設定：

| 設定 | 預設值 | 意義 |
|------|--------|------|
| `APP_ENV` | `prod` | `dev` 會啟用 API 文件與本機開發來源 |
| `BACKGROUND_UPDATER_ENABLED` | `false` | 明確啟用週期性爬取 |
| `MANAGEMENT_API_ENABLED` | `true` | 緊急停用開關；絕不略過驗證 |
| `ADMIN_USERNAME` | `admin` | 唯一的管理員名稱 |
| `ADMIN_PASSWORD_HASH` | 空白 | Argon2id 雜湊，絕不可填明文 |
| `SESSION_SECRET` | 空白 | 工作階段簽章密鑰，至少 32 位元組 |
| `AUTH_SESSION_TTL_SECONDS` | `43200` | 管理員工作階段期限 |
| `AUTH_COOKIE_SECURE` | 正式環境為 true | 公開 HTTPS 必須維持 true |
| `GUEST_RATE_LIMIT_REQUESTS/WINDOW_SECONDS` | `60/60` | 每個來源 IP／時間窗的訪客請求數 |
| `LOGIN_RATE_LIMIT_REQUESTS/WINDOW_SECONDS` | `5/300` | 每個來源 IP／時間窗的登入次數 |
| `TRUSTED_PROXY_CIDRS` | 空白 | 可提供用戶端 IP 的代理網路 |
| `CORS_ORIGINS` | 空白 | 可進行帶憑證跨來源存取的確切 UI 來源 |
| `DATA_UPDATE_INTERVAL` | `300` | Worker 心跳；只有到期工作才會呼叫 YouTube |
| `UPDATE_STEADY_SCAN_INTERVAL` | `21600` | 一般頻道發現間隔 |
| `UPDATE_MAX_COMMENT_SCRAPES` | `3` | 每個更新週期的留言爬取上限 |
| `UPDATE_YOUTUBE_COOLDOWN_SECONDS` | `21600` | 疑似遭封鎖後的持久化冷卻時間 |
| `LLM_CLEANING_ENABLED` | `false` | 可選用的正規表示式後處理 |

完整設定與說明請見 [`.env.example`](.env.example)。

## 資料流程如何運作

1. 透過有工作量上限的 Streams 與 Videos 播放清單頁面發現追蹤頻道內容。
2. 清單快照會保留穩定中繼資料與約略日期，不會對每支影片額外發出請求。
3. 可能是歌回的影片會進入獨立且受節流控制的留言分析佇列。
4. 分析器優先採用置頂與上傳者留言、抽取時間戳／標題配對，且只在成功分析後
   取代影片歌單。
5. 精確中繼資料可以升級約略值；之後的稀疏觀察不會抹除較完整的快照或先前
   成功的歌單。
6. 若疑似受到 YouTube 封鎖，系統會中止剩餘呼叫並保存冷卻時間，避免重啟
   繞過限制。

詳細設計決策記錄於 [PLAN.md](PLAN.md)，爬蟲資料形狀則記錄於
[backend/NOTE.md](backend/NOTE.md)。

## 測試與 CI

後端：

```bash
cd backend
python -m pip install -r requirements-dev.txt
python -m ruff check .
python -m ruff format --check .
python -m pytest
```

前端：

```bash
cd frontend
npm ci
npm run lint
npm run build
```

倉庫憑證掃描：

```bash
python scripts/check_secrets.py
```

GitHub Actions CI 會執行憑證掃描、Ruff、在 PostgreSQL 18 與完整 Flyway
migration 後的後端測試、正式環境映像建置、第三方授權清單驗證、前端 lint，
以及正式前端建置。Release workflow 只接受與目前受保護 `main` commit 相符的
語意版本 tag；正式部署則隔離在私有 repo。

## 專案結構

```text
setlist/
├── .devcontainer/          # Python 3.14 + Node 26 編輯器環境
├── .github/workflows/      # CI 與 release image 發佈
├── backend/                # FastAPI API、驗證、更新器、爬蟲與測試
├── db/migrations/          # Flyway V1–V9 schema 歷史（唯一依據）
├── frontend/               # React UI 與正式環境 nginx 代理
├── scripts/                # 倉庫安全檢查
├── CONTRIBUTING.md         # 貢獻流程
├── SECURITY.md             # 非公開漏洞通報方式
├── LICENSE                 # 專案原創程式碼的 MIT 授權
├── THIRD_PARTY_NOTICES.md  # 自動產生的前端相依套件授權聲明
├── docker-compose.dev.yml  # 開發資料庫與 Dev Container
└── docker-compose.yml      # 正式 homelab 服務
```

## 貢獻與專案狀態

Phase 0–8 已完成：資料流程、抽取、搜尋 API/UI、排程器強化、驗證、訪客限流、
公開服務頁面、部署強化與公開文件。專案仍在快速開發，現階段不保證資料庫與 API
向後相容。

提交 pull request 前，請先閱讀 [CONTRIBUTING.md](CONTRIBUTING.md)、
[AGENTS.md](AGENTS.md) 與 [PLAN.md](PLAN.md)。

## 法律聲明與移除請求

Setlist 儲存事實性中繼資料並連結至公開 YouTube 頁面，不託管所連結的演出。
影片、音訊、縮圖、名稱與其他創作素材的權利仍屬各自權利人。

權利人與頻道營運者可透過
[GitHub Issues](https://github.com/yutinglia/setlist/issues)
要求更正、排除頻道或移除資料。請勿在公開 Issue 中張貼私人身分文件。

## 授權

Setlist 採用 [MIT License](LICENSE)。只要保留著作權與授權聲明，即可使用、
修改、再散布、再授權或銷售本專案的副本。

第三方套件、字型、服務 API、連結媒體與抽取的中繼資料仍受各自的授權及條款
規範。編譯網站所重新散布的 production frontend 套件聲明收錄於
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
