# 版本發布驗證

[English](RELEASE_VERIFICATION.md)

本檢查表記錄 Setlist 可公開、可重複執行的 release 規則，刻意不包含正式主機
細節、憑證、私有 repo 名稱或本機檔案路徑。

## Release 規則

- [`VERSION`](../VERSION)、`frontend/package.json` 與
  `frontend/package-lock.json` 必須包含相同的 `MAJOR.MINOR.PATCH`。
- Annotated `vMAJOR.MINOR.PATCH` tag 必須指向受保護 `main` 的目前 commit。
  Branch push 或 pull request 不能發布 image。
- [Release workflow](../.github/workflows/release.yml) 必須在 GitHub-hosted
  runner 執行，並以同一個不可變版本 tag 發布 frontend、backend、migrations
  與 PostgreSQL image。
- 每個 image 都包含 BuildKit provenance 與 SBOM。Source repo 公開時，
  workflow 還會建立並驗證 GitHub 簽章 artifact attestation，通過後才建立
  GitHub Release。
- 正式部署由獨立控制面取用已發布的 image。一般 source checkout 也能直接用
  Docker Compose 建置相同應用程式，不需要私有部署控制面。

即使 source repo 已公開，四個 GHCR package 仍可能是私有的。Pull 或自行驗證
前，請先登入 GHCR。

## Dependabot 自動 release 路徑

任何通過 review 並合併的 Dependabot pull request，都會由
[`Prepare dependency release`](../.github/workflows/dependency-release.yml)
workflow 等待受保護 `main` 的 CI 成功。它只接受同 repo、commit 經 GitHub
驗證且仍有有效核准的 Dependabot pull request，接著會：

1. 建立或 rebase 一個 Patch release pull request，且只包含 `VERSION`、
   `frontend/package.json` 與 `frontend/package-lock.json`；
2. 明確 dispatch 該 branch 的 CI，並啟用 squash auto-merge；
3. 等待 branch protection 與維護者獨立核准；
4. 再次驗證已合併的 release pull request，於通過測試的目前 `main` 建立
   annotated tag，並 dispatch 一般 release workflow。

這個特權 workflow 不會取用 pull-request artifact 或 cache。自動 pull request
與 workflow dispatch 只使用 repo 的 `GITHUB_TOKEN`，不會加入維護者 PAT。
任何身分、簽章、review、版本、變更檔案或目前 revision 檢查失敗時，都會停止且
不發布。

## 建立 tag 前

以下步驟適用於手動 release。Dependabot 自動路徑會執行等效的版本同步、核准、
tag 與 dispatch 檢查。

1. 確認 release pull request 已通過審核、合併，且所有檢查皆為綠燈。
2. 更新本機 `main`，不要改寫歷史：

   ```bash
   git switch main
   git pull --ff-only
   git status --short
   ```

3. 確認版本檔一致，且預定 tag 尚不存在：

   ```bash
   version="$(tr -d '\r\n' < VERSION)"
   test "$version" = "$(node -p "require('./frontend/package.json').version")"
   test "$version" = "$(node -p "require('./frontend/package-lock.json').version")"
   git rev-parse --verify --quiet "refs/tags/v${version}" && exit 1 || true
   ```

4. 執行[貢獻指南](../CONTRIBUTING.md)記載的 repo 檢查，包括憑證掃描、
   backend 測試、frontend lint／build 及 production container build。
5. 使用 repo helper 建立 annotated tag，檢查後只 push 該精確 tag：

   ```bash
   node scripts/bump-version.mjs tag
   git show --no-patch "v${version}"
   git push origin "v${version}"
   ```

Workflow 仍會獨立拒絕不符合 `VERSION`，或未指向目前 `main` commit 的 tag。

## Attestation 驗證

Release job 會以 digest 驗證每個新發布 image，並要求：

- attestation 指向本 source repo；
- source ref 是該 release tag；
- attestation 由 GitHub-hosted runner 產生；以及
- 簽章與可信身分通過密碼學驗證。

Workflow 會在建立 GitHub Release 前自動執行。若要在已驗證身分的工作站重做
檢查，應盡量使用不可變的 image digest：

```bash
docker login ghcr.io
gh attestation verify \
  "oci://ghcr.io/yutinglia/setlist-frontend@sha256:DIGEST" \
  --repo yutinglia/setlist \
  --source-ref "refs/tags/vX.Y.Z" \
  --deny-self-hosted-runners
```

請對 `setlist-backend`、`setlist-migrations` 與 `setlist-postgres` 重複執行。
Workflow step 顯示成功本身不能取代密碼學驗證；實際驗證由
`gh attestation verify` 完成。

## Release 後

1. 確認精確 tag 的 `Build release images` run 成功。
2. 確認 GitHub Release 已建立，且指向該 `main` commit。
3. 確認四個版本化 image tag 都存在，並具有預期的 OCI version label、SBOM、
   provenance 與 attestation。
4. 確認部署選用一組完整且版本相符的 release，再檢查公開 health endpoint 與
  網站 footer 顯示的版本。
5. 詳細正式環境檢查只留在私有部署控制面；本 repo 僅記錄可重用且不敏感的
   發現。

## Build context 注意事項

`frontend/Dockerfile` 以 repo root 為 build context，但只複製特定 root metadata
與 `frontend/` 目錄。因此，`frontend/package.json` 呼叫的 script 必須位於
`frontend/` 內，否則就要由 Dockerfile 明確複製。變更 frontend build script
後，務必同時驗證 `npm run build` 與 production frontend image build。

歷史說明：`v0.2.0` 在 source repo 公開前發布，因此有 BuildKit SBOM 與
provenance，但略過只適用於 public repo 的 GitHub attestation 步驟。
`v0.2.1` 是第一個預定完整執行 attestation 建立與驗證流程的 release。
