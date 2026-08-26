"""Reject regressions in privileged release and Dependabot workflow guards."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


def _read(name: str) -> str:
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def _require(text: str, snippet: str, source: str) -> None:
    if snippet not in text:
        raise AssertionError(f"{source} is missing required policy: {snippet}")


def _reject(text: str, snippet: str, source: str) -> None:
    if snippet in text:
        raise AssertionError(f"{source} contains forbidden policy: {snippet}")


def main() -> int:
    dependabot = _read("dependabot-auto-merge.yml")
    dependency_release = _read("dependency-release.yml")
    maintainer_release = _read("maintainer-release.yml")
    privileged = dependabot + dependency_release + maintainer_release

    for forbidden in (
        "/reviews?per_page=100",
        "reviewDecision",
        "gh pr review",
        "requires_external_approval",
        "independent approval",
    ):
        _reject(privileged, forbidden, "privileged release workflows")

    for required in (
        'head_repo" != "$REPOSITORY"',
        'head_sha" != "$TESTED_SHA"',
        '--match-head-commit "$TESTED_SHA"',
        'pr_state" != "OPEN"',
    ):
        _require(dependabot, required, "dependabot-auto-merge.yml")

    for required in (
        ".head.repo.full_name == $repository",
        '.user.login == "dependabot[bot]"',
        '.user.login == "github-actions[bot]"',
        'version_commit" != "$(git rev-parse HEAD)"',
        '--match-head-commit "$release_sha"',
        'remote_sha" != "$local_sha"',
        'release_merge_sha" != "$local_sha"',
        "docs: regenerate third-party notices",
        '.files[0].filename == "THIRD_PARTY_NOTICES.md"',
    ):
        _require(dependency_release, required, "dependency-release.yml")
    if dependency_release.count(".head.repo.full_name == $repository") < 3:
        raise AssertionError(
            "dependency-release.yml must constrain merged dependency, merged "
            "release, and open release PRs to this repository"
        )

    for required in (
        ".head.repo.full_name == $repository",
        '.user.login == "yutinglia"',
        'version_commit" != "$TESTED_SHA"',
        'remote_sha" != "$TESTED_SHA"',
        'release_merge_sha" != "$TESTED_SHA"',
    ):
        _require(maintainer_release, required, "maintainer-release.yml")
    _reject(maintainer_release, '.user.type == "User"', "maintainer-release.yml")

    expected_release_files = (
        '"VERSION"',
        '"frontend/package-lock.json"',
        '"frontend/package.json"',
    )
    for source, text in (
        ("dependency-release.yml", dependency_release),
        ("maintainer-release.yml", maintainer_release),
    ):
        for expected in expected_release_files:
            _require(text, expected, source)

    print("Release workflow safety policy check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
