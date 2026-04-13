#!/usr/bin/env python3
"""
NIMS SAMURAIの各研究者のプレゼンテーション一覧から招待講演を検出し、
data/news.jsonに追加するスクリプト。
GitHub Actionsのcronで定期実行される。
"""

import json
import re
import sys
import time
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"
RESEARCHERS_PATH = DATA_DIR / "researchers.json"
NEWS_PATH = DATA_DIR / "news.json"
KNOWN_TALKS_PATH = DATA_DIR / "known_talk_ids.json"

SAMURAI_BASE = "https://samurai.nims.go.jp"
LOOKBACK_YEARS = 1


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path, data):
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def fetch_presentations_html(samurai_id):
    """SAMURAIの研究業績ページからプレゼンテーションセクションのHTMLを取得する"""
    url = f"{SAMURAI_BASE}/profiles/{samurai_id}/publications?locale=en"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "GroupHomepage/1.0"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def parse_invited_presentations(html, min_year):
    """HTMLからプレゼンテーションセクションを解析し、招待講演を抽出する"""
    # プレゼンテーションセクションを特定
    anchor = html.find('<a name="presentation">')
    if anchor < 0:
        return []

    # 次のセクション境界まで切り出し
    section = html[anchor:]
    next_anchor = section.find('<a name="', 10)
    if next_anchor > 0:
        section = section[:next_anchor]

    results = []
    # 年度ブロックを走査
    year_blocks = re.split(r'<h5 class="small_subject">(\d{4})</h5>', section)

    # year_blocks[0] はヘッダー部分、[1]=年, [2]=内容, [3]=年, [4]=内容, ...
    for i in range(1, len(year_blocks) - 1, 2):
        year = int(year_blocks[i])
        if year < min_year:
            continue
        block = year_blocks[i + 1]

        # 各 <li> を解析
        items = re.findall(r"<li[^>]*>(.*?)</li>", block, re.DOTALL)
        for item in items:
            if 'invited_presentation' not in item:
                continue

            # プレゼンテーションUUIDを抽出
            uuid_match = re.search(
                r'/presentations/([0-9a-f-]{36})', item
            )
            talk_id = uuid_match.group(1) if uuid_match else ""

            # タイトルを抽出（プレゼンテーションリンクのテキスト）
            title_match = re.search(
                r'/presentations/[^"]*"[^>]*>(.*?)</a>', item
            )
            title = _strip_html(title_match.group(1)) if title_match else ""

            # 学会名を抽出（タイトルリンクの後、年の前のテキスト）
            # パターン: </a>. 学会名. 年
            event_match = re.search(
                r'</a>\.\s*(.*?)\.\s*\d{4}', item, re.DOTALL
            )
            event = _strip_html(event_match.group(1)).strip() if event_match else ""

            # 著者を抽出（<li>の先頭からタイトルリンクの前まで）
            authors_match = re.search(r'^(.*?)<a href="/presentations/', item, re.DOTALL)
            authors = ""
            if authors_match:
                raw = authors_match.group(1)
                authors = _strip_html(raw).strip().rstrip(".")

            results.append({
                "id": talk_id,
                "title": title,
                "event": event,
                "year": year,
                "authors": authors,
            })

    return results


def _strip_html(s):
    """HTMLタグを除去する"""
    return re.sub(r"<[^>]+>", "", s).strip()


def build_news_entry(researcher, talk):
    """招待講演情報からニュースエントリを生成する"""
    year = talk["year"]
    event = talk["event"]
    title = talk["title"]
    authors = talk["authors"]

    # 日付は年のみ（SAMURAIには日付情報なし）
    date_iso = f"{year}-01-01"
    date_ja = f"{year}年"

    # タイトル
    today_year = datetime.now().year
    verb = "行います" if year > today_year else "行いました"
    news_title = (
        f"{researcher['name_ja']}{researcher['position_ja']}が"
        f"{event}で招待講演を{verb}"
    )

    # 本文
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
        "body": "<br>".join(body_lines),
        "body_en": "",
    }


def main():
    researchers = load_json(RESEARCHERS_PATH)
    news = load_json(NEWS_PATH)
    known_ids = set(load_json(KNOWN_TALKS_PATH))

    min_year = datetime.now().year - LOOKBACK_YEARS
    print(f"Checking invited talks from SAMURAI (year >= {min_year})")

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
            print(f"  ERROR: {e}")
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
            new_entries.append(entry)
            new_ids.append(talk_id)
            known_ids.add(talk_id)

            print(f"  NEW: {talk['title'][:60]}...")

        # レートリミット対策
        time.sleep(1)

    if not new_entries:
        print("\nNo new invited talks found.")
        return

    # news.jsonに追加
    news.extend(new_entries)
    news.sort(key=lambda x: x.get("date", ""), reverse=True)
    save_json(NEWS_PATH, news)

    # 既知IDを保存
    all_ids = sorted(known_ids)
    save_json(KNOWN_TALKS_PATH, all_ids)

    print(f"\nAdded {len(new_entries)} invited talk(s) to news.json:")
    for e in new_entries:
        print(f"  - {e['paper_title'][:70]}")


if __name__ == "__main__":
    main()
