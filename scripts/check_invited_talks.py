#!/usr/bin/env python3
"""
NIMS SAMURAIの各研究者のプレゼンテーション一覧から招待講演を検出し、
News Admin（GASエンドポイント）経由でnews.jsonに追加するスクリプト。
GitHub Actionsのcronで定期実行される。
"""

import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"
RESEARCHERS_PATH = DATA_DIR / "researchers.json"
KNOWN_TALKS_PATH = DATA_DIR / "known_talk_ids.json"

SAMURAI_BASE = "https://samurai.nims.go.jp"

# GAS_URL は環境変数で上書き可能（GitHub Secretsから渡す想定）
DEFAULT_GAS_URL = (
    "https://script.google.com/macros/s/"
    "AKfycbx_u67JnXKn5Fb3tcD6fQyn1as28Im6gcgdK7Mb9UAD6V3jCS2-Qn7tJYK14P9UN6qB/exec"
)
GAS_URL = os.environ.get("GAS_URL", DEFAULT_GAS_URL)

# 検索対象の年（2025年度 = 2025年）
LOOKBACK_YEARS = 1
POST_DELAY = 10  # GAS経由のコミットSHA競合を避けるため


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path, data):
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


# ── SAMURAI HTML パース ──

def fetch_presentations_html(samurai_id):
    """SAMURAIの研究業績ページからHTMLを取得する"""
    url = f"{SAMURAI_BASE}/profiles/{samurai_id}/publications?locale=en"
    req = urllib.request.Request(url, headers={"User-Agent": "GroupHomepage/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def parse_invited_presentations(html, min_year):
    """HTMLのプレゼンテーションセクションから招待講演を抽出する"""
    anchor = html.find('<a name="presentation">')
    if anchor < 0:
        return []

    section = html[anchor:]
    next_anchor = section.find('<a name="', 10)
    if next_anchor > 0:
        section = section[:next_anchor]

    results = []
    year_blocks = re.split(r'<h5 class="small_subject">(\d{4})</h5>', section)

    for i in range(1, len(year_blocks) - 1, 2):
        year = int(year_blocks[i])
        if year < min_year:
            continue
        block = year_blocks[i + 1]

        items = re.findall(r"<li[^>]*>(.*?)</li>", block, re.DOTALL)
        for item in items:
            if "invited_presentation" not in item:
                continue

            uuid_match = re.search(r"/presentations/([0-9a-f-]{36})", item)
            talk_id = uuid_match.group(1) if uuid_match else ""

            title_match = re.search(r'/presentations/[^"]*"[^>]*>(.*?)</a>', item)
            title = _strip_html(title_match.group(1)) if title_match else ""

            event_match = re.search(r"</a>\.\s*(.*?)\.\s*\d{4}", item, re.DOTALL)
            event = _strip_html(event_match.group(1)).strip() if event_match else ""

            authors_match = re.search(r"^(.*?)<a href=\"/presentations/", item, re.DOTALL)
            authors = ""
            if authors_match:
                authors = _strip_html(authors_match.group(1)).strip().rstrip(".")

            results.append({
                "id": talk_id,
                "title": title,
                "event": event,
                "year": year,
                "authors": authors,
            })

    return results


def _strip_html(s):
    return re.sub(r"<[^>]+>", "", s).strip()


# ── GASへの投稿 ──

def post_to_gas(entry):
    """GASエンドポイント経由でnews.jsonにエントリを追加する"""
    payload = {
        "action": "add",
        "date": entry["date"],
        "category": entry["category"],
        "category_en": entry["category_en"],
        "title": entry["title"],
        "title_en": entry["title_en"],
        "url": entry.get("url", ""),
        "paper_title": entry.get("paper_title", ""),
        "doi": entry.get("doi", ""),
        "body": entry["body"],
        "body_en": entry["body_en"],
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        GAS_URL,
        data=data,
        headers={"Content-Type": "text/plain"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    if result.get("status") != "ok":
        raise RuntimeError(f"GAS error: {result.get('message', 'unknown')}")
    return result


# ── ニュースエントリ生成 ──

def build_news_entry(researcher, talk):
    """招待講演情報からニュースエントリを生成する"""
    year = talk["year"]
    event = talk["event"]
    title = talk["title"]
    authors = talk["authors"]

    date_iso = f"{year}-01-01"
    date_ja = f"{year}年"

    today_year = datetime.now().year
    verb = "行います" if year > today_year else "行いました"
    news_title = (
        f"{researcher['name_ja']}{researcher['position_ja']}が"
        f"{event}で招待講演を{verb}"
    )

    body_lines = []
    if event:
        body_lines.append(f"学会名：{event}")
    if date_ja:
        body_lines.append(f"日時：{date_ja}")
    if authors:
        body_lines.append(f"発表者：{authors}")

    return {
        "date": date_iso,
        "category": "お知らせ",
        "category_en": "Announcement",
        "title": news_title,
        "title_en": "",
        "url": "",
        "paper_title": title,
        "doi": "",
        "body": "\n".join(body_lines),
        "body_en": "",
    }


def main():
    researchers = load_json(RESEARCHERS_PATH)
    known_ids = set(load_json(KNOWN_TALKS_PATH))

    min_year = datetime.now().year - LOOKBACK_YEARS
    print(f"Checking invited talks from SAMURAI (year >= {min_year})")
    print(f"Posting via GAS: {GAS_URL[:60]}...")

    new_entries = []
    new_ids = []

    for researcher in researchers:
        samurai_id = researcher.get("samurai_id", "")
        if not samurai_id:
            continue

        print(f"\n{researcher['name_en']} ({samurai_id})")

        try:
            html = fetch_presentations_html(samurai_id)
        except Exception as e:
            print(f"  ERROR fetching: {e}")
            continue

        talks = parse_invited_presentations(html, min_year)

        for talk in talks:
            talk_id = talk["id"]
            if not talk_id:
                continue
            if talk_id in known_ids:
                print(f"  Skip (known): {talk['title'][:50]}...")
                continue

            entry = build_news_entry(researcher, talk)
            new_entries.append((entry, talk_id))
            known_ids.add(talk_id)

            print(f"  NEW: {talk['title'][:60]}...")

        time.sleep(1)

    if not new_entries:
        print("\nNo new invited talks found.")
        return

    # GAS経由で投稿（SHA競合を避けるため逐次送信）
    posted_ids = []
    for i, (entry, talk_id) in enumerate(new_entries):
        try:
            print(f"\nPosting [{i+1}/{len(new_entries)}]: {entry['paper_title'][:50]}...")
            post_to_gas(entry)
            posted_ids.append(talk_id)
            print(f"  OK")
        except Exception as e:
            print(f"  ERROR posting: {e}")

        if i < len(new_entries) - 1:
            time.sleep(POST_DELAY)

    # 投稿成功分のIDを既知リストに保存
    all_ids = sorted(set(load_json(KNOWN_TALKS_PATH)) | set(posted_ids))
    save_json(KNOWN_TALKS_PATH, all_ids)

    print(f"\nPosted {len(posted_ids)}/{len(new_entries)} invited talk(s) via Admin")


if __name__ == "__main__":
    main()
