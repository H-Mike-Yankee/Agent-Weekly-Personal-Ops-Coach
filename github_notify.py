"""Create a GitHub Issue (containing the report) via the GitHub REST API."""

import requests

GITHUB_API_BASE = "https://api.github.com"
REQUEST_TIMEOUT_SECONDS = 30


class GitHubNotifyError(RuntimeError):
    """Raised when the GitHub Issue cannot be created."""


def create_issue(report_text, today, github_token, github_repository):
    """POST the report as a new Issue on {owner}/{repo}.

    Returns the created Issue URL on success. Raises GitHubNotifyError on
    any failure (network error, HTTP error, invalid repository name).
    """
    if not github_token:
        raise GitHubNotifyError("GITHUB_TOKEN is missing or empty.")
    if not github_repository:
        raise GitHubNotifyError("GITHUB_REPOSITORY is missing or empty.")

    repo = github_repository.strip().strip("/")
    parts = repo.split("/")
    if len(parts) != 2 or not all(parts):
        raise GitHubNotifyError(
            f"GITHUB_REPOSITORY must be 'owner/repository', got: {github_repository!r}."
        )
    owner, name = parts

    url = f"{GITHUB_API_BASE}/repos/{owner}/{name}/issues"
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    }
    payload = {
        "title": f"Weekly Ops Report — {today.isoformat()}",
        "body": report_text,
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        raise GitHubNotifyError(
            f"Network error while contacting the GitHub API ({url}): {exc}"
        ) from exc

    if response.status_code not in (200, 201):
        raise GitHubNotifyError(
            f"GitHub API returned HTTP {response.status_code} for {url}. "
            f"Response: {response.text[:500]!r}"
        )

    data = response.json()
    html_url = data.get("html_url")
    if not html_url:
        raise GitHubNotifyError(
            "GitHub API responded without an html_url; cannot confirm the Issue."
        )
    return html_url