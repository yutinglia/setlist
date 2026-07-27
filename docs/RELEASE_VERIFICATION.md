# Release verification

[繁體中文版](RELEASE_VERIFICATION.zh-Hant.md)

This checklist records the public, repeatable release contract for Setlist. It
intentionally excludes production host details, credentials, private repository
names, and local filesystem paths.

## Release contract

- [`VERSION`](../VERSION), `frontend/package.json`, and
  `frontend/package-lock.json` contain the same `MAJOR.MINOR.PATCH` value.
- An annotated `vMAJOR.MINOR.PATCH` tag points to the current protected `main`
  commit. A branch push or pull request cannot publish images.
- [The release workflow](../.github/workflows/release.yml) runs on a
  GitHub-hosted runner and publishes frontend, backend, migrations, and
  PostgreSQL images with the same immutable version tag.
- Each image contains BuildKit provenance and an SBOM. When the source
  repository is public, the workflow also creates and verifies a signed GitHub
  artifact attestation before it creates the GitHub Release.
- Production deployment is controlled separately and consumes published
  images. After publishing the GitHub Release, the source workflow sends the
  exact tag through a short-lived GitHub App token that is limited to the
  deployment control plane. A source checkout can instead build the same
  application locally with Docker Compose and does not require that private
  control plane.

The four GHCR packages may be private even though the source repository is
public. Authenticate to GHCR before pulling or independently verifying them.

## Automated Dependabot release path

After any reviewed and merged Dependabot pull request, the
[`Prepare dependency release`](../.github/workflows/dependency-release.yml)
workflow waits for the protected `main` CI run to succeed. It accepts only
same-repository Dependabot pull requests whose commits are GitHub-verified and
have a surviving approval. It then:

1. creates or rebases a Patch release pull request containing only `VERSION`,
   `frontend/package.json`, and `frontend/package-lock.json`;
2. explicitly dispatches CI for that branch and enables squash auto-merge;
3. waits for the branch protection rule and an independent maintainer approval;
4. verifies the merged release pull request, creates its annotated tag on the
   tested current `main`, and dispatches the normal release workflow.

The privileged workflow never consumes pull-request artifacts or caches.
Automatic pull requests and workflow dispatches use only the repository
`GITHUB_TOKEN`, so this path does not introduce a maintainer PAT. If any
identity, signature, review, version, changed-file, or current-revision check
fails, it stops without publishing.

After a release is published, its cross-repository deployment notification uses
a separate GitHub App credential stored in the release environment. The App is
installed only on the deployment control plane with the API-required
`Contents: write` permission, and each workflow token is further restricted to
that single repository and permission.

## Before tagging

Use these steps for a manual release. The automated Dependabot path performs the
equivalent version synchronization, approval, tag, and dispatch checks.

1. Confirm the release pull request is approved, merged, and green.
2. Update local `main` without rewriting history:

   ```bash
   git switch main
   git pull --ff-only
   git status --short
   ```

3. Confirm the version files agree and the intended tag does not already exist:

   ```bash
   version="$(tr -d '\r\n' < VERSION)"
   test "$version" = "$(node -p "require('./frontend/package.json').version")"
   test "$version" = "$(node -p "require('./frontend/package-lock.json').version")"
   git rev-parse --verify --quiet "refs/tags/v${version}" && exit 1 || true
   ```

4. Run the repository checks documented in
   [Contributing](../CONTRIBUTING.md), including the credential scan, backend
   tests, frontend lint/build, and production container builds.
5. Create the annotated tag with the repository helper, inspect it, then push
   only that exact tag:

   ```bash
   node scripts/bump-version.mjs tag
   git show --no-patch "v${version}"
   git push origin "v${version}"
   ```

The workflow independently rejects a tag that does not match `VERSION` or does
not point to the current `main` commit.

## Attestation verification

The release job verifies each newly published image by digest. Verification
requires all of the following:

- the attestation identifies this source repository;
- its source ref is the release tag;
- the attestation was produced on a GitHub-hosted runner; and
- the signature and trusted identity are cryptographically valid.

The workflow performs this check automatically before creating the GitHub
Release. To repeat it from an authenticated workstation, use an immutable image
digest when available:

```bash
docker login ghcr.io
gh attestation verify \
  "oci://ghcr.io/yutinglia/setlist-frontend@sha256:DIGEST" \
  --repo yutinglia/setlist \
  --source-ref "refs/tags/vX.Y.Z" \
  --deny-self-hosted-runners
```

Repeat the command for `setlist-backend`, `setlist-migrations`, and
`setlist-postgres`. A successful workflow step by itself is not a substitute
for cryptographic verification; `gh attestation verify` performs that
verification.

## After release

1. Confirm the `Build release images` run succeeded for the exact tag.
2. Confirm the GitHub Release exists and targets the tagged `main` commit.
3. Confirm the exact-tag deployment notification was accepted.
4. Confirm all four versioned image tags exist and have the expected OCI version
   label, SBOM, provenance, and attestation.
5. Confirm the deployment selected one complete matching release, then verify
   the public health endpoint and the version displayed in the site footer.
6. Keep detailed production checks in the private deployment control plane;
   record only reusable, non-sensitive findings in this repository.

## Build-context note

`frontend/Dockerfile` uses the repository root as its build context, but copies
only selected root metadata and the `frontend/` tree. A script called by
`frontend/package.json` must therefore live under `frontend/` or be explicitly
copied by the Dockerfile. Always validate both `npm run build` and the production
frontend image build after changing frontend build scripts.

Historical note: `v0.2.0` was published before the source repository became
public. Its BuildKit SBOM and provenance exist, but the public-repository-only
GitHub attestation steps were skipped. `v0.2.1` is the first release intended to
exercise the full create-and-verify attestation path.
