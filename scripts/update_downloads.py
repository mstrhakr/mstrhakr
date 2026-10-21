import json
import os
from pathlib import Path
from urllib.request import Request, urlopen


OWNERS = ("mstrhakr", "Printmaster-Org", "Szittai-Cloud")
OUTPUT = Path(__file__).resolve().parents[1] / "badges" / "release-downloads.json"
STARS_OUTPUT = OUTPUT.with_name("project-stars.json")


def request_json(path):
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "mstrhakr-profile-downloads",
    }
    token = os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(f"https://api.github.com{path}", headers=headers)
    with urlopen(request, timeout=60) as response:
        return json.load(response)


def paginate(path):
    page = 1
    while True:
        items = request_json(f"{path}?per_page=100&page={page}")
        if not isinstance(items, list):
            raise ValueError(f"Expected a list from {path}")
        yield from items
        if len(items) < 100:
            return
        page += 1


def count_totals():
    repositories = {}
    for owner in OWNERS:
        for repository in paginate(f"/users/{owner}/repos"):
            if not repository["private"]:
                repositories[repository["full_name"]] = repository

    stars = 0
    for repository in repositories.values():
        count = repository["stargazers_count"]
        if type(count) is not int or count < 0:
            raise ValueError(f"Invalid star count in {repository['full_name']}: {count!r}")
        stars += count

    total = 0
    for repository in sorted(repositories):
        for release in paginate(f"/repos/{repository}/releases"):
            if release["draft"]:
                continue
            for asset in release["assets"]:
                count = asset["download_count"]
                if type(count) is not int or count < 0:
                    raise ValueError(f"Invalid download count in {repository}: {count!r}")
                total += count
    return total, stars


def update_badge(output=OUTPUT, stars_output=STARS_OUTPUT):
    total, stars = count_totals()
    for path, label, count in (
        (output, "Release downloads", total),
        (stars_output, "Project stars", stars),
    ):
        badge = {
            "schemaVersion": 1,
            "label": label,
            "message": f"{count:,}",
            "color": "58a6ff",
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(badge, indent=2) + "\n", encoding="utf-8")
        print(f"{label} across {', '.join(OWNERS)}: {count:,}")


if __name__ == "__main__":
    update_badge()
