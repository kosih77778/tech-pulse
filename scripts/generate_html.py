#!/usr/bin/env python3
"""
Tech Pulse v2 - HTML生成スクリプト（強化版）
日本語UI、開発者反応、重要度バー、タグ、速報表示に対応
"""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

JST = timezone(timedelta(hours=9))
DATA_DIR = Path("data")
TEMPLATE_PATH = Path("templates/dashboard.html")
OUTPUT_PATH = Path("index.html")

TABS = [
    {"id": "ai", "label": "AI・LLM", "emoji": "\U0001f9e0"},
    {"id": "devtools", "label": "Dev Tools", "emoji": "\u26a1"},
    {"id": "data_dx", "label": "Data / DX", "emoji": "\U0001f5c4\ufe0f"},
    {"id": "cloud", "label": "Cloud", "emoji": "\u2601\ufe0f"},
    {"id": "security", "label": "Security", "emoji": "\U0001f6e1\ufe0f"},
    {"id": "hardware", "label": "Hardware", "emoji": "\U0001f527"},
    {"id": "funding", "label": "Funding", "emoji": "\U0001f4b0"},
]

AVATAR_COLORS = {
    "Google AI Blog": "#4285f4", "OpenAI Blog": "#10a37f", "Anthropic": "#d4a574",
    "Hugging Face": "#ffd21e", "Meta AI": "#0668E1", "TechCrunch AI": "#0a0",
    "GitHub Blog": "#333", "Hacker News": "#ff6600", "Krebs on Security": "#c00",
    "BleepingComputer": "#236b8e", "Cloudflare Blog": "#f38020",
    "AWS Blog": "#ff9900", "GCP Blog": "#4285f4", "Azure Blog": "#0078d4",
    "Databricks": "#ff3621", "dbt Blog": "#ff694b",
    "TechCrunch VC": "#0a0", "Crunchbase News": "#0288ff",
    "Tom's Hardware": "#e00", "SemiAnalysis": "#1a1a2e",
    "Azure DevOps Blog": "#0078d4", "Rust Blog": "#dea584",
    "Node.js Blog": "#339933", "TypeScript Blog": "#3178c6",
    "GCP Data": "#4285f4", "AWS Big Data": "#ff9900",
    "HashiCorp": "#000", "The Hacker News": "#333",
    "default": "#64748b",
}

TAG_COLORS = {
    "新リリース": "ft-release", "AIモデル": "ft-model", "エージェント": "ft-agent",
    "ベンチマーク": "ft-bench", "オープンソース": "ft-oss", "規制・政策": "ft-policy",
    "資金調達": "ft-funding", "製品": "ft-biz", "フレームワーク": "ft-frame",
    "プラットフォーム": "ft-data", "脆弱性": "ft-sec", "情報漏洩": "ft-sec",
    "ゼロデイ": "ft-sec", "パッチ": "ft-sec", "ランサムウェア": "ft-sec",
    "チップ": "ft-hw", "GPU": "ft-hw", "ニュース": "ft-biz",
    "ツール": "ft-frame", "インフラ": "ft-cloud", "アップデート": "ft-release",
    "データ連携": "ft-data", "分析": "ft-data", "レイクハウス": "ft-data",
    "IPO": "ft-funding", "M&A": "ft-biz", "ユニコーン": "ft-funding",
    "レイオフ": "ft-sec", "Kubernetes": "ft-cloud", "サーバーレス": "ft-cloud",
    "料金": "ft-biz", "製造": "ft-hw",
}


def esc(text):
    if not text:
        return ""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def get_color(source):
    return AVATAR_COLORS.get(source, AVATAR_COLORS["default"])


def get_impact_class(impact):
    if impact >= 85:
        return "imp-crit"
    elif impact >= 65:
        return "imp-high"
    else:
        return "imp-med"


def build_glossary(glossary):
    if not glossary:
        return ""
    items = []
    for g in glossary[:4]:
        term = esc(g.get("term", ""))
        defn = esc(g.get("definition", ""))
        items.append(f'<span class="gl-item">{term}<span class="gl-tip">{defn}</span></span>')
    return f'<div class="glossary">{"".join(items)}</div>'


def build_tags(tags):
    if not tags:
        return ""
    items = []
    for t in tags[:3]:
        css = TAG_COLORS.get(t, "ft-biz")
        items.append(f'<span class="ft {css}">{esc(t)}</span>')
    return f'<div class="fi-tags">{"".join(items)}</div>'


def build_reactions(reactions):
    if not reactions:
        return ""
    items = []
    for r in reactions[:3]:
        user = esc(r.get("user", ""))
        text = esc(r.get("text", ""))
        pf = r.get("platform", "HN")
        pf_class = "rx-hn" if pf == "HN" else "rx-reddit" if pf == "Reddit" else "rx-x"
        items.append(
            f'<div class="rx"><span class="rx-platform {pf_class}">{pf}</span>'
            f'<span class="rx-user">{user}:</span> {text}</div>'
        )
    return (
        f'<div class="reactions">'
        f'<div class="rx-title">\U0001f4ac \u958b\u767a\u8005\u305f\u3061\u306e\u53cd\u5fdc</div>'
        f'{"".join(items)}</div>'
    )


def build_article(article):
    title = esc(article.get("title", ""))
    source = esc(article.get("source", ""))
    icon = esc(article.get("icon", "?"))
    published = article.get("published", "")
    url = article.get("url", "#")
    easy = esc(article.get("easy", ""))
    why = esc(article.get("why", ""))
    glossary = article.get("glossary", [])
    tags = article.get("tags", [])
    reactions = article.get("reactions", [])
    impact = article.get("impact", 50)
    color = get_color(article.get("source", ""))
    score = article.get("score", 0)
    comments = article.get("comments", 0)

    score_html = ""
    if score:
        score_html += f' \u00b7 <span style="color:var(--org)">\u25b2{score}</span>'
    if comments:
        score_html += f' \u00b7 \U0001f4ac{comments}'

    source_html = ""
    if url and url != "#":
        source_html = f'<div class="fi-source">\U0001f4ce <a href="{url}" target="_blank" rel="noopener">{source}</a>{score_html}</div>'

    easy_html = ""
    if easy:
        easy_html = f'<div class="fi-easy"><strong>\u3056\u3063\u304f\u308a\u8a00\u3046\u3068\uff1a</strong>{easy}</div>'

    why_html = ""
    if why:
        why_html = f'<div class="fi-why">{why}</div>'

    impact_class = get_impact_class(impact)

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
    {build_glossary(glossary)}
    {build_tags(tags)}
    {source_html}
    {build_reactions(reactions)}
    <div class="imp"><span class="imp-l">\u91cd\u8981\u5ea6</span><div class="imp-bar"><div class="imp-f {impact_class}" style="width:{impact}%"></div></div></div>
  </div>
</div>"""


def build_breaking(breaking_list):
    if not breaking_list:
        return ""
    items = []
    level_map = {"red": ("bb-red", "brk-red", "\u901f\u5831"), "orange": ("bb-org", "brk-orange", "\u6ce8\u76ee"), "blue": ("bb-blue", "brk-blue", "\u6ce8\u76ee")}
    for b in breaking_list[:2]:
        lvl = b.get("level", "blue")
        bb, brk, label = level_map.get(lvl, level_map["blue"])
        text = esc(b.get("text", ""))
        items.append(f'<div class="brk {brk}"><span class="bb {bb}">{label}</span><span class="brk-text">{text}</span></div>')
    return "".join(items)


def build_hn_sidebar(hn_top):
    items = []
    for i, a in enumerate(hn_top[:10], 1):
        title = esc(a.get("title", ""))
        url = a.get("url", "#")
        score = a.get("score", 0)
        items.append(
            f'<div class="hn-item"><span class="hn-rank">{i}</span>'
            f'<div class="hn-content"><a href="{url}" target="_blank" rel="noopener" class="hn-title">{title}</a>'
            f'<span class="hn-score">\u25b2{score}</span></div></div>'
        )
    return "\n".join(items)


def generate_html():
    news_path = DATA_DIR / "news.json"
    if not news_path.exists():
        print("Error: data/news.json not found.")
        return

    with open(news_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    updated_at = data.get("updated_at", "\u4e0d\u660e")
    tabs_data = data.get("tabs", {})
    hn_top = data.get("hn_top", [])
    breaking = data.get("breaking", [])

    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template = f.read()

    # タブボタン
    tab_buttons = []
    for i, tab in enumerate(TABS):
        active = " active" if i == 0 else ""
        tab_buttons.append(
            f'<button class="tab-btn{active}" data-tab="{tab["id"]}">{tab["emoji"]} {tab["label"]}</button>'
        )
    tab_buttons_html = "\n".join(tab_buttons)

    # タブコンテンツ
    tab_contents = []
    for i, tab in enumerate(TABS):
        active = " active" if i == 0 else ""
        articles = tabs_data.get(tab["id"], [])

        # 速報は最初のタブだけ
        breaking_html = build_breaking(breaking) if i == 0 else ""

        articles_html = "\n".join(build_article(a) for a in articles)
        if not articles:
            articles_html = '<div class="fi" style="text-align:center;padding:40px;color:var(--mut)">\u3053\u306e\u30ab\u30c6\u30b4\u30ea\u306e\u8a18\u4e8b\u306f\u307e\u3060\u3042\u308a\u307e\u305b\u3093</div>'

        hn_sidebar = build_hn_sidebar(hn_top)

        tab_contents.append(f"""<div class="tab-content{active}" id="tab-{tab['id']}">
  <div class="feed">
    {breaking_html}
    {articles_html}
  </div>
  <div class="sidebar">
    <div class="sb-card">
      <div class="sb-title">\U0001f525 Hacker News \u30c8\u30c3\u30d7 10</div>
      {hn_sidebar}
    </div>
    <div class="sb-card">
      <div class="sb-title">\u2139\ufe0f \u3053\u306e\u30c0\u30c3\u30b7\u30e5\u30dc\u30fc\u30c9\u306b\u3064\u3044\u3066</div>
      <div style="font-size:.78rem;color:var(--dim);line-height:1.6">
        \u6bce\u671d7\u6642\u306b\u81ea\u52d5\u66f4\u65b0\u3002<br>
        RSS / HN / Reddit\u304b\u3089\u30cb\u30e5\u30fc\u30b9\u3092\u53d6\u5f97\u3057\u3001<br>
        Gemini AI\u304c\u65e5\u672c\u8a9e\u3067\u3084\u3055\u3057\u304f\u89e3\u8aac\u3002<br>
        \u7528\u8a9e\u306b\u30de\u30a6\u30b9\u3092\u4e57\u305b\u308b\u3068\u89e3\u8aac\u304c\u898b\u308c\u307e\u3059\u3002
      </div>
    </div>
  </div>
</div>""")
    tab_contents_html = "\n".join(tab_contents)

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
