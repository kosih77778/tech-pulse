#!/usr/bin/env python3
"""
Tech Pulse v5 - ニュース取得スクリプト（Groq版・ソース強化＋日本語メディア）
Hacker News全タブ振り分け + 海外速報メディア + 日本語メディア + 企業ブログ
Groq API (Llama 3.3 70B) でやさしい日本語解説を生成する
"""

import json
import os
import time
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
import feedparser

# ─── 設定 ───────────────────────────────────────────────
JST = timezone(timedelta(hours=9))
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"

MAX_PER_TAB = 8

# ─── RSSフィード定義（タブ別） ───────────────────────────
# ★ 速報系ニュースメディア + 企業ブログのバランス型
FEEDS = {
    "ai": [
        # --- 海外速報系メディア ---
        {"url": "https://techcrunch.com/category/artificial-intelligence/feed/", "name": "TechCrunch AI", "icon": "TC", "priority": 1},
        {"url": "https://venturebeat.com/category/ai/feed/", "name": "VentureBeat AI", "icon": "VB", "priority": 1},
        {"url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml", "name": "The Verge AI", "icon": "TV", "priority": 1},
        {"url": "https://arstechnica.com/tag/artificial-intelligence/feed/", "name": "Ars Technica AI", "icon": "AT", "priority": 1},
        {"url": "https://www.wired.com/feed/tag/ai/latest/rss", "name": "WIRED AI", "icon": "WD", "priority": 2},
        {"url": "https://www.technologyreview.com/feed/", "name": "MIT Tech Review", "icon": "MT", "priority": 2},
        # --- 企業ブログ ---
        {"url": "https://openai.com/blog/rss.xml", "name": "OpenAI Blog", "icon": "O", "priority": 2},
        {"url": "https://blog.google/technology/ai/rss/", "name": "Google AI Blog", "icon": "G", "priority": 2},
        {"url": "https://huggingface.co/blog/feed.xml", "name": "Hugging Face", "icon": "HF", "priority": 3},
        # --- 日本語メディア ---
        {"url": "https://rss.itmedia.co.jp/rss/2.0/aiplus.xml", "name": "ITmedia AI+", "icon": "JP", "priority": 1, "lang": "ja"},
        {"url": "https://gigazine.net/news/rss_2.0/", "name": "GIGAZINE", "icon": "JP", "priority": 2, "lang": "ja"},
        {"url": "https://japan.cnet.com/rss/index.rdf", "name": "CNET Japan", "icon": "JP", "priority": 2, "lang": "ja"},
    ],
    "devtools": [
        # --- 海外速報系 ---
        {"url": "https://www.infoq.com/feed/", "name": "InfoQ", "icon": "IQ", "priority": 1},
        {"url": "https://thenewstack.io/feed/", "name": "The New Stack", "icon": "NS", "priority": 1},
        {"url": "https://devclass.com/feed/", "name": "DevClass", "icon": "DC", "priority": 2},
        # --- 公式ブログ ---
        {"url": "https://github.blog/feed/", "name": "GitHub Blog", "icon": "GH", "priority": 1},
        {"url": "https://devblogs.microsoft.com/typescript/feed/", "name": "TypeScript Blog", "icon": "TS", "priority": 2},
        {"url": "https://blog.rust-lang.org/feed.xml", "name": "Rust Blog", "icon": "Rs", "priority": 3},
        {"url": "https://nodejs.org/en/feed/blog.xml", "name": "Node.js Blog", "icon": "NJ", "priority": 3},
        # --- 日本語メディア ---
        {"url": "https://www.publickey1.jp/atom.xml", "name": "Publickey", "icon": "JP", "priority": 1, "lang": "ja"},
        {"url": "https://rss.itmedia.co.jp/rss/2.0/news_bursts.xml", "name": "ITmedia News", "icon": "JP", "priority": 2, "lang": "ja"},
        {"url": "https://japan.zdnet.com/rss/index.rdf", "name": "ZDNet Japan", "icon": "JP", "priority": 2, "lang": "ja"},
    ],
    "data_dx": [
        # --- 海外速報系 ---
        {"url": "https://thenewstack.io/feed/", "name": "The New Stack", "icon": "NS", "priority": 1},
        {"url": "https://www.dataengineeringweekly.com/feed", "name": "Data Eng Weekly", "icon": "DE", "priority": 1},
        # --- 公式ブログ ---
        {"url": "https://blog.getdbt.com/rss/", "name": "dbt Blog", "icon": "dbt", "priority": 2},
        {"url": "https://www.databricks.com/feed", "name": "Databricks", "icon": "DB", "priority": 2},
        {"url": "https://cloud.google.com/blog/products/data-analytics/rss", "name": "GCP Data", "icon": "G", "priority": 2},
        {"url": "https://aws.amazon.com/blogs/big-data/feed/", "name": "AWS Big Data", "icon": "AW", "priority": 3},
        # --- 日本語メディア ---
        {"url": "https://www.publickey1.jp/atom.xml", "name": "Publickey", "icon": "JP", "priority": 1, "lang": "ja"},
        {"url": "https://japan.zdnet.com/rss/index.rdf", "name": "ZDNet Japan", "icon": "JP", "priority": 2, "lang": "ja"},
    ],
    "cloud": [
        # --- 海外速報系 ---
        {"url": "https://www.infoq.com/cloud-computing/rss", "name": "InfoQ Cloud", "icon": "IQ", "priority": 1},
        {"url": "https://thenewstack.io/feed/", "name": "The New Stack", "icon": "NS", "priority": 1},
        # --- 公式ブログ ---
        {"url": "https://aws.amazon.com/blogs/aws/feed/", "name": "AWS Blog", "icon": "AW", "priority": 1},
        {"url": "https://cloud.google.com/blog/rss", "name": "GCP Blog", "icon": "G", "priority": 2},
        {"url": "https://azure.microsoft.com/en-us/blog/feed/", "name": "Azure Blog", "icon": "AZ", "priority": 2},
        {"url": "https://blog.cloudflare.com/rss/", "name": "Cloudflare Blog", "icon": "CF", "priority": 2},
        # --- 日本語メディア ---
        {"url": "https://www.publickey1.jp/atom.xml", "name": "Publickey", "icon": "JP", "priority": 1, "lang": "ja"},
        {"url": "https://cloud.watch.impress.co.jp/data/rss/1.0/cw/feed.rdf", "name": "クラウドWatch", "icon": "JP", "priority": 1, "lang": "ja"},
    ],
    "security": [
        # --- 海外速報系（セキュリティは速報が命） ---
        {"url": "https://krebsonsecurity.com/feed/", "name": "Krebs on Security", "icon": "KS", "priority": 1},
        {"url": "https://www.bleepingcomputer.com/feed/", "name": "BleepingComputer", "icon": "BC", "priority": 1},
        {"url": "https://thehackernews.com/feeds/posts/default", "name": "The Hacker News", "icon": "HN", "priority": 1},
        {"url": "https://www.darkreading.com/rss.xml", "name": "Dark Reading", "icon": "DR", "priority": 1},
        {"url": "https://www.securityweek.com/feed/", "name": "SecurityWeek", "icon": "SW", "priority": 1},
        {"url": "https://blog.cloudflare.com/rss/", "name": "Cloudflare Blog", "icon": "CF", "priority": 2},
        # --- 日本語メディア ---
        {"url": "https://internet.watch.impress.co.jp/data/rss/1.0/iw/feed.rdf", "name": "INTERNET Watch", "icon": "JP", "priority": 1, "lang": "ja"},
        {"url": "https://rss.itmedia.co.jp/rss/2.0/enterprise.xml", "name": "ITmedia エンタープライズ", "icon": "JP", "priority": 2, "lang": "ja"},
    ],
    "hardware": [
        # --- 海外速報系 ---
        {"url": "https://www.tomshardware.com/feeds/all", "name": "Tom's Hardware", "icon": "TH", "priority": 1},
        {"url": "https://arstechnica.com/tag/hardware/feed/", "name": "Ars Hardware", "icon": "AT", "priority": 1},
        {"url": "https://www.theverge.com/rss/tech/index.xml", "name": "The Verge Tech", "icon": "TV", "priority": 1},
        {"url": "https://techcrunch.com/category/hardware/feed/", "name": "TechCrunch HW", "icon": "TC", "priority": 2},
        {"url": "https://semianalysis.com/feed/", "name": "SemiAnalysis", "icon": "SA", "priority": 2},
        # --- 日本語メディア ---
        {"url": "https://pc.watch.impress.co.jp/data/rss/1.0/pcw/feed.rdf", "name": "PC Watch", "icon": "JP", "priority": 1, "lang": "ja"},
        {"url": "https://gigazine.net/news/rss_2.0/", "name": "GIGAZINE", "icon": "JP", "priority": 2, "lang": "ja"},
    ],
    "funding": [
        # --- 海外速報系 ---
        {"url": "https://techcrunch.com/category/venture/feed/", "name": "TechCrunch VC", "icon": "TC", "priority": 1},
        {"url": "https://news.crunchbase.com/feed/", "name": "Crunchbase News", "icon": "CB", "priority": 1},
        {"url": "https://venturebeat.com/category/deals/feed/", "name": "VentureBeat Deals", "icon": "VB", "priority": 1},
        {"url": "https://techcrunch.com/category/startups/feed/", "name": "TechCrunch Startups", "icon": "TC", "priority": 2},
        # --- 日本語メディア ---
        {"url": "https://thebridge.jp/feed", "name": "BRIDGE", "icon": "JP", "priority": 1, "lang": "ja"},
        {"url": "https://japan.cnet.com/rss/index.rdf", "name": "CNET Japan", "icon": "JP", "priority": 2, "lang": "ja"},
    ],
}

# ─── HN記事のタブ振り分けキーワード ──────────────────────
HN_TAB_KEYWORDS = {
    "ai": ["ai", "llm", "gpt", "claude", "gemini", "model", "neural", "ml", "openai", "anthropic",
           "deepseek", "transformer", "agent", "diffusion", "copilot", "chatbot", "mistral", "llama",
           "stable diffusion", "midjourney", "sora", "rag", "fine-tun", "embedding"],
    "devtools": ["rust", "python", "javascript", "typescript", "go ", "golang", "react", "vue",
                 "github", "vscode", "docker", "compiler", "debugger", "ide", "api", "sdk",
                 "framework", "library", "npm", "cargo", "pip", "git ", "ci/cd", "devops"],
    "data_dx": ["database", "sql", "postgres", "mysql", "redis", "kafka", "spark", "dbt",
                "warehouse", "lakehouse", "etl", "pipeline", "parquet", "arrow", "snowflake",
                "bigquery", "databricks", "analytics", "data eng"],
    "cloud": ["aws", "azure", "gcp", "cloud", "kubernetes", "k8s", "docker", "serverless",
              "lambda", "terraform", "infrastructure", "deploy", "cdn", "cloudflare"],
    "security": ["vulnerability", "cve", "hack", "breach", "malware", "ransomware", "exploit",
                 "zero-day", "0day", "phishing", "backdoor", "encryption", "auth", "password",
                 "security", "privacy", "ddos"],
    "hardware": ["chip", "gpu", "cpu", "nvidia", "amd", "intel", "apple silicon", "arm",
                 "semiconductor", "fab", "tsmc", "memory", "ssd", "hardware", "quantum",
                 "chip", "processor", "tpu"],
    "funding": ["funding", "raised", "series a", "series b", "series c", "ipo", "acquisition",
                "acquired", "valuation", "unicorn", "startup", "venture", "investment", "layoff"],
}

TAG_KEYWORDS = {
    "ai": {"release": "新リリース", "model": "AIモデル", "agent": "エージェント", "benchmark": "ベンチマーク", "oss": "オープンソース", "policy": "規制・政策", "funding": "資金調達", "product": "製品"},
    "devtools": {"release": "新リリース", "framework": "フレームワーク", "oss": "オープンソース", "update": "アップデート", "tool": "ツール"},
    "data_dx": {"release": "新リリース", "platform": "プラットフォーム", "lakehouse": "レイクハウス", "etl": "データ連携", "analytics": "分析"},
    "cloud": {"release": "新リリース", "infra": "インフラ", "k8s": "Kubernetes", "serverless": "サーバーレス", "pricing": "料金"},
    "security": {"vuln": "脆弱性", "breach": "情報漏洩", "patch": "パッチ", "zeroday": "ゼロデイ", "ransomware": "ランサムウェア"},
    "hardware": {"chip": "チップ", "gpu": "GPU", "release": "新リリース", "benchmark": "ベンチマーク", "fab": "製造"},
    "funding": {"series": "資金調達", "ipo": "IPO", "ma": "M&A", "unicorn": "ユニコーン", "layoff": "レイオフ"},
}


# ─── ニュース取得関数 ─────────────────────────────────────

def fetch_rss(feed_info):
    try:
        resp = requests.get(feed_info["url"], timeout=15, headers={"User-Agent": "TechPulse/3.0"})
        feed = feedparser.parse(resp.text)
        articles = []
        now = datetime.now(timezone.utc)
        for entry in feed.entries[:8]:
            published = ""
            pub_time = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                pub_time = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                published = pub_time.strftime("%Y-%m-%d %H:%M")
            elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                pub_time = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
                published = pub_time.strftime("%Y-%m-%d %H:%M")

            # 7日以上古い記事はスキップ
            if pub_time and (now - pub_time).days > 7:
                continue

            summary = ""
            if hasattr(entry, "summary"):
                summary = re.sub(r"<[^>]+>", "", entry.summary)[:800]
            articles.append({
                "title": entry.get("title", "No title"),
                "url": entry.get("link", ""),
                "summary": summary,
                "published": published,
                "source": feed_info["name"],
                "icon": feed_info["icon"],
                "priority": feed_info.get("priority", 3),
                "freshness": (now - pub_time).total_seconds() / 3600 if pub_time else 999,
                "lang": feed_info.get("lang", "en"),
            })
        return articles
    except Exception as e:
        print(f"  [WARN] RSS failed: {feed_info['name']}: {e}")
        return []


def fetch_hn_top(limit=30):
    """HNトップ記事を取得（多めに取得して各タブに振り分ける）"""
    try:
        ids = requests.get("https://hacker-news.firebaseio.com/v0/topstories.json", timeout=10).json()
        articles = []
        for item_id in ids[:limit]:
            try:
                item = requests.get(f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json", timeout=5).json()
                if not item or item.get("type") != "story":
                    continue
                title = item.get("title", "")
                articles.append({
                    "title": title,
                    "url": item.get("url", f"https://news.ycombinator.com/item?id={item_id}"),
                    "score": item.get("score", 0),
                    "comments": item.get("descendants", 0),
                    "hn_id": item_id,
                    "published": datetime.fromtimestamp(item.get("time", 0), tz=timezone.utc).strftime("%Y-%m-%d %H:%M"),
                    "source": "Hacker News",
                    "icon": "HN",
                    "priority": 0,  # HNはスコアで重み付けするので最高優先度
                })
            except Exception:
                continue
        return articles
    except Exception as e:
        print(f"  [WARN] HN failed: {e}")
        return []


def classify_hn_article(title):
    """HN記事のタイトルからどのタブに振り分けるか判定"""
    title_lower = title.lower()
    scores = {}
    for tab, keywords in HN_TAB_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in title_lower)
        if score > 0:
            scores[tab] = score
    if scores:
        return max(scores, key=scores.get)
    return None


def fetch_hn_comments(hn_id, limit=3):
    try:
        item = requests.get(f"https://hacker-news.firebaseio.com/v0/item/{hn_id}.json", timeout=5).json()
        kid_ids = item.get("kids", [])[:limit * 2]
        comments = []
        for kid_id in kid_ids:
            try:
                kid = requests.get(f"https://hacker-news.firebaseio.com/v0/item/{kid_id}.json", timeout=5).json()
                if not kid or kid.get("dead") or kid.get("deleted"):
                    continue
                text = kid.get("text", "")
                text = re.sub(r"<[^>]+>", "", text)[:200]
                if len(text) > 20:
                    comments.append({"user": kid.get("by", "anon"), "text": text, "platform": "HN"})
                if len(comments) >= limit:
                    break
            except Exception:
                continue
        return comments
    except Exception:
        return []


# ─── Groq API 解説生成 ───────────────────────────────────

def call_groq(prompt):
    """Groq APIを呼び出す"""
    try:
        resp = requests.post(
            GROQ_URL,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": GROQ_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.4,
                "max_tokens": 1000,
            },
            timeout=45
        )
        data = resp.json()
        if "choices" in data and len(data["choices"]) > 0:
            return data["choices"][0]["message"]["content"]
        else:
            error_msg = data.get("error", {}).get("message", str(data)[:200])
            print(f"    [API Error] {error_msg}")
            return None
    except Exception as e:
        print(f"    [WARN] Groq call failed: {e}")
        return None


def generate_rich_explanation(title, summary, tab_id, is_japanese=False):
    if not GROQ_API_KEY:
        return _fallback(title)

    available_tags = TAG_KEYWORDS.get(tab_id, TAG_KEYWORDS["ai"])
    tags_str = ", ".join([f'"{k}"' for k in available_tags.keys()])

    if is_japanese:
        lang_hint = "この記事は日本語の記事です。タイトルと内容をそのまま活かしつつ、わかりやすく解説してください。"
    else:
        lang_hint = "この記事は英語の記事です。日本語で詳しく解説してください。英語のタイトルも日本語で説明に含めてください。"

    prompt = f"""あなたはテック業界のジャーナリストです。以下のニュースを解説してください。
{lang_hint}

タイトル: {title}
内容: {summary[:600]}
カテゴリ: {tab_id}

必ず以下のJSON形式だけを返してください（マークダウンのコードブロック不要、JSON以外の文字を含めないで）:
{{
  "easy": "専門用語を使わず中学生にもわかるように4-6文で詳しく説明。具体的な数字や比較を入れる。ドル表記は円換算も併記（例：3億ドル（約450億円））。",
  "why": "このニュースが重要な理由を2文で。業界への影響や今後の展望も含めて。",
  "glossary": [
    {{"term": "専門用語1", "definition": "その用語のやさしい説明を50文字以上で"}},
    {{"term": "専門用語2", "definition": "同上"}},
    {{"term": "専門用語3", "definition": "同上"}}
  ],
  "tags": ["該当するものを2-3個: {tags_str}"],
  "impact": 50
}}

impactは1-100の数値（90以上=業界を変える大ニュース、70-89=注目、50-69=一般、50未満=小ネタ）。
glossaryは記事の専門用語を3個含めてください。"""

    text = call_groq(prompt)
    if not text:
        return _fallback(title)

    try:
        text = re.sub(r"```json\s*", "", text)
        text = re.sub(r"```\s*$", "", text)
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            result = json.loads(json_match.group())
            available = TAG_KEYWORDS.get(tab_id, {})
            tags_ja = []
            for t in result.get("tags", []):
                if t in available:
                    tags_ja.append(available[t])
                else:
                    tags_ja.append(t)
            return {
                "easy": result.get("easy", ""),
                "why": result.get("why", ""),
                "glossary": result.get("glossary", []),
                "tags": tags_ja[:3],
                "impact": min(100, max(1, int(result.get("impact", 50)))),
            }
    except Exception as e:
        print(f"    [WARN] JSON parse failed: {e}")

    return _fallback(title)


def _fallback(title):
    return {
        "easy": f"「{title}」についてのニュースです。",
        "why": "テック業界の動向を把握するために注目されています。",
        "glossary": [],
        "tags": ["ニュース"],
        "impact": 50,
    }


def detect_breaking(articles):
    breaking = []
    for a in articles:
        score = a.get("score", 0)
        impact = a.get("impact", 50)
        if score > 300 or impact >= 85:
            breaking.append({
                "text": a.get("easy", a.get("title", "")),
                "level": "red" if impact >= 90 else "orange" if impact >= 80 else "blue",
            })
    return breaking[:3]


def smart_sort(articles):
    """スコア・鮮度・優先度を総合的にスコアリングして並び替え"""
    def calc_score(a):
        hn_score = min(a.get("score", 0) / 100, 5)  # HN点数（最大5点）
        freshness = max(0, 5 - a.get("freshness", 48) / 12)  # 鮮度（最大5点、12時間で1点減）
        priority = max(0, 4 - a.get("priority", 3))  # ソース優先度（最大3点）
        return hn_score + freshness + priority
    return sorted(articles, key=calc_score, reverse=True)


# ─── メイン処理 ─────────────────────────────────────────

def main():
    print("=" * 60)
    print("Tech Pulse v5 (Groq) - ニュース取得開始")
    print(f"時刻: {datetime.now(JST).strftime('%Y-%m-%d %H:%M JST')}")
    print(f"API: Groq ({GROQ_MODEL})")
    print(f"APIキー: {'設定済み' if GROQ_API_KEY else '未設定'}")
    print("=" * 60)

    # Groq API接続テスト
    if GROQ_API_KEY:
        print("\n[0/4] Groq API 接続テスト...")
        test = call_groq("Say OK in one word.")
        if test:
            print(f"  [OK] Groq API 正常動作")
        else:
            print(f"  [ERROR] Groq API に接続できません")

    all_data = {}

    # ── HN記事取得＆全タブ振り分け ──
    print("\n[1/4] Hacker News トップ30記事を取得・振り分け中...")
    hn_articles = fetch_hn_top(30)
    print(f"  -> {len(hn_articles)} 件取得")

    hn_by_tab = {tab: [] for tab in FEEDS.keys()}
    hn_unclassified = []
    for article in hn_articles:
        tab = classify_hn_article(article["title"])
        if tab and tab in hn_by_tab:
            hn_by_tab[tab].append(article)
        else:
            hn_unclassified.append(article)

    for tab, articles in hn_by_tab.items():
        print(f"  -> {tab}: {len(articles)} 件")
    print(f"  -> 未分類: {len(hn_unclassified)} 件")

    # ── 各タブのRSS取得 ──
    print("\n[2/4] RSSフィード取得中...")
    for tab_id, feeds in FEEDS.items():
        print(f"\n  [{tab_id}] {len(feeds)} ソースから取得中...")
        tab_articles = []

        for feed in feeds:
            articles = fetch_rss(feed)
            tab_articles.extend(articles)
            if articles:
                print(f"    -> {feed['name']}: {len(articles)} 件")
            else:
                print(f"    -> {feed['name']}: 0 件 (スキップ)")

        # HN記事をこのタブに追加
        hn_for_tab = hn_by_tab.get(tab_id, [])
        tab_articles.extend(hn_for_tab)
        if hn_for_tab:
            print(f"    -> HN振り分け: {len(hn_for_tab)} 件追加")

        # タイトル重複除去
        seen_titles = set()
        unique_articles = []
        for a in tab_articles:
            title_key = re.sub(r'\W+', '', a["title"].lower())[:60]
            if title_key not in seen_titles:
                seen_titles.add(title_key)
                unique_articles.append(a)

        # スマートソートで上位を選択
        sorted_articles = smart_sort(unique_articles)
        tab_articles = sorted_articles[:MAX_PER_TAB]

        all_data[tab_id] = tab_articles
        print(f"    => 最終: {len(tab_articles)} 件")

    # ── Groq解説生成 ──
    total_articles = sum(len(v) for v in all_data.values())
    print(f"\n[3/4] Groq API で {total_articles} 件の解説を生成中...")
    api_calls = 0
    for tab_id, articles in all_data.items():
        print(f"  [{tab_id}] {len(articles)} 件...")
        for i, article in enumerate(articles):
            is_ja = article.get("lang") == "ja"
            explanation = generate_rich_explanation(article["title"], article.get("summary", ""), tab_id, is_japanese=is_ja)
            article["easy"] = explanation["easy"]
            article["why"] = explanation["why"]
            article["glossary"] = explanation["glossary"]
            article["tags"] = explanation["tags"]
            article["impact"] = explanation["impact"]

            if article.get("hn_id"):
                article["reactions"] = fetch_hn_comments(article["hn_id"], limit=3)
            else:
                article["reactions"] = []

            api_calls += 1
            # Groqレート制限対策（30 req/min = 2秒間隔）
            if i < len(articles) - 1:
                time.sleep(2.5)

        print(f"    -> 完了 (API {api_calls} 回)")

    # ── 速報検出 ──
    print("\n[4/4] 速報検出・データ保存中...")
    all_arts = []
    for arts in all_data.values():
        all_arts.extend(arts)
    breaking = detect_breaking(all_arts)
    if breaking:
        print(f"  -> 速報 {len(breaking)} 件検出！")

    output = {
        "updated_at": datetime.now(JST).strftime("%Y-%m-%d %H:%M JST"),
        "updated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tabs": all_data,
        "hn_top": hn_articles[:10],
        "breaking": breaking,
    }

    output_path = DATA_DIR / "news.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    total = sum(len(v) for v in all_data.values())
    print(f"\n{'=' * 60}")
    print(f"完了！合計 {total} 件（速報 {len(breaking)} 件）を保存")
    print(f"ソース統計:")
    for tab, arts in all_data.items():
        sources = set(a["source"] for a in arts)
        print(f"  {tab}: {len(arts)} 件 from {', '.join(sources)}")
    print(f"API呼び出し: {api_calls} 回")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
