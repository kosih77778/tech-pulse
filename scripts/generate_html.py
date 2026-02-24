#!/usr/bin/env python3
"""
Tech Pulse v3 - HTML生成スクリプト
サイドバー: ホットワード + 速報タイムライン
HNランキング廃止、ホットネス対応
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

# ホットワード抽出時に無視するストップワード
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

    easy_html = ""
    if easy:
        easy_html = f'<div class="fi-easy"><strong>ざっくり言うと：</strong>{easy}</div>'

    why_html = ""
    if why:
        why_html = f'<div class="fi-why">{why}</div>'

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


def build_breaking(breaking_list):
    if not breaking_list:
        return ""
    items = []
    level_map = {"red": ("bb-red", "brk-red", "速報"), "orange": ("bb-org", "brk-orange", "注目"), "blue": ("bb-blue", "brk-blue", "注目")}
    for b in breaking_list[:3]:
        lvl = b.get("level", "blue")
        bb, brk, label = level_map.get(lvl, level_map["blue"])
        text = esc(b.get("text", ""))
        items.append(f'<div class="brk {brk}"><span class="bb {bb}">{label}</span><span class="brk-text">{text}</span></div>')
    return "".join(items)


def extract_hot_words(all_articles):
    """全記事のタイトルからホットワードを抽出"""
    word_count = Counter()
    for a in all_articles:
        title = a.get("title", "")
        # 英語のキーワード（大文字始まり or 全大文字）
        en_words = re.findall(r'[A-Z][a-zA-Z]{2,}|[A-Z]{2,}', title)
        for w in en_words:
            wl = w.lower()
            if wl not in STOP_WORDS and len(wl) >= 3:
                word_count[w] += 1
        # 日本語のキーワード（カタカナ語）
        ja_words = re.findall(r'[\u30A0-\u30FF]{3,}', title)
        for w in ja_words:
            word_count[w] += 1

    # 2回以上出現したワードのみ
    hot_words = [(word, count) for word, count in word_count.most_common(20) if count >= 2]
    return hot_words[:12]


def build_hotwords_html(hot_words):
    """ホットワードのHTML生成"""
    if not hot_words:
        return '<div class="hw-empty">データ収集中...</div>'
    items = []
    max_count = hot_words[0][1] if hot_words else 1
    for word, count in hot_words:
        # 出現回数に応じてサイズを変える
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


def build_breaking_timeline(all_articles):
    """ホットネス上位の記事をタイムラインで表示（タブ横断）"""
    # ホットネス上位の記事を抽出
    hot_articles = sorted(all_articles, key=lambda a: a.get("hotness", 0), reverse=True)
    top_articles = hot_articles[:8]

    if not top_articles:
        return '<div class="hw-empty">データ収集中...</div>'

    items = []
    # タブIDから日本語ラベルへの変換
    tab_labels = {t["id"]: t["emoji"] + " " + t["label"] for t in TABS}

    for a in top_articles:
        title = esc(a.get("title", ""))[:60]
        url = a.get("url", "#")
        source = esc(a.get("source", ""))
        hotness = a.get("hotness", 0)
        color = get_color(a.get("source", ""))
        published = a.get("published", "")[:10]

        # ホットネスに応じた色
        if hotness >= 70:
            dot_class = "tl-dot-fire"
        elif hotness >= 50:
            dot_class = "tl-dot-warm"
        else:
            dot_class = "tl-dot-normal"

        reasons = a.get("hotness_reasons", [])
        reason_text = esc(", ".join(reasons[:2])) if reasons else ""

        items.append(
            f'<div class="tl-item">'
            f'<div class="tl-dot {dot_class}"></div>'
            f'<div class="tl-content">'
            f'<a href="{url}" target="_blank" rel="noopener" class="tl-title">{title}</a>'
            f'<div class="tl-meta">'
            f'<span class="tl-source" style="color:{color}">{source}</span>'
            f'<span class="tl-hot">🔥{hotness:.0f}</span>'
            f'</div>'
            f'{"<div class=tl-reason>" + reason_text + "</div>" if reason_text else ""}'
            f'</div></div>'
        )
    return "\n".join(items)


def generate_html():
    news_path = DATA_DIR / "news.json"
    if not news_path.exists():
        print("Error: data/news.json not found.")
        return

    with open(news_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    updated_at = data.get("updated_at", "不明")
    tabs_data = data.get("tabs", {})
    breaking = data.get("breaking", [])

    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template = f.read()

    # 全記事を集めてホットワード＆タイムライン生成
    all_articles = []
    for tab_articles in tabs_data.values():
        all_articles.extend(tab_articles)

    hot_words = extract_hot_words(all_articles)
    hotwords_html = build_hotwords_html(hot_words)
    timeline_html = build_breaking_timeline(all_articles)

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
            articles_html = '<div class="fi" style="text-align:center;padding:40px;color:var(--mut)">このカテゴリの記事はまだありません</div>'

        tab_contents.append(f"""<div class="tab-content{active}" id="tab-{tab['id']}">
  <div class="feed">
    {breaking_html}
    {articles_html}
  </div>
  <div class="sidebar">
    <div class="sb-card">
      <div class="sb-title">🔤 今日のホットワード</div>
      <div class="hw-cloud">
        {hotwords_html}
      </div>
    </div>
    <div class="sb-card">
      <div class="sb-title">🔥 注目ニュース（全タブ横断）</div>
      <div class="timeline">
        {timeline_html}
      </div>
    </div>
    <div class="sb-card">
      <div class="sb-title">ℹ️ このダッシュボードについて</div>
      <div style="font-size:.78rem;color:var(--dim);line-height:1.6">
        毎朝7時に自動更新。<br>
        RSS / HN / はてブからニュースを取得し、<br>
        ホットネス判定で注目記事を厳選。<br>
        Groq AI が日本語でやさしく解説。<br>
        用語にマウスを乗せると解説が見れます。
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
    print(f"Hot words: {len(hot_words)} | Timeline: {min(8, len(all_articles))} articles")


if __name__ == "__main__":
    generate_html()
