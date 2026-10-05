#!/usr/bin/env python3
"""Fetch NBA scores/news, render a 400x300 NOTE4 board, and optionally upload it."""

import argparse
import datetime as dt
import html
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont
import cairosvg


CONFIG_DIR = os.environ.get("ZECTRIX_NBA_CONFIG_DIR", os.path.expanduser("~/.config/zectrix-nba-board"))
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
BASE = "https://cloud.zectrix.com/open/v1"
SCOREBOARD = os.environ.get("NBA_SCOREBOARD_URL", "https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json")
SCHEDULE = os.environ.get("NBA_SCHEDULE_URL", "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2_1.json")
# Third-party primary source. ESPN's public scoreboard endpoint is key-free and
# reachable from US datacenter egress where cdn.nba.com is Akamai-blocked. It
# accepts ?dates=YYYYMMDD, so it covers the -1..+2 day window collect() needs.
# Set NBA_SCORE_SOURCE=espn (default) or =official to force a specific source.
ESPN_SCOREBOARD = os.environ.get("NBA_ESPN_SCOREBOARD_URL", "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard")
SCORE_SOURCE = os.environ.get("NBA_SCORE_SOURCE", "espn").strip().lower()
SINA_NEWS = "https://sports.sina.com.cn/nba/"
TENCENT_NEWS = "https://sports.qq.com/nba/"
TZ = ZoneInfo("Asia/Shanghai")
CACHE_DIR = os.environ.get("ZECTRIX_NBA_CACHE_DIR", os.path.expanduser("~/.cache/zectrix-nba-board"))
TEAM_ZH = {
    "ATL": "老鹰", "BOS": "凯尔特人", "BKN": "篮网", "CHA": "黄蜂", "CHI": "公牛",
    "CLE": "骑士", "DAL": "独行侠", "DEN": "掘金", "DET": "活塞", "GSW": "勇士",
    "HOU": "火箭", "IND": "步行者", "LAC": "快船", "LAL": "湖人", "MEM": "灰熊",
    "MIA": "热火", "MIL": "雄鹿", "MIN": "森林狼", "NOP": "鹈鹕", "NYK": "尼克斯",
    "OKC": "雷霆", "ORL": "魔术", "PHI": "76人", "PHX": "太阳", "POR": "开拓者",
    "SAC": "国王", "SAS": "马刺", "TOR": "猛龙", "UTA": "爵士", "WAS": "奇才",
}
# ESPN's scoreboard uses a few non-standard team codes; normalize them to the
# official tricode before the TEAM_ZH lookup so the Chinese names resolve.
ESPN_CODE_ALIAS = {"GS": "GSW", "NO": "NOP", "NY": "NYK", "UTAH": "UTA", "PHI": "PHI"}


def _esp_code(code):
    return ESPN_CODE_ALIAS.get(code, code)


class NewsParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.items = []
        self.capture = False
        self.buffer = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        cls = "%s %s" % (attrs.get("class", ""), attrs.get("id", ""))
        if tag in {"a", "h1", "h2", "h3", "h4"} and (tag.startswith("h") or "title" in cls.lower() or "news" in cls.lower() or "article" in cls.lower()):
            self.capture = True
            self.buffer = []

    def handle_data(self, data):
        if self.capture:
            self.buffer.append(html.unescape(data).strip())

    def handle_endtag(self, tag):
        if self.capture and tag in {"a", "h1", "h2", "h3", "h4"}:
            text = re.sub(r"\s+", " ", "".join(self.buffer)).strip()
            ignored = {"首页", "更多", "登录", "注册", "直播", "赛程", "排名", "数据", "视频"}
            if 8 <= len(text) <= 80 and text not in ignored and text not in self.items:
                self.items.append(text)
            self.capture = False
W, H = 400, 300
THRESHOLD = 128
FONT_CANDIDATES = [
    os.environ.get("ZECTRIX_FONT", ""),
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "fonts", "Zfull.ttf"),
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "zectrix-morning-brief", "assets", "fonts", "Zfull.ttf"),
    os.path.expanduser("~/Library/Fonts/Zfull.ttf"),
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
]
LOGO_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "nba-script.svg")
_NBA_LOGO = None


def font(size):
    path = next((item for item in FONT_CANDIDATES if item and os.path.exists(item)), None)
    return ImageFont.truetype(path, size) if path else ImageFont.load_default()


def fit(draw, text, text_font, width):
    text = str(text or "")
    if draw.textlength(text, font=text_font) <= width:
        return text
    while text and draw.textlength(text + "…", font=text_font) > width:
        text = text[:-1]
    return text + "…"


def nba_logo():
    """Rasterize the supplied NBA wordmark once for sharp 1BPP placement."""
    global _NBA_LOGO
    if _NBA_LOGO is None:
        raw = cairosvg.svg2png(url=LOGO_FILE, output_width=42, output_height=22)
        _NBA_LOGO = Image.open(io.BytesIO(raw)).convert("RGBA")
    return _NBA_LOGO


def draw_left_centered(draw, xy, text, text_font, fill, max_width):
    """Place left-aligned text with vertical center aligned to the target band."""
    left, top, right, bottom = xy
    label = fit(draw, text, text_font, max_width or right - left)
    bbox = draw.textbbox((0, 0), label, font=text_font)
    y = (top + bottom - (bbox[3] - bbox[1])) / 2 - bbox[1]
    draw.text((left, y), label, font=text_font, fill=fill)


def draw_right_centered(draw, xy, text, text_font, fill, max_width):
    """Place right-aligned text with vertical center aligned to the target band."""
    left, top, right, bottom = xy
    label = fit(draw, text, text_font, max_width or right - left)
    bbox = draw.textbbox((0, 0), label, font=text_font)
    y = (top + bottom - (bbox[3] - bbox[1])) / 2 - bbox[1]
    draw.text((right, y), label, font=text_font, fill=fill, anchor="ra")


def fetch_json(url):
    request = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/131 Safari/537.36",
        "Accept": "application/json,text/plain,*/*",
        "Referer": "https://www.nba.com/",
        "Origin": "https://www.nba.com",
    })
    with urllib.request.urlopen(request, timeout=25) as response:
        return json.loads(response.read().decode("utf-8"))


def _zh_count(text):
    return sum(1 for char in text if "\u4e00" <= char <= "\u9fff")


_NEWS_IGNORED = ("首页", "登录", "注册", "更多", "视频", "图片", "评论", "分享",
                 "排行", "直播", "数据", "资料", "专题", "收藏", "阅读",
                 "意见反馈", "招募", "广告")


def _regex_news(html_text):
    """Extract real Chinese headline links from a Sina-style NBA listing page.

    The page's live article links all carry a recognizable path (``/doc-``,
    a ``YYYY-MM-DD`` date segment, or a ``/k/`` opinion column) and a Chinese
    title of at least a few characters. This is far more reliable than the
    class-based NewsParser, which matches nothing on Sina's current markup.
    Returns an ordered, de-duplicated list of headline strings.
    """
    found = []
    seen = set()
    for attrs, text in re.findall(r'<a\s+([^>]*href="[^"]+")>([^<{}]{8,60})</a>', html_text):
        title = html.unescape(text).strip()
        if _zh_count(title) < 4:
            continue
        if any(word in title for word in _NEWS_IGNORED):
            continue
        href = re.search(r'href="([^"]*)"', attrs)
        href = href.group(1) if href else ""
        if not re.search(r"/doc-|/k/|\d{4}-\d{2}-\d{2}/", href):
            continue
        if title in seen:
            continue
        seen.add(title)
        found.append(title)
    return found


def fetch_html(url):
    browser_ua = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0 Safari/537.36")
    request = urllib.request.Request(url, headers={
        "User-Agent": browser_ua,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "zh-CN,zh;q=0.9",
    })
    with urllib.request.urlopen(request, timeout=15) as response:
        html_text = response.read().decode("utf-8", "ignore")
    items = _regex_news(html_text)
    if not items:
        parser = NewsParser()
        parser.feed(html_text)
        items = parser.items
    return items


def cache_json(name, value):
    try:
        os.makedirs(CACHE_DIR, mode=0o700, exist_ok=True)
        with open(os.path.join(CACHE_DIR, name), "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False)
    except OSError:
        pass


def read_cache(name, default):
    try:
        with open(os.path.join(CACHE_DIR, name), encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return default


def safe_fetch(label, fetcher, default):
    for attempt in range(2):
        try:
            return fetcher()
        except (OSError, ValueError, KeyError, urllib.error.URLError) as error:
            if attempt:
                print("WARN: %s 数据源失败：%s" % (label, error), file=sys.stderr)
            else:
                time.sleep(1)
    return default


def cached_fetch(label, url, cache_name, default, html_mode=False):
    value = safe_fetch(label, (lambda: fetch_html(url)) if html_mode else (lambda: fetch_json(url)), None)
    if value is not None:
        cache_json(cache_name, value)
        return value
    return read_cache(cache_name, default)


def load_config(offline=False):
    if offline:
        return {"api_key": "", "device_id": "", "page": "3"}
    if not os.path.exists(CONFIG_FILE):
        raise RuntimeError("未找到配置，请先运行 scripts/init.py")
    with open(CONFIG_FILE, encoding="utf-8") as handle:
        return json.load(handle)


def parse_games(data, local_date):
    games = []
    source_games = data.get("scoreboard", {}).get("games") or data.get("games") or data.get("leagueSchedule", {}).get("gameDates", [])
    if source_games and isinstance(source_games[0], dict) and "games" in source_games[0]:
        source_games = [game for day in source_games for game in day.get("games", [])]
    for event in source_games:
        away = event.get("awayTeam") or {}
        home = event.get("homeTeam") or {}
        game_status = int(event.get("gameStatus", 1) or 1)
        state = "live" if game_status == 2 else ("final" if game_status == 3 else "scheduled")
        status_text = event.get("gameStatusText") or "未开始"
        if state == "scheduled":
            start = event.get("gameTimeUTC", event.get("gameDateTimeUTC", "")).replace("Z", "+00:00")
            try:
                when = dt.datetime.fromisoformat(start).astimezone(dt.timezone(dt.timedelta(hours=8))).strftime("%H:%M")
            except ValueError:
                when = "待定"
            status_text = when
        elif state == "final":
            status_text = "已结束"
        away_code = away.get("teamTricode", "客队")
        home_code = home.get("teamTricode", "主队")
        if state == "live":
            period = event.get("period", 0)
            clock = event.get("gameClock", "")
            clock_match = re.search(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?", clock)
            if clock_match:
                minutes = int(clock_match.group(2) or 0)
                seconds = int(float(clock_match.group(3) or 0))
                clock = "%02d:%02d" % (minutes, seconds)
            status_text = "中场休息" if not clock else "%s节 · 剩余 %s" % (period, clock)
        elif state == "final":
            status_text = "已结束"
        games.append({
            "away": TEAM_ZH.get(away_code, away_code), "home": TEAM_ZH.get(home_code, home_code),
            "away_code": away_code, "home_code": home_code,
            "away_score": away.get("score", "-"), "home_score": home.get("score", "-"),
            "status": status_text, "state": state,
            "start": event.get("gameTimeUTC", event.get("gameDateTimeUTC", "")) or event.get("gameDateUTC", ""),
        })
    return {"date": local_date.isoformat(), "games": games}


def parse_news(data):
    result = []
    for item in (data.get("articles") or []):
        title = item.get("headline") or item.get("title")
        if not title:
            continue
        result.append({"title": title, "source": (item.get("source") or "ESPN")})
    return result[:3]


def parse_chinese_news(items, source):
    return [{"title": title, "source": source, "age": ""} for title in items[:10]]


def sample_data(start):
    games = [
        {"away": "湖人", "home": "勇士", "away_code": "LAL", "home_code": "GSW", "away_score": "112", "home_score": "108", "status": "已结束", "state": "final", "start": ""},
        {"away": "掘金", "home": "太阳", "away_code": "DEN", "home_code": "PHX", "away_score": "-", "home_score": "-", "status": "10:00", "state": "scheduled", "start": ""},
    ]
    return {
        "days": [{"date": start.isoformat(), "games": games}, {"date": (start + dt.timedelta(1)).isoformat(), "games": [{"away": "NYK", "home": "MIA", "away_score": "-", "home_score": "-", "status": "08:30", "state": "pre"}]}, {"date": (start + dt.timedelta(2)).isoformat(), "games": []}],
        "news": [{"title": "新赛季球队阵容与轮换进入最后调整阶段", "source": "新浪体育", "age": "2小时前"}],
    }


def parse_espn_games(data, local_date):
    """Parse ESPN's public scoreboard JSON into the same game dict shape as
    parse_games(), so build_state()/render() need no changes. ESPN source is
    key-free and reachable from US datacenter egress where cdn.nba.com is
    Akamai-blocked."""
    games = []
    for event in data.get("events", []):
        competition = (event.get("competitions") or [{}])[0]
        status = competition.get("status", {}) or {}
        state = {"in": "live", "post": "final"}.get((status.get("type", {}) or {}).get("state", "pre"), "scheduled")
        competitors = competition.get("competitors", [])
        away = next((c for c in competitors if c.get("homeAway") == "away"), {})
        home = next((c for c in competitors if c.get("homeAway") == "home"), away)
        away_code = _esp_code((away.get("team") or {}).get("abbreviation", "客队"))
        home_code = _esp_code((home.get("team") or {}).get("abbreviation", "主队"))
        away_score = away.get("score", "-")
        home_score = home.get("score", "-")
        start = event.get("date", "")
        if state == "scheduled":
            try:
                when = dt.datetime.fromisoformat(start.replace("Z", "+00:00")).astimezone(TZ).strftime("%H:%M")
            except ValueError:
                when = "待定"
            status_text = when
        elif state == "live":
            period = status.get("period", 0) or 1
            clock = (status.get("displayClock") or "").strip()
            status_text = "中场休息" if clock in ("", "0.0") else "%s节 · 剩余 %s" % (period, clock)
        else:
            status_text = "已结束"
        games.append({
            "away": TEAM_ZH.get(away_code, away_code), "home": TEAM_ZH.get(home_code, home_code),
            "away_code": away_code, "home_code": home_code,
            "away_score": away_score, "home_score": home_score,
            "status": status_text, "state": state, "start": start,
        })
    return {"date": local_date.isoformat(), "games": games}


def collect(date, offline=False):
    if offline:
        return sample_data(date)
    days = []
    if SCORE_SOURCE == "espn":
        # NBA games land on the US date they start, but a Beijing calendar day
        # spans two US dates (US evening == Beijing morning). So fetch a window
        # of US dates, then re-bucket every game by its Beijing-time start date.
        # For a target Beijing day D we need US days D-1 and D, hence the range.
        by_date = {}
        for k in range(-2, 3):
            us_day = date + dt.timedelta(k)
            url = "%s?dates=%s" % (ESPN_SCOREBOARD, us_day.strftime("%Y%m%d"))
            data = cached_fetch("ESPN赛程", url, "espn-%s.json" % us_day.isoformat(), {})
            for game in parse_espn_games(data, us_day)["games"]:
                try:
                    bj_date = dt.datetime.fromisoformat(game["start"].replace("Z", "+00:00")).astimezone(TZ).date()
                except (ValueError, TypeError):
                    bj_date = date  # live/unknown -> fold into today
                by_date.setdefault(bj_date.isoformat(), []).append(game)
        for offset in range(-1, 3):
            target = (date + dt.timedelta(offset)).isoformat()
            days.append({"date": target, "games": by_date.get(target, [])})
    else:
        for offset in range(-1, 3):
            day = date + dt.timedelta(offset)
            query = urllib.parse.urlencode({"dates": day.strftime("%Y%m%d")})
            if offset == 0:
                data = cached_fetch("NBA官方赛程", SCOREBOARD, "scoreboard.json", {})
                days.append(parse_games(data, day))
            else:
                schedule = cached_fetch("NBA官方未来赛程", SCHEDULE, "schedule.json", {})
                schedule_games = parse_games(schedule, day)
                days.append({"date": day.isoformat(), "games": [game for game in schedule_games["games"] if game.get("start", "").startswith(day.isoformat())]})
    sina = parse_chinese_news(cached_fetch("新浪NBA新闻", SINA_NEWS, "sina-news.json", [], html_mode=True), "新浪体育")
    tencent = parse_chinese_news(cached_fetch("腾讯NBA新闻", TENCENT_NEWS, "tencent-news.json", [], html_mode=True), "腾讯体育")
    news = (sina + tencent)[:3]
    return {"days": days, "news": news}


def minutes_to_start(game, now):
    try:
        start = dt.datetime.fromisoformat(game["start"].replace("Z", "+00:00")).astimezone(TZ)
        return int((start - now).total_seconds() / 60)
    except (KeyError, ValueError, TypeError):
        return 99999


def select_focus(games, mode, now):
    if mode == "live":
        return sorted(games, key=lambda item: minutes_to_start(item, now), reverse=True)[0]
    return sorted(games, key=lambda item: abs(minutes_to_start(item, now)))[0]


def build_state(data, date, now):
    today = next((item for item in data["days"] if item["date"] == date.isoformat()), {"games": []})
    future = [game for item in data["days"] if item["date"] > date.isoformat() for game in item.get("games", []) if game["state"] == "scheduled"]
    live = [game for game in today.get("games", []) if game["state"] == "live"]
    scheduled = [game for game in today.get("games", []) if game["state"] == "scheduled"]
    final = [game for game in today.get("games", []) if game["state"] == "final"]
    if live:
        status = "LIVE"
        focus = select_focus(live, "live", now)
        poll = 10
    elif scheduled:
        status = "NEXT"
        focus = select_focus(scheduled, "next", now)
        poll = 10 if minutes_to_start(focus, now) <= 120 else 60
    elif final:
        status = "FINAL"
        focus = select_focus(final, "final", now)
        poll = 120
    else:
        status = "REST"
        yesterday = next((item for item in data["days"] if item["date"] < date.isoformat()), {"games": []})
        previous = [game for game in yesterday.get("games", []) if game["state"] == "final"]
        focus = previous[-1] if previous else None
        poll = 720
    recent_finals = final
    recent_date = date
    if status == "REST":
        recent_finals = []
        for day in sorted((item for item in data["days"] if item["date"] < date.isoformat()), key=lambda item: item["date"], reverse=True):
            candidates = [game for game in day.get("games", []) if game["state"] == "final"]
            if candidates:
                recent_finals = candidates
                recent_date = dt.date.fromisoformat(day["date"])
                break
    return {
        "status": status, "focus": focus, "today": today.get("games", []),
        "future": future, "poll": poll, "recent_finals": recent_finals[:3],
        "recent_date": recent_date,
    }


def render(data, date, output, now=None):
    image = Image.new("L", (W, H), 255)
    draw = ImageDraw.Draw(image)
    black, gray, white = 0, 120, 255
    now = now or dt.datetime.now(TZ)
    state = build_state(data, date, now)
    title = font(15)
    team_font = font(17)
    code_font = font(11)
    score_font = font(27)
    detail_font = font(12)
    small = font(11)
    tiny = font(10)
    draw.rounded_rectangle((12, 12, 388, 288), radius=2, outline=black, width=2)
    logo = nba_logo()
    image.alpha_composite(logo, (18, 15)) if image.mode == "RGBA" else image.paste(logo.convert("L"), (18, 15), logo.getchannel("A"))
    header_text = "%s %s NBA 赛程" % (date.strftime("%m月%d日"), ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][date.weekday()])
    title_width = draw.textlength(header_text, font=title)
    draw.text((190 - title_width / 2, 17), header_text, font=title, fill=black)
    draw_left_centered(draw, (310, 13, 382, 39), "更新 %s" % now.strftime("%H:%M"), small, gray, 72)
    draw.line((14, 43, 386, 43), fill=black, width=1)
    focus = state["focus"]
    status = state["status"]
    status_zh = {"LIVE": "直播中", "NEXT": "未开始", "FINAL": "已结束", "REST": "休赛日"}[status]
    badge_right = 90 if status == "LIVE" else 82
    draw.rounded_rectangle((20, 51, badge_right, 73), radius=3, fill=black)
    draw.text(((20 + badge_right) / 2, 62), status_zh, font=small, fill=white, anchor="mm")
    type_text = "今日无比赛" if status == "REST" else "常规赛"
    draw_left_centered(draw, (310, 51, 380, 73), type_text, small, gray, 70)
    if status in {"FINAL", "REST"} and state["recent_finals"]:
        label = "今日赛果" if status == "FINAL" else "最近比赛日赛果"
        draw_left_centered(draw, (44, 84, 356, 105), label, detail_font, black, 312)
        for index, game in enumerate(state["recent_finals"]):
            row_top = 108 + index * 27
            away = fit(draw, game.get("away"), small, 80)
            home = fit(draw, game.get("home"), small, 80)
            score = "%s : %s" % (game.get("away_score", "-"), game.get("home_score", "-"))
            draw_left_centered(draw, (44, row_top, 145, row_top + 21), away, small, black, 101)
            draw.text((200, row_top + 10), score, font=detail_font, fill=black, anchor="mm")
            draw_right_centered(draw, (255, row_top, 356, row_top + 21), home, small, black, 101)
        footer = "最近 1 个比赛日 · 共 %d 场" % len(state["recent_finals"])
        draw.text((200, 190), footer, font=tiny, fill=gray, anchor="mm")
    elif focus:
        draw_left_centered(draw, (44, 84, 136, 108), focus.get("away"), team_font, black, 92)
        draw_left_centered(draw, (44, 111, 136, 130), focus.get("away_code", "客"), code_font, gray, 92)
        draw_right_centered(draw, (264, 84, 356, 108), focus.get("home"), team_font, black, 92)
        draw_right_centered(draw, (264, 111, 356, 130), focus.get("home_code", "主"), code_font, gray, 92)
        if status == "NEXT":
            center = "@"
            detail = "今晚 %s · 北京时间" % focus.get("status", "待定")
            remaining = minutes_to_start(focus, now)
            sub = "距开赛约 %02d小时%02d分" % (max(0, remaining) // 60, max(0, remaining) % 60) if remaining < 99999 else "今日下一场比赛"
        else:
            center = "%s  :  %s" % (focus.get("away_score", "-"), focus.get("home_score", "-"))
            detail = focus.get("status", "比赛进行中") if status == "LIVE" else "全场结束"
            sub = {"LIVE": "当前直播比分", "FINAL": "今日最终赛果", "REST": "最近一场赛果"}[status]
        draw.text((200, 105), center, font=score_font, fill=black, stroke_width=1, anchor="mm")
        draw.text((200, 150), fit(draw, detail, detail_font, 232), font=detail_font, fill=black, anchor="mm")
        draw.text((200, 176), fit(draw, sub, small, 232), font=small, fill=gray, anchor="mm")
    else:
        draw_left_centered(draw, (84, 95, 316, 124), "今日暂无赛程", team_font, black, 232)
        draw_left_centered(draw, (84, 137, 316, 158), "等待下一场比赛", detail_font, gray, 232)
    draw.line((14, 202, 386, 202), fill=black, width=1)
    if status == "LIVE":
        next_games = [g for g in state["today"] if g["state"] == "scheduled"]
        aux = "NEXT  %s · 今日还有 %d 场" % (next_games[0].get("status", "待定") if next_games else "暂无", len(next_games))
    elif status == "NEXT":
        aux = "TODAY  已结束 %d 场 · 下一场后还有 %d 场" % (sum(g["state"] == "final" for g in state["today"]), max(0, len(state["today"]) - 1))
    else:
        # FINAL / REST: NEXT 行补全为「下一比赛日标签 · 开赛时间 · 共 N 场」，
        # 场次按北京开赛日分桶（data["days"] 的 date 即北京日），避免 UTC 串跨界误计。
        next_day = next((day for day in sorted((d for d in data["days"] if d["date"] > date.isoformat()), key=lambda d: d["date"]) if day.get("games")), None)
        if next_day:
            nd = dt.date.fromisoformat(next_day["date"])
            label = {1: "明日", 2: "后天"}.get((nd - date).days, nd.strftime("%m-%d"))
            def _start_key(game):
                s = game.get("status", "")
                return s if re.match(r"^\d{1,2}:\d{2}$", s) else "99:99"
            first = min(next_day["games"], key=_start_key)
            aux = "NEXT  %s · %s · 共 %d 场" % (label, first.get("status", "待定"), len(next_day["games"]))
        else:
            aux = "NEXT  暂无后续赛程"
    draw_left_centered(draw, (22, 206, 378, 250), aux, detail_font, black, 356)
    draw.line((14, 250, 386, 250), fill=black, width=1)
    news = (data.get("news") or [{}])[0]
    hot = "热点  %s · %s %s" % (news.get("title", "暂无最新中文资讯"), news.get("source", ""), news.get("age", ""))
    draw_left_centered(draw, (22, 254, 378, 286), hot, detail_font, black, 356)
    result = image.point(lambda value: 0 if value < THRESHOLD else 255, mode="1")
    result.convert("RGB").save(output)
    return state


def push(config, output):
    with open(output, "rb") as handle:
        payload = handle.read()
    boundary = "----ZectrixNBA" + os.urandom(8).hex()
    body = ("--%s\r\nContent-Disposition: form-data; name=\"pageId\"\r\n\r\n%s\r\n" % (boundary, config.get("page", "3"))).encode()
    body += ("--%s\r\nContent-Disposition: form-data; name=\"dither\"\r\n\r\nfalse\r\n" % boundary).encode()
    body += ("--%s\r\nContent-Disposition: form-data; name=\"images\"; filename=\"nba-board.png\"\r\nContent-Type: image/png\r\n\r\n" % boundary).encode() + payload + b"\r\n"
    body += ("--%s--\r\n" % boundary).encode()
    url = "%s/devices/%s/display/image" % (BASE, urllib.parse.quote(config["device_id"], safe=":"))
    request = urllib.request.Request(url, data=body, method="POST", headers={"X-API-Key": config["api_key"], "Content-Type": "multipart/form-data; boundary=%s" % boundary})
    with urllib.request.urlopen(request, timeout=40) as response:
        result = json.loads(response.read().decode("utf-8"))
    if result.get("code") != 0:
        raise RuntimeError("推送失败：%s" % result)
    print("PUSH pageId=%s OK" % config.get("page", "3"))


def main():
    parser = argparse.ArgumentParser(description="生成 Zectrix NBA 看板")
    parser.add_argument("--output", default="/tmp/zectrix-nba-board.png")
    parser.add_argument("--date", help="固定日期 YYYY-MM-DD，用于调试")
    parser.add_argument("--offline-sample", action="store_true")
    args = parser.parse_args()
    config = load_config(args.offline_sample)
    date = dt.date.fromisoformat(args.date) if args.date else dt.date.today()
    state = render(collect(date, args.offline_sample), date, args.output)
    print("saved %s" % args.output)
    print("STATE=%s POLL_MINUTES=%s" % (state["status"], state["poll"]))
    if os.environ.get("ZECTRIX_NO_PUSH") != "1" and not args.offline_sample:
        push(config, args.output)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("ERROR: %s" % error, file=sys.stderr)
        sys.exit(1)
