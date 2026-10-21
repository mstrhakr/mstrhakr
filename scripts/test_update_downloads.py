import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import update_downloads as downloads


class DownloadsTests(unittest.TestCase):
    def test_pagination(self):
        with patch.object(downloads, "request_json", side_effect=[list(range(100)), [100]]) as request:
            self.assertEqual(list(downloads.paginate("/items")), list(range(101)))
        self.assertEqual(
            [call.args[0] for call in request.call_args_list],
            ["/items?per_page=100&page=1", "/items?per_page=100&page=2"],
        )

    def test_invalid_api_response_fails(self):
        with patch.object(downloads, "request_json", return_value={"message": "error"}):
            with self.assertRaises(ValueError):
                list(downloads.paginate("/items"))

    def test_counts_public_repos_once_including_prereleases_and_forks(self):
        repo = {"full_name": "owner/fork", "private": False, "fork": True, "stargazers_count": 99}
        routes = {
            "/users/one/repos": [repo, {"full_name": "one/private", "private": True}],
            "/users/two/repos": [repo],
            "/repos/owner/fork/releases": [
                {"draft": False, "assets": [{"download_count": 1200}, {"download_count": 34}]},
                {"draft": False, "prerelease": True, "assets": [{"download_count": 5}]},
                {"draft": True, "assets": [{"download_count": 999}]},
                {"draft": False, "assets": []},
            ],
        }
        with patch.object(downloads, "OWNERS", ("one", "two")):
            with patch.object(downloads, "paginate", side_effect=lambda path: iter(routes[path])) as pages:
                self.assertEqual(downloads.count_totals(), (1239, 99))
        self.assertEqual(pages.call_count, 3)

    def test_invalid_counts_fail(self):
        for count in (-1, "12", True, None):
            with self.subTest(count=count):
                routes = {
                    "/users/one/repos": [{"full_name": "one/repo", "private": False, "stargazers_count": 0}],
                    "/repos/one/repo/releases": [
                        {"draft": False, "assets": [{"download_count": count}]},
                    ],
                }
                with patch.object(downloads, "OWNERS", ("one",)):
                    with patch.object(downloads, "paginate", side_effect=lambda path: iter(routes[path])):
                        with self.assertRaises(ValueError):
                            downloads.count_totals()

    def test_invalid_star_counts_fail(self):
        for count in (-1, "12", True, None):
            with self.subTest(count=count):
                repo = {"full_name": "one/repo", "private": False, "stargazers_count": count}
                with patch.object(downloads, "OWNERS", ("one",)):
                    with patch.object(downloads, "paginate", return_value=iter([repo])):
                        with self.assertRaises(ValueError):
                            downloads.count_totals()

    def test_stars_sum_across_distinct_repositories(self):
        routes = {
            "/users/one/repos": [
                {"full_name": "one/repo", "private": False, "stargazers_count": 99},
                {"full_name": "one/empty", "private": False, "stargazers_count": 0},
            ],
            "/users/two/repos": [
                {"full_name": "two/repo", "private": False, "stargazers_count": 11},
            ],
            "/repos/one/repo/releases": [],
            "/repos/one/empty/releases": [],
            "/repos/two/repo/releases": [],
        }
        with patch.object(downloads, "OWNERS", ("one", "two")):
            with patch.object(downloads, "paginate", side_effect=lambda path: iter(routes[path])):
                self.assertEqual(downloads.count_totals(), (0, 110))

    def test_badge_shape_and_exact_count(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / "badges" / "downloads.json"
            stars_output = output.with_name("stars.json")
            with patch.object(downloads, "count_totals", return_value=(123456, 1234)):
                downloads.update_badge(output, stars_output)
            self.assertEqual(json.loads(output.read_text()), {
                "schemaVersion": 1,
                "label": "Release downloads",
                "message": "123,456",
                "color": "58a6ff",
            })
            self.assertEqual(json.loads(stars_output.read_text()), {
                "schemaVersion": 1,
                "label": "Project stars",
                "message": "1,234",
                "color": "58a6ff",
            })

    def test_failure_preserves_existing_badge(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / "downloads.json"
            stars_output = Path(directory) / "stars.json"
            output.write_text("previous badge", encoding="utf-8")
            stars_output.write_text("previous stars", encoding="utf-8")
            with patch.object(downloads, "count_totals", side_effect=RuntimeError("API failed")):
                with self.assertRaises(RuntimeError):
                    downloads.update_badge(output, stars_output)
            self.assertEqual(output.read_text(), "previous badge")
            self.assertEqual(stars_output.read_text(), "previous stars")


if __name__ == "__main__":
    unittest.main()
