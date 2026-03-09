#!/usr/bin/env python3
"""
研究者の追加肩書きをSAMURAI + researchmapから自動取得してHTMLを更新するスクリプト

データソース:
  1. SAMURAI HTML <ul class="concurrent"> → NIMS部署名 + 役職名
  2. SAMURAI HTML「外部併任先」→ 外部所属（東工大、横浜国大等）
  3. SAMURAI HTML「学生受け入れ」→ NIMS連携大学院（筑波大等）
  4. researchmap API → 上記で取れない外部所属の補完 + EN翻訳

使い方:
  python3 scripts/update_roles.py          # 差分を表示（dry-run）
  python3 scripts/update_roles.py --apply  # HTMLファイルを更新
"""

import json
import re
import sys
import urllib.request
from pathlib import Path

# ── 研究者定義 ──────────────────────────────────────────────
RESEARCHERS = [
    {
        "name_ja": "出村 雅彦",
        "name_en": "Masahiko Demura",
        "samurai_id": "demura_masahiko",
        "researchmap_id": "read0003464",
    },
    {
        "name_ja": "石井 真史",
        "name_en": "Masashi Ishii",
        "samurai_id": "ishii_masashi",
        "researchmap_id": "ishiimasashi",
    },
    {
        "name_ja": "戸田 佳明",
        "name_en": "Yoshiaki Toda",
        "samurai_id": "toda_yoshiaki",
        "researchmap_id": "read0080019",
    },
    {
        "name_ja": "渡邊 育夢",
        "name_en": "Ikumu Watanabe",
        "samurai_id": "watanabe_ikumu",
        "researchmap_id": "ikumu",
    },
    {
        "name_ja": "伊藤 海太",
        "name_en": "Kaita Ito",
        "samurai_id": "ito_kaita",
        "researchmap_id": "ito_kaita",
    },
    {
        "name_ja": "桂 ゆかり",
        "name_en": "Yukari Katsura",
        "samurai_id": "katsura_yukari",
        "researchmap_id": "ykatsura",
    },
    {
        "name_ja": "柿沼 洋",
        "name_en": "Hiroshi Kakinuma",
        "samurai_id": "kakinuma_hiroshi",
        "researchmap_id": "hiroshikakinuma",
    },
]

# members.html で使われている名前（スペースなし）→ マッチ用
NAME_MATCH_JA = {
    "出村 雅彦": "出村",
    "石井 真史": "石井",
    "戸田 佳明": "戸田",
    "渡邊 育夢": "渡邊",
    "伊藤 海太": "伊藤 海太",  # 伊藤は一般的なので長めに
    "桂 ゆかり": "桂",
    "柿沼 洋": "柿沼",
}


# ── API取得 ─────────────────────────────────────────────────
def fetch_url(url):
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8")


def fetch_json(url):
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


# ── SAMURAIパーサー ─────────────────────────────────────────
def parse_concurrent_groups(html_ja, html_en):
    """SAMURAI <ul class='concurrent'> から部署+役職をペアで取得"""
    def extract(html):
        groups = []
        lis = re.findall(r'<li class="main_unit">(.*?)</li>', html)
        for li in lis:
            items = re.findall(r'<a[^>]*href="([^"]*)"[^>]*>([^<]+)</a>', li)
            dept_parts = []
            role_part = ""
            for href, text in items:
                text = text.strip()
                if "employee_position" in href:
                    role_part = text
                elif "unit=" in href:
                    dept_parts.append(text)
            groups.append({"dept": " ".join(dept_parts), "role": role_part})
        return groups

    ja = extract(html_ja)
    en = extract(html_en)

    paired = []
    for i, jg in enumerate(ja):
        eg = en[i] if i < len(en) else {"dept": "", "role": ""}
        ja_str = (jg["dept"] + " " + jg["role"]).strip() if jg["dept"] else jg["role"]
        en_str = (eg["dept"] + " " + eg["role"]).strip() if eg["dept"] else eg["role"]
        paired.append({"ja": ja_str, "en": en_str})
    return paired


def parse_section_text(html, marker, end_markers):
    """HTML内の特定セクション（h2等）の後のテキストを取得"""
    idx = html.find(marker)
    if idx < 0:
        return []
    section = html[idx : idx + 3000]
    for em in end_markers:
        eidx = section.find(em, len(marker))
        if eidx > 0:
            section = section[:eidx]
            break
    clean = re.sub(r"<[^>]+>", "\n", section)
    lines = [l.strip() for l in clean.split("\n") if l.strip()]
    return lines[1:]  # skip header


def parse_student_positions(html_ja, html_en):
    """学生受け入れセクションから大学ポジションを取得（重複排除）"""
    def extract(html, start, ends):
        lines = parse_section_text(html, start, ends)
        positions = []
        seen = set()
        for l in lines:
            if "准教授" in l or "教授" in l or "professor" in l.lower():
                l = l.replace("&#39;", "'")
                if l not in seen:
                    seen.add(l)
                    positions.append(l)
        return positions

    ja = extract(html_ja, "学生受け入れ", ["外部併任先", "研究内容", "NIMS各種制度"])
    en = extract(html_en, "Accepting Students", ["External", "Research", "NIMS Programs"])
    return ja, en


# ── researchmap ─────────────────────────────────────────────
def fetch_researchmap_external(rm_id):
    """researchmap APIから非NIMS所属を取得"""
    try:
        data = fetch_json(f"https://api.researchmap.jp/{rm_id}")
    except Exception:
        return []

    externals = []
    for aff in data.get("affiliations", []):
        org_ja = aff.get("affiliation", {}).get("ja", "")
        if "物質・材料研究機構" in org_ja or "NIMS" in org_ja.upper():
            continue
        parts_ja, parts_en = [], []
        for field in ["affiliation", "section", "job"]:
            val = aff.get(field, {})
            if val.get("ja"):
                parts_ja.append(val["ja"])
            if val.get("en"):
                parts_en.append(val["en"])
            elif val.get("ja"):
                parts_en.append(val["ja"])
        jt = aff.get("job_title", {})
        if jt.get("ja"):
            parts_ja.append(f"({jt['ja']})")
        if jt.get("en"):
            parts_en.append(f"({jt['en']})")
        elif jt.get("ja"):
            parts_en.append(f"({jt['ja']})")
        externals.append({"ja": " ".join(parts_ja), "en": " ".join(parts_en)})
    return externals


# ── 統合ロジック ────────────────────────────────────────────
def build_additional_roles(researcher):
    """SAMURAI + researchmapから追加肩書きを生成"""
    s_id = researcher["samurai_id"]
    rm_id = researcher["researchmap_id"]

    html_ja = fetch_url(f"https://samurai.nims.go.jp/profiles/{s_id}?locale=ja")
    html_en = fetch_url(f"https://samurai.nims.go.jp/profiles/{s_id}?locale=en")

    # 1. NIMS concurrent groups + roles（材料モデリンググループは除外）
    groups = parse_concurrent_groups(html_ja, html_en)
    nims = [
        g
        for g in groups
        if "材料モデリンググループ" not in g["ja"]
        and "Materials Modeling" not in g["en"]
    ]

    # 2. 外部併任先（SAMURAI）
    ext_samurai_ja = parse_section_text(
        html_ja, "外部併任先", ["研究内容", "Research", "Keywords"]
    )
    ext_samurai_ja = [e for e in ext_samurai_ja if e not in ["Keywords", "研究内容"]]

    # 3. 学生受け入れ（SAMURAI）
    stu_ja, stu_en = parse_student_positions(html_ja, html_en)

    # 4. researchmap外部所属
    rm_ext = fetch_researchmap_external(rm_id)

    # ── 統合 ──
    final_ja = []
    final_en = []

    # (a) NIMS groups + roles
    for g in nims:
        final_ja.append(g["ja"])
        final_en.append(g["en"])

    # (b) 外部併任先 → ENはresearchmapから補完
    for ej in ext_samurai_ja:
        final_ja.append(ej)
        matched = False
        for rm in rm_ext:
            org_key = rm["ja"].split()[0] if rm["ja"] else ""
            if org_key and len(org_key) > 2 and org_key in ej:
                final_en.append(rm["en"])
                matched = True
                break
        if not matched:
            final_en.append(ej)  # EN未登録→JAをフォールバック

    # (c) 学生受け入れ（同じ大学でもサブプログラム違いは全て追加）
    for i, sj in enumerate(stu_ja):
        # 外部併任先と完全重複する場合のみスキップ
        if any(sj in f for f in final_ja):
            continue
        final_ja.append(sj + " (NIMS連携大学院)")
        if i < len(stu_en):
            final_en.append(stu_en[i] + " (NIMS Joint Graduate School)")

    # (d) researchmap-onlyの外部所属（SAMURAI未カバー分を補完）
    #     学生受け入れや外部併任先で既にカバーされている大学はスキップ
    for rm in rm_ext:
        org_ja = rm["ja"]
        if not org_ja:
            continue
        # 大学名の基幹部分を抽出（「筑波大学大学院」→「筑波大学」等）
        org_base = org_ja.split()[0]
        if "大学" in org_base:
            org_base = org_base[: org_base.index("大学") + 2]  # 「○○大学」まで
        if len(org_base) <= 2:
            continue
        already = any(org_base in f for f in final_ja)
        if already:
            continue
        final_ja.append(rm["ja"])
        final_en.append(rm["en"])

    # (e) 柿沼のような場合: SAMURAI外部併任先が組織名のみ→researchmapで上書き
    for i, fj in enumerate(final_ja):
        # 組織名のみ（スペースなし）で、researchmapにより詳しいデータがある場合
        if " " not in fj and not any(
            k in fj for k in ["部門", "センター", "グループ", "理事長"]
        ):
            for rm in rm_ext:
                if fj in rm["ja"] and len(rm["ja"]) > len(fj):
                    final_ja[i] = rm["ja"]
                    if i < len(final_en):
                        final_en[i] = rm["en"]
                    break

    return final_ja, final_en


# ── HTML更新 ────────────────────────────────────────────────
def update_members_html(filepath, researcher, roles_ja, roles_en, dry_run=True):
    """members.htmlのmember-additional-rolesを更新"""
    content = Path(filepath).read_text(encoding="utf-8")
    name_ja = researcher["name_ja"]
    name_en = researcher["name_en"]

    # 言語判定
    is_en = "-en.html" in str(filepath)
    roles = roles_en if is_en else roles_ja
    new_roles_html = "<br>".join(roles)

    # 対象の研究者のmember-additional-rolesを見つけて更新
    # members.htmlの構造: member-name → member-title-label → member-additional-roles
    # パターン: name_ja or name_en の近くにある member-additional-roles
    search_name = name_en if is_en else NAME_MATCH_JA.get(name_ja, name_ja.split()[0])

    # member-additional-rolesタグを見つける
    pattern = re.compile(
        r'(<p class="member-additional-roles">)(.*?)(</p>)', re.DOTALL
    )

    matches = list(pattern.finditer(content))
    if not matches:
        return content, False

    # 対象研究者に最も近いmember-additional-rolesを見つける
    name_pos = content.find(search_name)
    if name_pos < 0:
        return content, False

    closest_match = None
    closest_dist = float("inf")
    for m in matches:
        dist = m.start() - name_pos
        if 0 < dist < closest_dist:
            closest_dist = dist
            closest_match = m

    if closest_match is None:
        return content, False

    old_roles = closest_match.group(2)
    if old_roles.strip() == new_roles_html.strip():
        return content, False

    if dry_run:
        print(f"  File: {filepath}")
        print(f"  Old: {old_roles.strip()}")
        print(f"  New: {new_roles_html}")
        return content, True

    new_content = (
        content[: closest_match.start()]
        + closest_match.group(1)
        + new_roles_html
        + closest_match.group(3)
        + content[closest_match.end() :]
    )
    Path(filepath).write_text(new_content, encoding="utf-8")
    return new_content, True


# ── メイン ──────────────────────────────────────────────────
def main():
    dry_run = "--apply" not in sys.argv
    script_dir = Path(__file__).parent
    base_dir = script_dir.parent  # group-homepage2/

    if dry_run:
        print("=== DRY RUN (差分表示のみ) ===")
        print("実際に更新するには: python3 scripts/update_roles.py --apply\n")
    else:
        print("=== APPLY MODE (HTMLファイルを更新) ===\n")

    # 更新対象ファイル
    target_files = [
        base_dir / "members.html",
        base_dir / "members-en.html",
    ]

    for r in RESEARCHERS:
        print(f"\n{'='*60}")
        print(f"■ {r['name_ja']} ({r['name_en']})")
        print(f"{'='*60}")

        try:
            roles_ja, roles_en = build_additional_roles(r)
        except Exception as e:
            print(f"  ERROR: {e}")
            continue

        print(f"  JA: {'<br>'.join(roles_ja)}")
        print(f"  EN: {'<br>'.join(roles_en)}")

        for filepath in target_files:
            if not filepath.exists():
                continue
            _, changed = update_members_html(filepath, r, roles_ja, roles_en, dry_run)
            if changed and not dry_run:
                print(f"  ✅ Updated: {filepath.name}")
            elif not changed:
                print(f"  (no change: {filepath.name})")

    if dry_run:
        print("\n" + "=" * 60)
        print("実際に更新するには: python3 scripts/update_roles.py --apply")


if __name__ == "__main__":
    main()
