#!/usr/bin/env python3
"""
サロンメンバー サイト更新チェッカー
- スプレッドシートまたはローカルCSVからメンバー一覧とURLを取得
- 各サイトのRSS/Atomフィードを自動検出・取得
- 新着記事を抽出し、スマホ対応の軽量ポータルHTMLを出力
"""

import os
import sys
import re
import csv
import io
import html
from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin, urlparse, parse_qs
import requests
import feedparser
from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader
import pytz

# 定数
JST = pytz.timezone('Asia/Tokyo')
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 (Salon-Feed-Checker/1.0)'
}
TIMEOUT = 12  # リクエストタイムアウト（秒）


def clean_html(raw_html: str, max_length: int = 120) -> str:
    """HTMLタグを除去してプレーンテキストにトリム"""
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r'\s+', ' ', text)
    if len(text) > max_length:
        return text[:max_length] + "..."
    return text


def parse_datetime(entry) -> datetime:
    """feedparserのエントリからJSTのdatetimeを取得"""
    time_tuple = getattr(entry, 'published_parsed', None) or getattr(entry, 'updated_parsed', None)
    if time_tuple:
        try:
            dt = datetime(*time_tuple[:6], tzinfo=timezone.utc)
            return dt.astimezone(JST)
        except Exception:
            pass
    return datetime.now(JST)


def extract_spreadsheet_csv_url(sheet_input: str) -> str:
    """GoogleスプレッドシートのURLからCSVエクスポートURLを生成"""
    sheet_input = sheet_input.strip()
    if not sheet_input.startswith("http"):
        return sheet_input

    # Google Sheets URLパターン
    match = re.search(r'/spreadsheets/d/([a-zA-Z0-9-_]+)', sheet_input)
    if match:
        doc_id = match.group(1)
        # gidの取得
        gid = "0"
        gid_match = re.search(r'[#&?]gid=([0-9]+)', sheet_input)
        if gid_match:
            gid = gid_match.group(1)
        return f"https://docs.google.com/spreadsheets/d/{doc_id}/export?format=csv&gid={gid}"
    return sheet_input


def load_members(source: str) -> list:
    """スプレッドシートまたはCSVファイルからメンバー一覧を読み込む"""
    print(f"[INFO] メンバー情報を読み込んでいます: {source}")
    csv_text = ""

    if source.startswith("http://") or source.startswith("https://"):
        url = extract_spreadsheet_csv_url(source)
        print(f"[INFO] GoogleスプレッドシートCSV取得URL: {url}")
        res = requests.get(url, headers=DEFAULT_HEADERS, timeout=TIMEOUT)
        res.raise_for_status()
        res.encoding = res.apparent_encoding or 'utf-8'
        csv_text = res.text
    else:
        if not os.path.exists(source):
            raise FileNotFoundError(f"ファイルが見つかりません: {source}")
        with open(source, "r", encoding="utf-8-sig") as f:
            csv_text = f.read()

    reader = csv.reader(io.StringIO(csv_text))
    rows = [row for row in reader if any(cell.strip() for cell in row)]
    if not rows:
        return []

    # ヘッダー解析
    header = [c.strip().lower() for c in rows[0]]
    name_idx, url_idx = -1, -1

    # ヘッダー名からの推測
    for idx, col in enumerate(header):
        if any(keyword in col for keyword in ["名前", "氏名", "メンバー", "name", "ユーザー"]):
            name_idx = idx
        elif any(keyword in col for keyword in ["url", "サイト", "ブログ", "link", "アドレス"]):
            url_idx = idx

    # ヘッダーが見つからなかった場合のフォールバック（URLが含まれる列を探す）
    start_row = 1
    if name_idx == -1 or url_idx == -1:
        start_row = 0
        for r_idx, row in enumerate(rows[:5]):
            for c_idx, cell in enumerate(row):
                if cell.strip().startswith("http://") or cell.strip().startswith("https://"):
                    url_idx = c_idx
                    name_idx = 0 if c_idx != 0 else 1
                    start_row = 1 if r_idx == 0 else 0
                    break
            if url_idx != -1:
                break

    if name_idx == -1:
        name_idx = 0
    if url_idx == -1:
        url_idx = 1 if len(rows[0]) > 1 else 0

    members = []
    for row in rows[start_row:]:
        if len(row) <= max(name_idx, url_idx):
            continue
        name = row[name_idx].strip()
        site_url = row[url_idx].strip()
        if not site_url or not (site_url.startswith("http://") or site_url.startswith("https://")):
            continue
        members.append({
            "name": name or "No Name",
            "url": site_url
        })

    print(f"[SUCCESS] {len(members)} 名のメンバー情報を読み込みました")
    return members


def find_rss_feed(site_url: str) -> str:
    """サイトURLからRSS/AtomフィードのURLを自動検出"""
    # 1. すでにフィードURLそのものが渡されているか検証
    try:
        f = feedparser.parse(site_url, request_headers=DEFAULT_HEADERS)
        if f.entries and len(f.entries) > 0:
            return site_url
    except Exception:
        pass

    parsed = urlparse(site_url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"

    # 2. HTMLの<link rel="alternate">タグを探す
    try:
        res = requests.get(site_url, headers=DEFAULT_HEADERS, timeout=TIMEOUT)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            feed_links = soup.find_all("link", rel=lambda x: x and "alternate" in x.lower())
            for link in feed_links:
                feed_type = link.get("type", "").lower()
                if "rss" in feed_type or "atom" in feed_type or "xml" in feed_type:
                    href = link.get("href")
                    if href:
                        return urljoin(site_url, href)
    except Exception as e:
        print(f"[WARN] HTMLパース失敗 ({site_url}): {e}")

    # 3. 代表的なフィードパスを試す
    common_paths = [
        "/feed",
        "/feed/",
        "/rss",
        "/rss.xml",
        "/atom.xml",
        "/?feed=rss2",
        "/index.xml"
    ]
    # note.com の場合
    if "note.com" in parsed.netloc:
        parts = [p for p in parsed.path.split("/") if p]
        if parts:
            common_paths.insert(0, f"/{parts[0]}/rss")

    for path in common_paths:
        candidate = urljoin(site_url, path)
        try:
            candidate_feed = feedparser.parse(candidate, request_headers=DEFAULT_HEADERS)
            if candidate_feed.entries and len(candidate_feed.entries) > 0:
                return candidate
        except Exception:
            continue

    return ""


def fetch_member_updates(members: list) -> dict:
    """各メンバーのサイトから新着記事を取得"""
    now = datetime.now(JST)
    all_articles = []
    members_data = []
    updated_today_count = 0

    for idx, member in enumerate(members):
        name = member["name"]
        url = member["url"]
        print(f"[{idx+1}/{len(members)}] チェック中: {name} ({url})")

        feed_url = find_rss_feed(url)
        feed_articles = []
        site_title = name

        if feed_url:
            try:
                feed = feedparser.parse(feed_url, request_headers=DEFAULT_HEADERS)
                if hasattr(feed, 'feed') and hasattr(feed.feed, 'title'):
                    site_title = feed.feed.title or name

                for entry in feed.entries[:5]:  # 最新5件
                    published_at = parse_datetime(entry)
                    title = getattr(entry, 'title', 'No Title')
                    link = getattr(entry, 'link', url)
                    summary_raw = getattr(entry, 'summary', '') or getattr(entry, 'description', '')
                    summary = clean_html(summary_raw, max_length=100)

                    diff_hours = (now - published_at).total_seconds() / 3600
                    is_new_today = diff_hours <= 24
                    is_recent = diff_hours <= 72

                    article = {
                        "member_name": name,
                        "site_title": site_title,
                        "site_url": url,
                        "title": title,
                        "link": link,
                        "summary": summary,
                        "published_at": published_at.strftime('%Y-%m-%d %H:%M'),
                        "published_dt": published_at,
                        "published_ts": int(published_at.timestamp() * 1000),
                        "is_new_today": is_new_today,
                        "is_recent": is_recent,
                    }
                    feed_articles.append(article)
                    all_articles.append(article)
            except Exception as e:
                print(f"[ERROR] フィード取得エラー ({name}): {e}")
        else:
            print(f"[WARN] RSSフィードが見つかりませんでした: {name} ({url})")

        latest_dt = feed_articles[0]["published_dt"] if feed_articles else None
        has_new_today = any(a["is_new_today"] for a in feed_articles)
        if has_new_today:
            updated_today_count += 1

        members_data.append({
            "name": name,
            "url": url,
            "site_title": site_title,
            "feed_url": feed_url,
            "has_feed": bool(feed_url),
            "articles": feed_articles,
            "latest_article": feed_articles[0] if feed_articles else None,
            "latest_update": latest_dt.strftime('%Y-%m-%d %H:%M') if latest_dt else "取得なし",
            "latest_dt": latest_dt or datetime(1970, 1, 1, tzinfo=JST),
            "has_new_today": has_new_today
        })

    # 全記事を公開日時降順でソート
    all_articles.sort(key=lambda x: x["published_dt"], reverse=True)

    # 各メンバーおよび記事にファビコンURLを付与
    for m in members_data:
        netloc = urlparse(m["url"]).netloc
        m["favicon"] = f"https://www.google.com/s2/favicons?domain={netloc}&sz=64"

    for a in all_articles:
        netloc = urlparse(a["site_url"]).netloc
        a["favicon"] = f"https://www.google.com/s2/favicons?domain={netloc}&sz=64"

    # メンバー一覧を最終更新日時順でソート（更新がある人を上位に）
    members_data.sort(key=lambda x: x["latest_dt"], reverse=True)

    return {
        "all_articles": all_articles,
        "members": members_data,
        "total_members": len(members),
        "total_articles": len(all_articles),
        "updated_today_count": updated_today_count,
        "checked_at": now.strftime('%Y年%m月%d日 %H:%M (JST)'),
        "now_iso": now.isoformat()
    }


def generate_rss_feed(data: dict, output_path: str):
    """全メンバーの新着記事をまとめた統合RSS 2.0フィードを生成"""
    articles = data.get("all_articles", [])[:30]
    now = datetime.now(JST)

    items_xml = []
    for a in articles:
        pub_rfc822 = a["published_dt"].strftime("%a, %d %b %Y %H:%M:%S +0900")
        items_xml.append(f"""    <item>
      <title><![CDATA[[{a['member_name']}] {a['title']}]]></title>
      <link>{html.escape(a['link'])}</link>
      <guid isPermaLink="true">{html.escape(a['link'])}</guid>
      <pubDate>{pub_rfc822}</pubDate>
      <description><![CDATA[{a['summary']}]]></description>
      <author><![CDATA[{a['member_name']}]]></author>
    </item>""")

    rss_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>サロンメンバー 統合更新フィード</title>
    <link>https://github.com</link>
    <description>サロンメンバーのブログ・サイト更新まとめフィード</description>
    <language>ja</language>
    <lastBuildDate>{now.strftime("%a, %d %b %Y %H:%M:%S +0900")}</lastBuildDate>
{chr(10).join(items_xml)}
  </channel>
</rss>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(rss_content)
    print(f"[SUCCESS] 統合RSSフィードを出力しました: {output_path}")


def render_html(data: dict, template_dir: str, output_path: str):
    """HTMLを生成して出力し、静的アセット（アイコン・マニフェスト）をコピー"""
    out_dir = os.path.dirname(output_path)
    os.makedirs(out_dir, exist_ok=True)
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template("index.html")
    rendered = template.render(**data)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(rendered)
    print(f"[SUCCESS] HTMLを出力しました: {output_path}")

    # アイコンやmanifest等の静的ファイルをdistへコピー
    import shutil
    for fname in os.listdir(template_dir):
        if fname.endswith(('.png', '.ico', '.svg', '.json', '.jpg', '.webp')):
            src = os.path.join(template_dir, fname)
            dst = os.path.join(out_dir, fname)
            shutil.copy2(src, dst)
            print(f"[INFO] 静的アセットをコピーしました: {fname}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Salon Members Site Update Checker")
    parser.add_argument("--source", default=None, help="Spreadsheet URL or local CSV path")
    parser.add_argument("--output", default="dist/index.html", help="Output HTML file path")
    parser.add_argument("--templates", default="templates", help="Template directory")
    args = parser.parse_args()

    # データソースの優先順位:
    # 1. コマンドライン引数 --source
    # 2. 環境変数 SPREADSHEET_URL
    # 3. data/members.csv（存在する場合）
    # 4. data/members_sample.csv（デフォルト）
    source = args.source or os.environ.get("SPREADSHEET_URL")
    if not source:
        if os.path.exists("data/members.csv"):
            source = "data/members.csv"
        else:
            source = "data/members_sample.csv"

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    template_dir = os.path.join(base_dir, args.templates)
    output_path = os.path.join(base_dir, args.output)

    try:
        members = load_members(source)
        if not members:
            print("[WARN] メンバーが1件も登録されていません")
            sys.exit(0)

        data = fetch_member_updates(members)
        render_html(data, template_dir, output_path)

        rss_output_path = os.path.join(os.path.dirname(output_path), "rss.xml")
        generate_rss_feed(data, rss_output_path)

        print("[FINISHED] すべての処理が正常に完了しました！")
    except Exception as e:
        print(f"[FATAL] エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
