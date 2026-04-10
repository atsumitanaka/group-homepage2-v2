#!/usr/bin/env python3
"""
researchmap APIで各研究者の招待講演を検出し、data/news.jsonに追加するスクリプト
GitHub Actionsのcronで定期実行される
"""

import json
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

RESEARCHMAP_API = "https://api.researchmap.jp"
LOOKBACK_DAYS = 180


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path, data):
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def fetch_presentations(researchmap_id):
    """researchmap APIで講演一覧を取得する"""
    url = f"{RESEARCHMAP_API}/{researchmap_id}/presentations?limit=100&format=json"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "GroupHomepage/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data.get("items", [])
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return []
        raise


def is_invited(presentation):
    """招待講演かどうかを判定する"""
    if presentation.get("invited"):
        return True
    ptype = presentation.get("presentation_type", "")
    return "invited" in ptype.lower()


def get_text(field, prefer_lang="ja"):
    """言語対応フィールドからテキストを取得する（ja優先）"""
    if not field:
        return ""
    if isinstance(field, str):
        return field
    if prefer_lang in field:
        return field[prefer_lang]
    # ja がなければ en、それもなければ最初のものを返す
    if "en" in field:
        return field["en"]
    values = list(field.values())
    return values[0] if values else ""


def get_presenters(item):
    """発表者名を取得する"""
    presenters = item.get("presenters", {})
    names = []
    # en を優先（英語名の方が整合性が高い）
    for lang in ("en", "ja"):
        if lang in presenters:
            for p in presenters[lang]:
                name = p.get("name", "")
                if name:
                    names.append(name)
            if names:
                return ", ".join(names)
    return ""


def format_date_ja(date_str):
    """ISO日付を日本語表記に変換する"""
    if not date_str:
        return ""
    parts = date_str.split("-")
    if len(parts) == 3:
        return f"{int(parts[0])}年{int(parts[1])}月{int(parts[2])}日"
    if len(parts) == 2:
        return f"{int(parts[0])}年{int(parts[1])}月"
    return date_str


def format_event_period(from_date, to_date):
    """イベント期間を整形する"""
    from_ja = format_date_ja(from_date)
    to_ja = format_date_ja(to_date)
    if from_ja and to_ja and from_ja != to_ja:
        return f"{from_ja} - {to_ja}"
    return from_ja or to_ja


def build_news_entry(researcher, talk):
    """招待講演情報からニュースエントリを生成する"""
    talk_title = get_text(talk.get("presentation_title"))
    event_name = get_text(talk.get("event"))
    from_date = talk.get("from_event_date", "")
    to_date = talk.get("to_event_date", "")
    presenters = get_presenters(talk)

    # タイトル: 過去なら「行いました」、未来なら「行います」
    today = datetime.now().strftime("%Y-%m-%d")
    verb = "行います" if from_date > today else "行いました"
    news_title = (
        f"{researcher['name_ja']}{researcher['position_ja']}が"
        f"{event_name}で招待講演を{verb}"
    )

    # 本文
    body_lines = []
    if event_name:
        body_lines.append(f"学会名：{event_name}")
    period = format_event_period(from_date, to_date)
    if period:
        body_lines.append(f"日時：{period}")
    if presenters:
        body_lines.append(f"発表者：{presenters}")

    return {
        "date": from_date,
        "category": "お知らせ",
        "category_en": "Announcement",
        "title": news_title,
        "title_en": "",
        "paper_title": talk_title,
        "doi": "",
        "body": "<br>".join(body_lines),
        "body_en": "",
    }


def main():
    researchers = load_json(RESEARCHERS_PATH)
    news = load_json(NEWS_PATH)
    known_ids = set(load_json(KNOWN_TALKS_PATH))

    cutoff = (datetime.now() - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    print(f"Checking invited talks with event date since {cutoff}")

    new_entries = []
    new_ids = []

    for researcher in researchers:
        rm_id = researcher.get("researchmap_id", "")
        if not rm_id:
            continue

        print(f"\n{researcher['name_en']} ({rm_id})")

        try:
            presentations = fetch_presentations(rm_id)
        except Exception as e:
            print(f"  ERROR: {e}")
            continue

        for talk in presentations:
            # 招待講演のみ
            if not is_invited(talk):
                continue

            # 既知のIDはスキップ
            talk_id = talk.get("rm:id", "")
            if talk_id in known_ids:
                title = get_text(talk.get("presentation_title"))[:50]
                print(f"  Skip (known): {title}...")
                continue

            # 期間外はスキップ
            from_date = talk.get("from_event_date", "")
            if from_date and from_date < cutoff:
                continue

            entry = build_news_entry(researcher, talk)
            new_entries.append(entry)
            if talk_id:
                new_ids.append(talk_id)
                known_ids.add(talk_id)

            print(f"  NEW: {get_text(talk.get('presentation_title'))[:60]}...")

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
