#!/usr/bin/env python3
"""
Tech Pulse - HTML生成スクリプト
news.jsonからダッシュボードHTMLを生成
"""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

JST = timezone(timedelta(hours=9))
DATA_DIR = Path("data")
TEMPLATE_PATH = Path("templates/dashboard.html")
OUTPUT_PATH = Path("index.html")

# タブ定義
TABS = [
    {"id": "ai", "label": "AI・LLM", "color": "#4f46e5"},
    {"id": "devtools", "label": "Dev Tools", "color": "#0284c7"},
    {"id": "data_dx", "label": "Data / DX", "color": "#d97706"},
    {"id": "cloud", "label": "Cloud", "color": "#0891b2"},
    {"id": "security", "label": "Security", "color": "#dc2626"},
    {"id": "hardware", "label": "Hardware", "color": "#65a30d"},
    {"id": "funding", "label": "Funding", "color": "#7c3aed"},
]

# アバターカラー（ソース名別）
AVATAR_COLORS = {
    "Google AI Blog": "#4285f4", "OpenAI Blog": "#10a37f", "Anthropic": "#d4a574",
    "Hugging Face": "#ffd21e", "Meta AI": "#0668E1", "TechCrunch AI": "#0a0",
    "GitHub Blog": "#333", "Hacker News": "#ff6600", "Krebs on Security": "#c00",
    "BleepingComputer": "#236b8e", "Cloudflare Blog": "#f38020",
    "AWS Blog": "#ff9900", "GCP Blog": "#4285f4", "Azure Blog": "#0078d4",
    "Databricks": "#ff3621", "dbt Blog": "#ff694b",
    "TechCrunch VC": "#0a0", "Crunchbase News": "#0288ff",
    "default": "#64748b",
}


def get_avatar_color(source: str) -> str:
    return AVATAR_COLORS.get(source, AVATAR_COLORS["default"])


def escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def build_glossary_html(glossary: list) -> str:
    if not glossary:
        return ""
    items = []
    for g in glossary[:4]:
        term = escape_html(g.get("term", ""))
        definition = escape_html(g.get("definition", ""))
        items.append(
            f'<span class="gl-item">{term}'
            f'<span class="gl-tip">{definition}</span></span>'
        )
    return f'<div class="glossary">{"".join(items)}</div>'


def build_article_html(article: dict) -> str:
    title = escape_html(article.get("title", "No title"))
    source = escape_html(article.get("source", "Unknown"))
    icon = escape_html(article.get("icon", "?"))
    published = article.get("published", "")
    url = article.get("url", "#")
    easy = escape_html(article.get("easy", ""))
    why = escape_html(article.get("why", ""))
    glossary = article.get("glossary", [])
    color = get_avatar_color(article.get("source", ""))
    score = article.get("score", 0)
    comments = article.get("comments", 0)

    score_html = ""
    if score:
        score_html = f' · <span style="color:var(--org)">▲{score}</span>'
    if comments:
        score_html += f' · 💬{comments}'

    glossary_html = build_glossary_html(glossary)

    source_html = ""
    if url and url != "#":
        source_html = f'<div class="fi-source">出典: <a href="{url}" target="_blank" rel="noopener">{source}</a>{score_html}</div>'

    easy_html = ""
    if easy:
        easy_html = f'<div class="fi-easy"><span class="emoji">🔰</span> <strong>ざっくり言うと：</strong>{easy}</div>'

    why_html = ""
    if why:
        why_html = f'<div class="fi-why">{why}</div>'

    return f"""<div class="fi">
  <div class="fi-head">
    <div class="fi-av" style="background:{color}">{icon}</div>
    <div><div class="fi-src">{source}</div></div>
    <div class="fi-time">{published}</div>
  </div>
  <div class="fi-body">
    <div class="fi-title"><a href="{url}" target="_blank" rel="noopener" style="color:inherit;text-decoration:none">{title}</a></div>
    {easy_html}
    {why_html}
    {glossary_html}
    {source_html}
  </div>
</div>"""


def build_hn_sidebar(hn_top: list) -> str:
    items = []
    for i, article in enumerate(hn_top[:10], 1):
        title = escape_html(article.get("title", ""))
        url = article.get("url", "#")
        score = article.get("score", 0)
        items.append(
            f'<div class="hn-item">'
            f'<span class="hn-rank">{i}</span>'
            f'<div class="hn-content">'
            f'<a href="{url}" target="_blank" rel="noopener" class="hn-title">{title}</a>'
            f'<span class="hn-score">▲{score}</span>'
            f'</div></div>'
        )
    return "\n".join(items)


def generate_html():
    # news.json 読み込み
    news_path = DATA_DIR / "news.json"
    if not news_path.exists():
        print("Error: data/news.json not found. Run fetch_news.py first.")
        return

    with open(news_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    updated_at = data.get("updated_at", "不明")
    tabs_data = data.get("tabs", {})
    hn_top = data.get("hn_top", [])

    # テンプレート読み込み
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template = f.read()

    # タブボタン生成
    tab_buttons = []
    for i, tab in enumerate(TABS):
        active = " active" if i == 0 else ""
        tab_buttons.append(
            f'<button class="tab-btn{active}" data-tab="{tab["id"]}">{tab["label"]}</button>'
        )
    tab_buttons_html = "\n".join(tab_buttons)

    # タブコンテンツ生成
    tab_contents = []
    for i, tab in enumerate(TABS):
        active = " active" if i == 0 else ""
        articles = tabs_data.get(tab["id"], [])
        articles_html = "\n".join(build_article_html(a) for a in articles)

        if not articles:
            articles_html = '<div class="fi" style="text-align:center;padding:40px;color:var(--mut)">このカテゴリの記事はまだありません</div>'

        hn_sidebar_html = build_hn_sidebar(hn_top)

        tab_contents.append(f"""<div class="tab-content{active}" id="tab-{tab['id']}">
  <div class="feed">{articles_html}</div>
  <div class="sidebar">
    <div class="sb-card">
      <div class="sb-title">🔥 Hacker News Top 10</div>
      {hn_sidebar_html}
    </div>
    <div class="sb-card">
      <div class="sb-title">ℹ️ About</div>
      <div style="font-size:.78rem;color:var(--dim);line-height:1.6">
        このダッシュボードは毎朝7時に自動更新されます。<br>
        ニュースはRSS/HN/Redditから取得し、Gemini AIが日本語でやさしく解説しています。
      </div>
    </div>
  </div>
</div>""")
    tab_contents_html = "\n".join(tab_contents)

    # テンプレートに埋め込み
    html = template
    html = html.replace("{{UPDATED_AT}}", updated_at)
    html = html.replace("{{TAB_BUTTONS}}", tab_buttons_html)
    html = html.replace("{{TAB_CONTENTS}}", tab_contents_html)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Dashboard generated: {OUTPUT_PATH}")
    print(f"Updated at: {updated_at}")


if __name__ == "__main__":
    generate_html()
