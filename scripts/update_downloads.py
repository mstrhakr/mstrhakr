import json
import os
from pathlib import Path
from urllib.request import Request, urlopen


OWNERS = ("mstrhakr", "Printmaster-Org", "Szittai-Cloud")
OUTPUT = Path(__file__).resolve().parents[1] / "badges" / "release-downloads.json"


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


def count_downloads():
    repositories = set()
    for owner in OWNERS:
        for repository in paginate(f"/users/{owner}/repos"):
            if not repository["private"]:
                repositories.add(repository["full_name"])

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
    return total


def update_badge(output=OUTPUT):
    total = count_downloads()
    badge = {
        "schemaVersion": 1,
        "label": "Release downloads",
        "message": f"{total:,}",
        "color": "58a6ff",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(badge, indent=2) + "\n", encoding="utf-8")
    print(f"Release downloads across {', '.join(OWNERS)}: {total:,}")


if __name__ == "__main__":
    update_badge()
