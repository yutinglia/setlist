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
        "--admin",
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
        "workflow_dispatch:",
        "ci_run_id:",
        "expected_sha:",
        "queue: max",
        "github.actor == 'github-actions[bot]'",
        "github.triggering_actor == 'github-actions[bot]'",
        "github.run_attempt == '1'",
        '(.path | split("@")[0]) == ".github/workflows/ci.yml"',
        '.event == "workflow_dispatch"',
        '.actor.login == "github-actions[bot]"',
        '.triggering_actor.login == "github-actions[bot]"',
        ".run_attempt == 1",
        'gh run watch "$CI_RUN_ID"',
        'gh run watch "$release_ci_run_id"',
        'gh pr merge "$pr_number"',
        'validate_ci_identity "$main_ci_run_id" main "$merge_sha"',
        'release_parent_sha" != "$current_main_sha"',
        'release_commit_count" != "1"',
        'release_subject" != "chore(release): $release_tag"',
        "all(.[][];",
        '.status == "modified" and',
        "(.previous_filename // null) == null",
        'remote_main_sha" != "$merge_sha"',
        "gh workflow run dependency-release.yml",
        '-f "ci_run_id=$main_ci_run_id"',
        '-f "expected_sha=$merge_sha"',
        "docs: regenerate third-party notices",
        '.files[0].filename == "THIRD_PARTY_NOTICES.md"',
    ):
        _require(dependency_release, required, "dependency-release.yml")
    if dependency_release.count(".head.repo.full_name == $repository") < 4:
        raise AssertionError(
            "dependency-release.yml must constrain merged dependency, merged "
            "release, open release, and pre-merge release PRs to this repository"
        )
    if dependency_release.count('.triggering_actor.login == "github-actions[bot]"') < 3:
        raise AssertionError(
            "dependency-release.yml must authenticate release CI, main CI, "
            "and the queued continuation"
        )
    if (
        dependency_release.count('.status == "completed" and .conclusion == "success"')
        < 2
    ):
        raise AssertionError(
            "dependency-release.yml must require completed successful release "
            "and main CI runs"
        )
    _reject(dependency_release, "gh pr merge --auto", "dependency-release.yml")
    _reject(dependency_release, "--auto --squash", "dependency-release.yml")
    _reject(dependency_release, "${{ secrets.", "dependency-release.yml")

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
