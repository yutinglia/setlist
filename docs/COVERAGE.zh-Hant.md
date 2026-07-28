# 測試覆蓋率政策

前後端都必須通過覆蓋率品質閘門。任一 stack 低於門檻時，pull request 或
`main` push 的 CI 都不會通過；release 也只能發佈已有成功 coverage-gated CI
的同一個 tagged commit。

## 門檻

| Stack | 計算指標 | 最低要求 |
| --- | --- | --- |
| 後端 | Coverage.py 合併 statements 與 branches | 80% |
| 前端 | Statements、branches、functions、lines | 每項 80% |

門檻會分別檢查兩個 stack，因此後端的高覆蓋率不能掩蓋未測試的前端，反之
亦然。

## 計算範圍

後端從 `backend/` 下所有 Python 原始碼開始計算，包括 API、application
services、repositories、scraper adapters、設定及維護入口程式。以下項目不
納入：

- `backend/tests/`，因為測試程式本身不屬於產品覆蓋率；
- `backend/db/models.py`，因為 Flyway 才是 schema 唯一依據，這個 ORM 檔由
  `sqlacodegen` 產生；
- `backend/services/yt_scraper/test.py`，因為它是操作人員手動執行的 YouTube
  live smoke script，不是自動測試目標；
- `if __name__ == "__main__"` 啟動 guard、只供型別檢查的區塊，以及刻意保留
  的抽象 `NotImplementedError`。

前端從 `frontend/src/` 下所有 TypeScript 與 TSX 檔案開始計算，包括 routes、
components、hooks、stores 及瀏覽器入口。只排除測試／測試 helper、ambient
declarations，以及產生的 Paraglide 與 TanStack Router 程式碼。

## 本機分析

完整後端測試前，先啟動 PostgreSQL 並套用 migration：

```bash
docker compose -f docker-compose.dev.yml up -d db
docker compose -f docker-compose.dev.yml run --rm flyway

cd backend
python -m pip install -r requirements-dev.txt
python -m pytest \
  --cov \
  --cov-report=term-missing:skip-covered \
  --cov-report=xml:coverage.xml \
  --cov-report=html:htmlcov
```

以瀏覽器開啟 `backend/htmlcov/index.html` 可查看各檔案與 branch 細節；XML
報告可供編輯器及 CI 工具使用。若只想快速執行特定測試，仍可用
`python -m pytest path/to/test.py`，不會被迫執行全專案 coverage gate。

前端覆蓋率請分開執行：

```bash
cd frontend
npm ci
npm run test:coverage
```

以瀏覽器開啟 `frontend/coverage/index.html` 可查看 line 與 branch 細節；同一
目錄也包含供自動化使用的 `coverage-summary.json` 與 LCOV 輸出。單純執行
測試時仍可使用較快的 `npm test`。

關鍵瀏覽器流程使用 Playwright 與固定的 API stub，因此能在 Chromium 中操作
完整應用程式，又不依賴 PostgreSQL 或即時 YouTube 存取：

```bash
cd frontend
npx playwright install chromium
npm run test:e2e
```

E2E 刻意只涵蓋高價值 journey：公開歌曲搜尋與詳情導覽、影片時間戳歌單，以及
管理員驗證邊界。元件變化與各種 edge case 留在速度更快、較容易診斷的 Vitest。

## CI 與 release 行為

前後端 CI job 都會輸出可閱讀的終端摘要，並把完整報告分別以
`backend-coverage` 與 `frontend-coverage` artifact 保留 14 天。覆蓋率失敗會
在正式環境 image 建置前中止該 job；兩個 job 也會把總計寫入 GitHub Actions
run summary，reviewer 不需下載 artifact 就能看到 gate 結果。前端 job 也會
安裝 Chromium、執行 Playwright，並把失敗畫面、影片、trace 與 HTML 報告保留
成 artifact。Release workflow 也會先向 GitHub Actions 查詢同一 tagged
commit 是否已有成功 CI，通過後才建置或發佈 image。

覆蓋率是 guardrail，不能取代有意義的 assertion。新增測試應驗證可觀察行為、
錯誤與邊界條件，避免只靠 import 或 mock 執行來墊高百分比。
