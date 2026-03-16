#!/usr/bin/env python3
"""
Tech Pulse v4 - HTML生成スクリプト
TOPページ追加、サイドバー簡素化、未来的デザイン
"""

import json
import re
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

JST = timezone(timedelta(hours=9))
DATA_DIR = Path("data")
TEMPLATE_PATH = Path("templates/dashboard.html")
OUTPUT_PATH = Path("index.html")

CATEGORY_TABS = [
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
    "The Verge AI": "#5200FF", "The Verge Tech": "#5200FF",
    "VentureBeat AI": "#c00", "VentureBeat Deals": "#c00",
    "Ars Technica AI": "#ff4e00", "Ars Hardware": "#ff4e00",
    "WIRED AI": "#000", "MIT Tech Review": "#9B1B30",
    "InfoQ": "#007dc3", "InfoQ Cloud": "#007dc3",
    "The New Stack": "#1a73e8", "DevClass": "#333",
    "Dark Reading": "#000", "SecurityWeek": "#003366",
    "TechCrunch HW": "#0a0", "TechCrunch Startups": "#0a0",
    "INTERNET Watch": "#369", "PC Watch": "#369",
    "ITmedia AI+": "#e60012", "ITmedia News": "#e60012", "ITmedia エンタープライズ": "#e60012",
    "Publickey": "#1a73e8", "GIGAZINE": "#333",
    "CNET Japan": "#d00", "ZDNet Japan": "#c00",
    "クラウドWatch": "#369", "BRIDGE": "#ff6347",
    "Zenn トレンド": "#3ea8ff", "Qiita 人気": "#55c500",
    "Data Eng Weekly": "#333", "Spotify Engineering": "#1DB954",
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

STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "up", "about", "into", "over", "after",
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "will", "would", "could", "should", "may", "might",
    "it", "its", "this", "that", "these", "those", "what", "which", "who",
    "how", "why", "new", "says", "can", "get", "now", "just", "more", "all",
    "your", "not", "than", "other", "also", "like", "out", "most", "first",
    "use", "using", "used", "make", "makes", "made", "blog", "post",
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
        f'<div class="rx-title">\U0001f4ac 開発者たちの反応</div>'
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
    hotness = article.get("hotness", 0)

    score_html = ""
    if score:
        score_html += f' · <span style="color:var(--org)">▲{score}</span>'
    if comments:
        score_html += f' · 💬{comments}'

    # ホットネスバッジ
    hot_badge = ""
    if hotness >= 70:
        hot_badge = f'<span class="hot-badge hot-fire">🔥 {hotness:.0f}</span>'
    elif hotness >= 50:
        hot_badge = f'<span class="hot-badge hot-warm">🌡 {hotness:.0f}</span>'

    source_html = ""
    if url and url != "#":
        source_html = f'<div class="fi-source">📎 <a href="{url}" target="_blank" rel="noopener">{source}</a>{score_html}</div>'

    # 「解説」ラベル（旧: ざっくり言うと）
    easy_html = ""
    if easy:
        easy_html = f'<div class="fi-easy"><strong>解説：</strong>{easy}</div>'

    # 「重要ポイント」ラベル（旧: このニュースは重要です）
    why_html = ""
    if why:
        why_html = f'<div class="fi-why">💎 <strong>重要ポイント：</strong>{why}</div>'

    impact_class = get_impact_class(impact)

    return f"""<div class="fi">
  <div class="fi-head">
    <div class="fi-av" style="background:{color}">{icon}</div>
    <div><div class="fi-src">{source}</div></div>
    {hot_badge}
    <div class="fi-time">{published}</div>
  </div>
  <div class="fi-body">
    <div class="fi-title"><a href="{url}" target="_blank" rel="noopener">{title}</a></div>
    {easy_html}
    {why_html}
    {build_glossary(glossary)}
    {build_tags(tags)}
    {source_html}
    {build_reactions(reactions)}
    <div class="imp"><span class="imp-l">重要度</span><div class="imp-bar"><div class="imp-f {impact_class}" style="width:{impact}%"></div></div></div>
  </div>
</div>"""


def extract_hot_words(all_articles):
    """全記事のタイトルからホットワードを抽出"""
    word_count = Counter()
    for a in all_articles:
        title = a.get("title", "")
        en_words = re.findall(r'[A-Z][a-zA-Z]{2,}|[A-Z]{2,}', title)
        for w in en_words:
            wl = w.lower()
            if wl not in STOP_WORDS and len(wl) >= 3:
                word_count[w] += 1
        ja_words = re.findall(r'[\u30A0-\u30FF]{3,}', title)
        for w in ja_words:
            word_count[w] += 1
    hot_words = [(word, count) for word, count in word_count.most_common(20) if count >= 2]
    return hot_words[:12]


def build_hotwords_html(hot_words):
    """ホットワードのHTML生成"""
    if not hot_words:
        return '<div class="hw-empty">データ収集中...</div>'
    items = []
    max_count = hot_words[0][1] if hot_words else 1
    for word, count in hot_words:
        ratio = count / max_count
        if ratio >= 0.8:
            size_class = "hw-xl"
        elif ratio >= 0.5:
            size_class = "hw-lg"
        elif ratio >= 0.3:
            size_class = "hw-md"
        else:
            size_class = "hw-sm"
        items.append(f'<span class="hw {size_class}" title="{count}回出現">{esc(word)}</span>')
    return "".join(items)


def build_top_page(all_articles, hot_words):
    """TOPページ: 全ニュースのダイジェスト（ぱっと見で概要把握）"""
    hotwords_html = build_hotwords_html(hot_words)

    # ホットネス上位15件を表示
    sorted_arts = sorted(all_articles, key=lambda a: a.get("hotness", 0), reverse=True)
    top_arts = sorted_arts[:15]

    tab_map = {t["id"]: f'{t["emoji"]} {t["label"]}' for t in CATEGORY_TABS}

    cards = []
    for a in top_arts:
        title = esc(a.get("title", ""))
        source = esc(a.get("source", ""))
        url = a.get("url", "#")
        easy = esc(a.get("easy", ""))
        if len(easy) > 120:
            easy = easy[:117] + "..."
        hotness = a.get("hotness", 0)
        color = get_color(a.get("source", ""))
        published = a.get("published", "")[:10]
        tab_id = a.get("_tab", "")
        tab_label = tab_map.get(tab_id, "")

        hot_class = "top-fire" if hotness >= 70 else "top-warm" if hotness >= 50 else "top-normal"
        hot_icon = "\U0001f525" if hotness >= 70 else "\U0001f321" if hotness >= 50 else "\U0001f4f0"

        cards.append(
            f'<a href="{url}" target="_blank" rel="noopener" class="top-card">'
            f'<div class="top-accent" style="background:{color}"></div>'
            f'<div class="top-body">'
            f'<div class="top-head">'
            f'<span class="top-cat">{tab_label}</span>'
            f'<span class="top-hot {hot_class}">{hot_icon}{hotness:.0f}</span>'
            f'</div>'
            f'<div class="top-title">{title}</div>'
            f'<div class="top-summary">{easy}</div>'
            f'<div class="top-meta">'
            f'<span class="top-source" style="color:{color}">{source}</span>'
            f'<span class="top-time">{published}</span>'
            f'</div>'
            f'</div></a>'
        )

    return (
        f'<div class="top-page">'
        f'<div class="top-hw-section">'
        f'<div class="top-hw-label">Today\'s Hot Words</div>'
        f'<div class="hw-cloud">{hotwords_html}</div>'
        f'</div>'
        f'<div class="top-grid">{"".join(cards)}</div>'
        f'</div>'
    )


def build_ai_tools_page():
    """AI Toolsタブ: カテゴリ別ツールカード"""
    config_path = DATA_DIR / "ai-tools-config.json"
    trends_path = DATA_DIR / "ai-tools-trends.json"

    if not config_path.exists():
        return '<div class="ait-page"><div style="text-align:center;padding:40px;color:var(--mut)">AI Toolsの設定ファイルがありません</div></div>'

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    # トレンドデータ読み込み（初回実行時は存在しない場合あり）
    trends_map = {}
    cat_trends = {}
    generated_at = ""
    if trends_path.exists():
        with open(trends_path, "r", encoding="utf-8") as f:
            trends = json.load(f)
        generated_at = trends.get("generated_at", "")
        for cat in trends.get("categories", []):
            cat_id = cat.get("id", "")
            cat_trends[cat_id] = cat.get("trend_summary", "")
            trends_map[cat_id] = {}
            for tool in cat.get("tools", []):
                trends_map[cat_id][tool["name"]] = tool

    sections = []
    for cat in config["categories"]:
        cat_id = cat["id"]
        cat_name = esc(cat["name"])
        cat_emoji = cat.get("emoji", "")
        cat_color = cat.get("color", "var(--ac)")
        summary = esc(cat_trends.get(cat_id, ""))

        summary_html = ""
        if summary:
            summary_html = f'<div class="ait-cat-trend">{summary}</div>'

        cards = []
        for tool in cat["tools"]:
            t_name = tool["name"]
            t_url = tool.get("url", "#")
            t_icon = esc(tool.get("icon", "?"))

            t_data = trends_map.get(cat_id, {}).get(t_name, {})
            t_trend = esc(t_data.get("trend", "トレンド情報を取得中..."))
            t_momentum = t_data.get("momentum", "stable")
            t_highlights = t_data.get("highlights", [])

            momentum_class = f"ait-{t_momentum}" if t_momentum in ("up", "stable", "down") else "ait-stable"
            momentum_label = {"up": "\U0001f4c8 勢いあり", "stable": "\u27a1\ufe0f 安定", "down": "\U0001f4c9 低調"}.get(t_momentum, "\u27a1\ufe0f 安定")

            hl_html = ""
            if t_highlights:
                hl_items = "".join(f'<span class="ait-hl">{esc(h)}</span>' for h in t_highlights[:3])
                hl_html = f'<div class="ait-highlights">{hl_items}</div>'

            cards.append(
                f'<div class="ait-card">'
                f'<div class="ait-card-head">'
                f'<div class="ait-av" style="background:{cat_color}">{t_icon}</div>'
                f'<div class="ait-name"><a href="{t_url}" target="_blank" rel="noopener">{esc(t_name)}</a></div>'
                f'<span class="ait-momentum {momentum_class}">{momentum_label}</span>'
                f'</div>'
                f'<div class="ait-trend">{t_trend}</div>'
                f'{hl_html}'
                f'</div>'
            )

        sections.append(
            f'<div class="ait-section">'
            f'<div class="ait-cat-head">'
            f'<span class="ait-cat-emoji">{cat_emoji}</span>'
            f'<span class="ait-cat-name">{cat_name}</span>'
            f'</div>'
            f'{summary_html}'
            f'<div class="ait-grid">{"".join(cards)}</div>'
            f'</div>'
        )

    updated_html = ""
    if generated_at:
        updated_html = f'<div class="ait-updated">トレンド更新: {esc(generated_at)}</div>'

    return f'<div class="ait-page">{"".join(sections)}{updated_html}</div>'


def generate_html():
    news_path = DATA_DIR / "news.json"
    if not news_path.exists():
        print("Error: data/news.json not found.")
        return

    with open(news_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    updated_at = data.get("updated_at", "不明")
    tabs_data = data.get("tabs", {})

    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template = f.read()

    # 全記事を集める（タブ情報付き）
    all_articles = []
    for tab_id, tab_articles in tabs_data.items():
        for a in tab_articles:
            a["_tab"] = tab_id
            all_articles.append(a)

    hot_words = extract_hot_words(all_articles)
    hotwords_html = build_hotwords_html(hot_words)

    # タブボタン（TOPが最初・デフォルトactive）
    tab_buttons = ['<button class="tab-btn active" data-tab="top">\U0001f3e0 Top</button>']
    for tab in CATEGORY_TABS:
        tab_buttons.append(
            f'<button class="tab-btn" data-tab="{tab["id"]}">{tab["emoji"]} {tab["label"]}</button>'
        )
    tab_buttons.append('<button class="tab-btn" data-tab="aitools">\U0001f9f0 AI Tools</button>')
    tab_buttons_html = "\n".join(tab_buttons)

    # TOPページ
    top_html = build_top_page(all_articles, hot_words)
    tab_contents = [f'<div class="tab-content active" id="tab-top">{top_html}</div>']

    # カテゴリタブ
    for tab in CATEGORY_TABS:
        articles = tabs_data.get(tab["id"], [])
        articles_html = "\n".join(build_article(a) for a in articles)
        if not articles:
            articles_html = '<div class="fi" style="text-align:center;padding:40px;color:var(--mut)">このカテゴリの記事はまだありません</div>'

        tab_contents.append(f"""<div class="tab-content" id="tab-{tab['id']}">
  <div class="feed">
    {articles_html}
  </div>
  <div class="sidebar">
    <div class="sb-card">
      <div class="sb-title">\U0001f524 今日のホットワード</div>
      <div class="hw-cloud">
        {hotwords_html}
      </div>
    </div>
  </div>
</div>""")

    # AI Toolsタブ
    ai_tools_html = build_ai_tools_page()
    tab_contents.append(f'<div class="tab-content" id="tab-aitools">{ai_tools_html}</div>')

    tab_contents_html = "\n".join(tab_contents)

    html = template
    html = html.replace("{{UPDATED_AT}}", updated_at)
    html = html.replace("{{TAB_BUTTONS}}", tab_buttons_html)
    html = html.replace("{{TAB_CONTENTS}}", tab_contents_html)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Dashboard generated: {OUTPUT_PATH}")
    print(f"Updated at: {updated_at}")
    print(f"Hot words: {len(hot_words)} | Total articles: {len(all_articles)}")
    print(f"Top page: {min(15, len(all_articles))} articles shown")


if __name__ == "__main__":
    generate_html()
