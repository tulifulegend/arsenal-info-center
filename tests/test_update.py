import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_dist  # noqa: E402
import update_data  # noqa: E402
import verify_data  # noqa: E402

NOW = datetime(2026, 11, 13, 12, 0, tzinfo=timezone.utc)
SECRET = "supersecretvalue123"


def rss(items, last_build="Fri, 13 Nov 2026 07:40:00 +0000"):
    rows = []
    for item in items:
        encoded = item.get("encoded", "")
        rows.append(
            f"""<item>
              <title><![CDATA[{item['title']}]]></title>
              <link>{item['link']}</link>
              <pubDate>{item['pubDate']}</pubDate>
              <description><![CDATA[{item.get('description', '')}]]></description>
              <content:encoded><![CDATA[{encoded}]]></content:encoded>
            </item>"""
        )
    xml = f"""<?xml version="1.0"?>
      <rss xmlns:content="http://purl.org/rss/1.0/modules/content/">
        <channel>
          <title>sample</title>
          <lastBuildDate>{last_build}</lastBuildDate>
          {''.join(rows)}
        </channel>
      </rss>"""
    return xml.encode("utf-8")


def podcast_item(title, link, when="Tue, 10 Nov 2026 09:16:02 GMT", duration="1:10:17"):
    return f"""<item>
      <title>{title}</title>
      <link>{link}</link>
      <pubDate>{when}</pubDate>
      <itunes:duration>{duration}</itunes:duration>
      <itunes:summary><![CDATA[<p>Short episode notes about the match.</p>]]></itunes:summary>
    </item>"""


def podcast_feed():
    items = []
    for number in range(900, 888, -1):
        items.append(
            podcast_item(
                f"Episode {number} - sample",
                f"https://shows.acast.com/arseblog/episodes/episode-{number}",
                f"Wed, {max(1, number - 890)} Nov 2026 09:00:00 GMT",
            )
        )
    for number in range(720, 708, -1):
        items.append(
            podcast_item(
                f"Arsecast Extra Episode {number} - 09.11.2026",
                f"https://shows.acast.com/arseblog/episodes/extra-{number}",
            )
        )
    for number in range(181, 169, -1):
        items.append(
            podcast_item(
                f"Arsenal Women Arsecast Episode {number}: sample",
                f"https://shows.acast.com/arseblog/episodes/women-{number}",
            )
        )
    items.append(
        podcast_item(
            "Arseblog launches on Patreon - an explanation",
            "https://shows.acast.com/arseblog/episodes/patreon-explainer",
        )
    )
    items.append(
        podcast_item(
            "BONUS PODCAST! The 30 - Season preview",
            "https://shows.acast.com/arseblog/episodes/bonus-preview",
        )
    )
    items.append(
        podcast_item(
            "Paid extra",
            "https://www.patreon.com/arseblog/posts/1",
        )
    )
    xml = f"""<?xml version="1.0"?>
      <rss xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
        <channel><title>Arsecast</title>{''.join(items)}</channel>
      </rss>"""
    return xml.encode("utf-8")


def fixture(fid, home, away, date, status="NS", league_id=39, league="Premier League", round_name="Regular Season - 12", goals=None, season=2026, venue="Emirates Stadium"):
    home_id = 42 if home == "Arsenal" else 99
    away_id = 42 if away == "Arsenal" else 100
    return {
        "fixture": {
            "id": fid,
            "date": date,
            "status": {"short": status},
            "venue": {"name": venue},
        },
        "league": {"id": league_id, "name": league, "season": season, "round": round_name},
        "teams": {
            "home": {"id": home_id, "name": home},
            "away": {"id": away_id, "name": away},
        },
        "goals": {
            "home": None if goals is None else goals[0],
            "away": None if goals is None else goals[1],
        },
    }


def api_body(response, errors=None):
    return json.dumps({"response": response, "errors": [] if errors is None else errors, "results": len(response)}).encode()


def leagues_body(ids):
    response = [
        {"league": {"id": league_id, "name": name, "type": kind}, "seasons": [{"year": 2026}]}
        for league_id, name, kind in ids
    ]
    return api_body(response)


class Scripted:
    def __init__(self, routes):
        self.routes = routes
        self.urls = []
        self.headers = []

    def __call__(self, url, headers, timeout=45):
        self.urls.append(url)
        self.headers.append(headers)
        for key, value in self.routes.items():
            if key in url:
                if isinstance(value, Exception):
                    raise value
                status, body = value
                if isinstance(body, str):
                    body = body.encode("utf-8")
                return status, {}, body
        raise update_data.FetchError("unexpected " + url)


class UpdateTests(unittest.TestCase):
    def setUp(self):
        import tempfile

        self._dir = tempfile.TemporaryDirectory()
        self.data = Path(self._dir.name)

    def tearDown(self):
        self._dir.cleanup()

    def news_routes(self, guardian=None):
        blog = rss(
            [
                {
                    "title": "Building in Barca",
                    "link": "https://arseblog.com/2026/11/building-in-barca/",
                    "pubDate": "Fri, 13 Nov 2026 07:34:18 +0000",
                    "description": "<p>Hello from Barcelona.</p><p>The post Building in Barca appeared first on Arseblog ... an Arsenal blog.</p>",
                    "encoded": "FULL_ARTICLE_MARKER_XYZ " + ("word " * 800),
                },
                {
                    "title": "<script>alert(1)</script>",
                    "link": "https://arseblog.com/evil",
                    "pubDate": "Fri, 13 Nov 2026 06:00:00 +0000",
                    "description": "nope",
                },
                {
                    "title": "Bad link",
                    "link": "javascript:alert(1)",
                    "pubDate": "Fri, 13 Nov 2026 05:00:00 +0000",
                    "description": "nope",
                },
            ]
        )
        if guardian is None:
            guardian = rss(
                [
                    {
                        "title": "Odegaard winner",
                        "link": "https://www.theguardian.com/football/2026/nov/07/arsenal-hull",
                        "pubDate": "Sat, 07 Nov 2026 17:02:45 GMT",
                        "description": "Patience is a virtue. " + ("Long lede. " * 80),
                        "encoded": "GUARDIAN_FULL_BODY " + ("sentence " * 500),
                    }
                ]
            )
        return {
            "arseblog.com/feed": (200, blog),
            "theguardian.com": (200, guardian),
            "rss.acast.com": (200, podcast_feed()),
        }

    def test_excerpt_strips_boilerplate_and_limits_length(self):
        text = update_data.excerpt(
            "<p>Hello <b>there</b>. Arseblog\u2019s notes.</p><script>secret()</script>"
            + ("<p>More detail about the match.</p>" * 20)
            + "<p>The post Hello appeared first on Arseblog news.</p>"
        )
        self.assertNotIn("<", text)
        self.assertNotIn("secret", text)
        self.assertNotIn("appeared first", text)
        self.assertLessEqual(len(text), 160)
        self.assertTrue(text.endswith("..."))
        self.assertNotIn("\u2019", text)

    def test_news_podcasts_and_beijing_time(self):
        http = Scripted(self.news_routes())
        update_data.run(self.data, env={}, now=NOW, http_get=http)
        news = json.loads((self.data / "news.json").read_text(encoding="utf-8"))
        blob = json.dumps(news, ensure_ascii=False)
        self.assertNotIn("FULL_ARTICLE_MARKER_XYZ", blob)
        self.assertNotIn("GUARDIAN_FULL_BODY", blob)
        self.assertNotIn("javascript:", blob)
        titles = [item["title"] for item in news["items"]]
        self.assertIn("Building in Barca", titles)
        self.assertNotIn("alert(1)", " ".join(titles))
        blog = next(item for item in news["items"] if item["sourceId"] == "arseblog")
        self.assertEqual(blog["publishedAt"], "2026-11-13T15:34:18+08:00")
        self.assertNotIn("appeared first", blog["summary"])
        guardian = next(item for item in news["items"] if item["sourceId"] == "guardian")
        self.assertLessEqual(len(guardian["summary"]), 160)
        self.assertTrue(all(item["publishedAt"].endswith("+08:00") for item in news["items"]))
        podcasts = json.loads((self.data / "podcasts.json").read_text(encoding="utf-8"))
        kinds = {}
        for item in podcasts["items"]:
            kinds[item["kind"]] = kinds.get(item["kind"], 0) + 1
            self.assertNotIn("patreon", item["title"].lower())
            self.assertNotIn("patreon.com", item["url"])
            self.assertNotIn("bonus", item["title"].lower())
        self.assertEqual(kinds, {"episode": 6, "extra": 6, "women": 6})
        self.assertTrue(any(item["duration"] == "1小时10分" for item in podcasts["items"]))
        self.assertTrue(all("api-sports.io" not in url for url in http.urls))
        self.assertEqual(verify_data.problems(self.data), [])

    def test_failed_source_keeps_previous_items(self):
        http = Scripted(self.news_routes())
        update_data.run(self.data, env={}, now=NOW, http_get=http)
        original = json.loads((self.data / "news.json").read_text(encoding="utf-8"))
        guardian_urls = [item["url"] for item in original["items"] if item["sourceId"] == "guardian"]
        later = NOW + timedelta(hours=1)
        http_fail = Scripted(
            {
                "arseblog.com/feed": (
                    200,
                    rss(
                        [
                            {
                                "title": "A newer blog",
                                "link": "https://arseblog.com/2026/11/newer/",
                                "pubDate": "Fri, 13 Nov 2026 10:00:00 +0000",
                                "description": "Fresh excerpt.",
                            }
                        ]
                    ),
                ),
                "theguardian.com": update_data.FetchError("超时"),
                "rss.acast.com": update_data.FetchError("超时"),
            }
        )
        update_data.run(self.data, env={}, now=later, http_get=http_fail)
        news = json.loads((self.data / "news.json").read_text(encoding="utf-8"))
        urls = [item["url"] for item in news["items"]]
        self.assertIn("https://arseblog.com/2026/11/newer/", urls)
        self.assertNotIn("https://arseblog.com/2026/11/building-in-barca/", urls)
        for url in guardian_urls:
            self.assertIn(url, urls)
        self.assertTrue(news["stale"])
        self.assertIn("上次缓存", news["message"])
        podcasts = json.loads((self.data / "podcasts.json").read_text(encoding="utf-8"))
        self.assertTrue(podcasts["stale"])
        self.assertEqual(len(podcasts["items"]), 18)
        status = json.loads((self.data / "status.json").read_text(encoding="utf-8"))
        self.assertIn("仍在显示上次成功缓存", status["banner"])

    def test_fixtures_failure_keeps_cache_and_hides_key(self):
        http = Scripted(self.news_routes())
        update_data.run(self.data, env={}, now=NOW, http_get=http)
        cached = update_data.empty_fixtures()
        cached["available"] = True
        cached["matches"] = [
            {
                "id": 7,
                "competition": "英超",
                "competitionRaw": "Premier League",
                "competitionId": 39,
                "round": "第11轮",
                "kickoff": "2026-11-08T20:00:00+08:00",
                "status": "finished",
                "statusText": "已结束",
                "home": "阿森纳",
                "homeEn": "Arsenal",
                "away": "赫尔城",
                "awayEn": "Hull City",
                "arsenalSide": "home",
                "score": {"home": 1, "away": 0},
                "venue": "酋长球场",
                "venueEn": "Emirates Stadium",
                "season": 2026,
            }
        ]
        views = update_data.annotate_fixture_views(cached["matches"])
        cached.update(views)
        cached["fetchedAt"] = "2026-11-13T18:00:00+08:00"
        update_data.write_json(self.data / "fixtures.json", cached)
        http_fail = Scripted(
            {
                **self.news_routes(),
                "v3.football.api-sports.io/fixtures": (
                    200,
                    json.dumps({"errors": {"token": SECRET}, "response": []}),
                ),
            }
        )
        update_data.run(
            self.data,
            env={"API_FOOTBALL_KEY": SECRET, "FORCE_FIXTURES": "true"},
            now=NOW + timedelta(hours=9),
            http_get=http_fail,
        )
        fixtures = json.loads((self.data / "fixtures.json").read_text(encoding="utf-8"))
        self.assertTrue(fixtures["stale"])
        self.assertEqual(fixtures["matches"][0]["id"], 7)
        self.assertEqual(fixtures["matches"][0]["score"]["home"], 1)
        self.assertIn("上次成功缓存", fixtures["message"])
        tree = "\n".join(path.read_text(encoding="utf-8") for path in self.data.glob("*.json"))
        self.assertNotIn(SECRET, tree)
        self.assertTrue(any("/fixtures" in url for url in http_fail.urls))
        self.assertEqual(sum("/leagues" in url for url in http_fail.urls), 0)

    def test_missing_key_does_not_call_api_and_coverage_is_honest(self):
        routes = self.news_routes()
        matches = [
            fixture(1, "Arsenal", "Hull City", "2026-11-22T15:00:00+00:00"),
            fixture(2, "Liverpool", "Arsenal", "2026-11-01T16:30:00+00:00", status="FT", goals=(0, 1), venue="Anfield"),
            fixture(3, "Arsenal", "Slavia Praha", "2026-11-04T20:00:00+00:00", status="FT", league_id=2, league="UEFA Champions League", round_name="League Stage - 4", goals=(2, 1)),
            fixture(4, "Arsenal", "Brighton", "2026-10-28T19:30:00+00:00", status="FT", league_id=48, league="League Cup", round_name="Round of 16", goals=(3, 0)),
        ]
        routes["v3.football.api-sports.io/fixtures"] = (200, api_body(matches))
        routes["v3.football.api-sports.io/leagues"] = (
            200,
            leagues_body(
                [
                    (39, "Premier League", "League"),
                    (2, "UEFA Champions League", "Cup"),
                    (48, "League Cup", "Cup"),
                ]
            ),
        )
        http = Scripted(routes)
        update_data.run(self.data, env={"API_FOOTBALL_KEY": SECRET, "FORCE_FIXTURES": "true"}, now=NOW, http_get=http)
        fixtures = json.loads((self.data / "fixtures.json").read_text(encoding="utf-8"))
        self.assertTrue(fixtures["coverage"]["complete"])
        self.assertEqual(fixtures["nextMatch"]["away"], "赫尔城")
        self.assertEqual(fixtures["nextMatch"]["kickoff"], "2026-11-22T23:00:00+08:00")
        scores = [item["score"] for item in fixtures["results"]]
        self.assertIn({"home": 0, "away": 1}, scores)
        self.assertEqual(fixtures["results"][0]["score"], {"home": 2, "away": 1})
        self.assertIn("欧冠", fixtures["results"][0]["competition"])
        self.assertIn("16强", [item["round"] for item in fixtures["matches"]])
        self.assertNotIn(SECRET, (self.data / "fixtures.json").read_text(encoding="utf-8"))
        sent = [headers for url, headers in zip(http.urls, http.headers) if "api-sports.io" in url]
        self.assertTrue(sent)
        self.assertEqual(sent[0].get("x-apisports-key"), SECRET)
        self.assertTrue(all(SECRET not in url for url in http.urls))

        bare = Scripted(self.news_routes())
        update_data.run(self.data, env={}, now=NOW + timedelta(minutes=30), http_get=bare)
        self.assertTrue(all("api-sports.io" not in url for url in bare.urls))
        kept = json.loads((self.data / "fixtures.json").read_text(encoding="utf-8"))
        self.assertTrue(kept["stale"])
        self.assertEqual(kept["nextMatch"]["id"], fixtures["nextMatch"]["id"])

    def test_incomplete_cup_coverage_is_flagged_without_a_second_season(self):
        routes = self.news_routes()
        routes["v3.football.api-sports.io/fixtures"] = (
            200,
            api_body([fixture(1, "Arsenal", "Hull City", "2026-11-22T15:00:00+00:00", status="FT", goals=(1, 0))]),
        )
        routes["v3.football.api-sports.io/leagues"] = (
            200,
            leagues_body(
                [
                    (39, "Premier League", "League"),
                    (45, "FA Cup", "Cup"),
                ]
            ),
        )
        http = Scripted(routes)
        update_data.run(self.data, env={"API_FOOTBALL_KEY": SECRET, "FORCE_FIXTURES": "true"}, now=NOW, http_get=http)
        fixtures = json.loads((self.data / "fixtures.json").read_text(encoding="utf-8"))
        self.assertFalse(fixtures["coverage"]["complete"])
        self.assertIn("足总杯", fixtures["coverage"]["warning"])
        self.assertIn("免费套餐", fixtures["coverage"]["warning"])
        season_calls = [url for url in http.urls if "/fixtures" in url]
        self.assertEqual(len(season_calls), 1)
        self.assertIn("season=2026", season_calls[0])
        self.assertNotIn("season=2025", season_calls[0])

    def test_plan_error_does_not_guess_an_older_season(self):
        routes = self.news_routes()
        routes["v3.football.api-sports.io/fixtures"] = (
            200,
            json.dumps({"errors": {"plan": "Free plans do not have access to this season"}, "response": []}).encode(),
        )
        http = Scripted(routes)
        update_data.run(self.data, env={"API_FOOTBALL_KEY": SECRET, "FORCE_FIXTURES": "true"}, now=NOW, http_get=http)
        fixtures = json.loads((self.data / "fixtures.json").read_text(encoding="utf-8"))
        self.assertFalse(fixtures["available"])
        self.assertIn("免费套餐", fixtures["message"])
        self.assertEqual(sum("/fixtures" in url for url in http.urls), 1)

    def test_schedule_quota_and_narrow_merge(self):
        kickoff = NOW + timedelta(minutes=30)
        existing = update_data.empty_fixtures()
        existing["available"] = True
        existing["fetchedAt"] = update_data.to_shanghai_iso(NOW - timedelta(hours=1))
        existing["matches"] = [
            {
                "id": 10,
                "competition": "英超",
                "competitionRaw": "Premier League",
                "competitionId": 39,
                "round": "第12轮",
                "kickoff": update_data.to_shanghai_iso(kickoff),
                "status": "scheduled",
                "statusText": "未开始",
                "home": "阿森纳",
                "homeEn": "Arsenal",
                "away": "切尔西",
                "awayEn": "Chelsea",
                "arsenalSide": "home",
                "score": None,
                "venue": "酋长球场",
                "venueEn": "Emirates Stadium",
                "season": 2026,
            },
            {
                "id": 11,
                "competition": "欧冠",
                "competitionRaw": "UEFA Champions League",
                "competitionId": 2,
                "round": "联赛阶段",
                "kickoff": "2026-12-09T04:00:00+08:00",
                "status": "scheduled",
                "statusText": "未开始",
                "home": "阿森纳",
                "homeEn": "Arsenal",
                "away": "国际米兰",
                "awayEn": "Inter",
                "arsenalSide": "home",
                "score": None,
                "venue": "酋长球场",
                "venueEn": "Emirates Stadium",
                "season": 2026,
            },
        ]
        existing.update(update_data.annotate_fixture_views(existing["matches"]))
        existing["coverage"] = {
            "season": 2026,
            "seasonLabel": "2026/2027",
            "checked": True,
            "complete": True,
            "competitions": [],
            "missing": [],
            "warning": None,
        }
        meta = update_data.empty_meta(NOW)
        meta["lastFixturesAttempt"] = update_data.to_shanghai_iso(NOW - timedelta(minutes=10))
        meta["lastFixturesSuccess"] = update_data.to_shanghai_iso(NOW - timedelta(hours=1))
        self.assertEqual(update_data.choose_fixture_mode(meta, existing, NOW, False), "skip")
        meta["lastFixturesAttempt"] = update_data.to_shanghai_iso(NOW - timedelta(minutes=40))
        self.assertEqual(update_data.choose_fixture_mode(meta, existing, NOW, False), "narrow")
        stale_meta = dict(meta)
        stale_meta["lastFixturesSuccess"] = update_data.to_shanghai_iso(NOW - timedelta(hours=10))
        outside = dict(existing)
        outside["matches"] = [
            dict(existing["matches"][1], kickoff="2026-12-09T04:00:00+08:00", status="scheduled")
        ]
        self.assertEqual(update_data.choose_fixture_mode(stale_meta, outside, NOW, False), "full")
        self.assertFalse(
            update_data.in_match_window(
                [{"status": "inplay", "kickoff": "2026-11-01T12:00:00+08:00"}],
                NOW,
            )
        )

        update_data.write_json(self.data / "fixtures.json", existing)
        update_data.write_json(self.data / "meta.json", meta)
        routes = self.news_routes()
        routes["v3.football.api-sports.io/fixtures"] = (
            200,
            api_body(
                [
                    fixture(
                        10,
                        "Arsenal",
                        "Chelsea",
                        kickoff.isoformat(),
                        status="1H",
                        goals=(1, 0),
                    )
                ]
            ),
        )
        http = Scripted(routes)
        update_data.run(self.data, env={"API_FOOTBALL_KEY": SECRET}, now=NOW, http_get=http)
        fixtures = json.loads((self.data / "fixtures.json").read_text(encoding="utf-8"))
        by_id = {item["id"]: item for item in fixtures["matches"]}
        self.assertEqual(by_id[10]["status"], "inplay")
        self.assertEqual(by_id[10]["score"], {"home": 1, "away": 0})
        self.assertIn(11, by_id)
        self.assertIn("不是实时比分", fixtures["scoreDisclaimer"])
        self.assertNotIn("实时直播", json.dumps(fixtures, ensure_ascii=False))
        self.assertTrue(any("from=" in url for url in http.urls))
        self.assertFalse(any("/leagues" in url for url in http.urls))

        meta_cap = json.loads((self.data / "meta.json").read_text(encoding="utf-8"))
        meta_cap["requests"] = 80
        meta_cap["lastFixturesAttempt"] = update_data.to_shanghai_iso(NOW - timedelta(hours=9))
        update_data.write_json(self.data / "meta.json", meta_cap)
        http_cap = Scripted(self.news_routes())
        update_data.run(
            self.data,
            env={"API_FOOTBALL_KEY": SECRET, "FORCE_FIXTURES": "true"},
            now=NOW + timedelta(minutes=5),
            http_get=http_cap,
        )
        self.assertTrue(all("api-sports.io" not in url for url in http_cap.urls))
        status = json.loads((self.data / "status.json").read_text(encoding="utf-8"))
        self.assertTrue(status["fixtures"]["quotaHeld"])
        self.assertEqual(json.loads((self.data / "fixtures.json").read_text(encoding="utf-8"))["matches"][0]["id"] in {10, 11}, True)

    def test_frontend_contract_and_snapshot_escape(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "js/app.js").read_text(encoding="utf-8")
        workflow = (ROOT / ".github/workflows/update.yml").read_text(encoding="utf-8")
        self.assertIn("阿森纳足球信息中心", html)
        self.assertIn("snapshot.html", html)
        self.assertIn("localStorage", js)
        self.assertIn('fetch("data/" + name + ".json"', js)
        for blocked in ("api-sports.io", "theguardian.com", "arseblog.com/feed", "rss.acast.com", "football-data.org"):
            self.assertNotIn(blocked, js)
        self.assertIn("secrets.API_FOOTBALL_KEY", workflow)
        self.assertIn("workflow_dispatch", workflow)
        self.assertIn("*/30 * * * *", workflow)
        self.assertNotIn("football-data.org", workflow)
        script = build_dist.embed_script({"news": {"items": [{"title": "</script><script>alert(1)</script>"}]}})
        self.assertNotIn("<script>alert", script)
        self.assertIn("\\u003c", script)
        import tempfile

        with tempfile.TemporaryDirectory() as dist_name:
            built = build_dist.build(ROOT, Path(dist_name))
            snapshot = (built / "snapshot.html").read_text(encoding="utf-8")
            self.assertIn("window.__AIC_DATA__", snapshot)
            self.assertNotIn('src="js/app.js"', snapshot)
            self.assertNotIn('href="css/site.css"', snapshot)
            sample = json.loads((ROOT / "data" / "news.json").read_text(encoding="utf-8"))["items"][0]["title"]
            self.assertIn(sample, snapshot)
            self.assertIn("function loadFavs", snapshot)

    def test_verify_rejects_a_long_summary(self):
        update_data.write_json(self.data / "news.json", {"items": [{"title": "x", "summary": "y" * 400, "url": "https://example.com", "publishedAt": "2026-11-13T12:00:00+08:00", "sourceId": "arseblog"}]})
        update_data.write_json(self.data / "podcasts.json", {"items": []})
        update_data.write_json(self.data / "fixtures.json", {"scoreDisclaimer": update_data.SCORE_DISCLAIMER, "matches": []})
        update_data.write_json(self.data / "status.json", {"generatedAt": "2026-11-13T20:00:00+08:00"})
        self.assertTrue(verify_data.problems(self.data))


if __name__ == "__main__":
    unittest.main()
