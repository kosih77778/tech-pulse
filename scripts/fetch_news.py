#!/usr/bin/env python3
"""
Tech Pulse v6 - ニュース取得スクリプト（Groq版・ホットネス判定付き）
HN + はてブ + クロスソース検出で「本当にホットな記事」を厳選
Zenn, Qiita, はてブホットエントリーを追加
Groq API (Llama 3.3 70B) でやさしい日本語解説を生成する
"""

import json
import os
import time
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import Counter
from difflib import SequenceMatcher

import requests
import feedparser

# ─── 設定 ───────────────────────────────────────────────
JST = timezone(timedelta(hours=9))
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL_LARGE = "llama-3.3-70b-versatile"  # 高品質（トークン上限: 10万/日）
GROQ_MODEL_SMALL = "llama-3.1-8b-instant"     # 軽量（トークン上限: 大幅に高い）
TOP_N_USE_LARGE = 3  # 各タブ上位N件のみ70Bモデルを使用

MAX_PER_TAB = 10

# ─── RSSフィード定義（タブ別） ───────────────────────────
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
        # --- エンジニアコミュニティ ---
        {"url": "https://zenn.dev/feed", "name": "Zenn トレンド", "icon": "ZN", "priority": 1, "lang": "ja"},
        {"url": "https://qiita.com/popular-items/feed.atom", "name": "Qiita 人気", "icon": "QT", "priority": 1, "lang": "ja"},
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
        # --- 海外速報系 ---
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

# はてなブックマーク ホットエントリー（テクノロジー）- タブ横断のホットネス判定用
HATENA_HOTENTRY_URL = "https://b.hatena.ne.jp/hotentry/it.rss"

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
                 "processor", "tpu"],
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


# ─── ホットネス判定エンジン ────────────────────────────────

def fetch_hatena_hotentry():
    """はてブのテクノロジーホットエントリーを取得（ホットさの温度計）"""
    try:
        resp = requests.get(HATENA_HOTENTRY_URL, timeout=15, headers={"User-Agent": "TechPulse/4.0"})
        feed = feedparser.parse(resp.text)
        entries = []
        for entry in feed.entries[:30]:
            bookmarks = 0
            # はてブRSSにはブックマーク数が含まれる場合がある
            if hasattr(entry, "hatena_bookmarkcount"):
                bookmarks = int(entry.hatena_bookmarkcount)
            entries.append({
                "title": entry.get("title", ""),
                "url": entry.get("link", ""),
                "bookmarks": bookmarks,
            })
        return entries
    except Exception as e:
        print(f"  [WARN] はてブ取得失敗: {e}")
        return []


def normalize_title(title):
    """タイトルを正規化して比較しやすくする"""
    t = title.lower().strip()
    t = re.sub(r'[^\w\s]', '', t)
    t = re.sub(r'\s+', ' ', t)
    return t


def title_similarity(t1, t2):
    """2つのタイトルの類似度を計算（0-1）"""
    n1 = normalize_title(t1)
    n2 = normalize_title(t2)
    return SequenceMatcher(None, n1, n2).ratio()


def extract_key_phrases(title):
    """タイトルからキーフレーズを抽出"""
    # 固有名詞やキーワードを抽出
    words = re.findall(r'[A-Z][a-zA-Z]+|[a-z]{4,}', title)
    return set(w.lower() for w in words)


def calc_hotness(article, hn_titles, hatena_titles, all_rss_titles):
    """
    記事のホットネススコアを計算（0-100）

    構成要素:
    1. HNスコア（HN記事の場合）: 最大30点
    2. はてブ関連度: 最大25点
    3. クロスソース検出: 最大25点
    4. 鮮度: 最大10点
    5. ソース優先度: 最大10点
    """
    score = 0.0
    reasons = []

    title = article.get("title", "")

    # 1. HNスコア（HN記事のupvote数）
    hn_score = article.get("score", 0)
    if hn_score > 0:
        if hn_score >= 500:
            score += 30
            reasons.append(f"HN:{hn_score}pts(超注目)")
        elif hn_score >= 300:
            score += 25
            reasons.append(f"HN:{hn_score}pts(注目)")
        elif hn_score >= 100:
            score += 15
            reasons.append(f"HN:{hn_score}pts")
        elif hn_score >= 50:
            score += 8
            reasons.append(f"HN:{hn_score}pts")
    else:
        # HN記事でなくても、HNで似たタイトルの記事がある場合ボーナス
        for hn_t in hn_titles:
            sim = title_similarity(title, hn_t["title"])
            if sim > 0.4:
                hn_pts = min(hn_t.get("score", 0) / 20, 20)
                score += hn_pts
                reasons.append(f"HN関連({hn_t['score']}pts)")
                break

    # 2. はてブ関連度（はてブホットエントリーに類似タイトルがある場合）
    for hb in hatena_titles:
        sim = title_similarity(title, hb["title"])
        if sim > 0.35:
            bm = hb.get("bookmarks", 50)
            hatena_pts = min(bm / 10, 25)
            score += max(hatena_pts, 10)  # 最低10点
            reasons.append(f"はてブ関連({bm}ブクマ)")
            break
        # URLが一致する場合も
        if article.get("url") and hb.get("url") and article["url"] == hb["url"]:
            score += 25
            reasons.append("はてブHot")
            break

    # 3. クロスソース検出（複数メディアが同じ話題を報じている）
    key_phrases = extract_key_phrases(title)
    cross_count = 0
    cross_sources = set()
    for other in all_rss_titles:
        if other["source"] == article.get("source"):
            continue
        other_phrases = extract_key_phrases(other["title"])
        overlap = key_phrases & other_phrases
        if len(overlap) >= 2 or title_similarity(title, other["title"]) > 0.4:
            cross_count += 1
            cross_sources.add(other["source"])
    if cross_count >= 3:
        score += 25
        reasons.append(f"クロスソース:{len(cross_sources)}社")
    elif cross_count >= 2:
        score += 18
        reasons.append(f"クロスソース:{len(cross_sources)}社")
    elif cross_count >= 1:
        score += 10
        reasons.append(f"クロスソース:{len(cross_sources)}社")

    # 4. 鮮度（新しいほど高い）
    freshness_hours = article.get("freshness", 48)
    if freshness_hours < 6:
        score += 10
    elif freshness_hours < 12:
        score += 7
    elif freshness_hours < 24:
        score += 5
    elif freshness_hours < 48:
        score += 2

    # 5. ソース優先度
    priority = article.get("priority", 3)
    score += max(0, (4 - priority) * 3.3)  # priority 1 = 10点, 2 = 6.6点, 3 = 3.3点

    article["hotness"] = round(min(score, 100), 1)
    article["hotness_reasons"] = reasons
    return article


# ─── ニュース取得関数 ─────────────────────────────────────

def fetch_rss(feed_info):
    try:
        resp = requests.get(feed_info["url"], timeout=15, headers={"User-Agent": "TechPulse/4.0"})
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


def fetch_hn_top(limit=50):
    """HNトップ記事を取得（ホットネス判定用に多めに取得）"""
    try:
        ids = requests.get("https://hacker-news.firebaseio.com/v0/topstories.json", timeout=10).json()
        articles = []
        for item_id in ids[:limit]:
            try:
                item = requests.get(f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json", timeout=5).json()
                if not item or item.get("type") != "story":
                    continue
                articles.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", f"https://news.ycombinator.com/item?id={item_id}"),
                    "score": item.get("score", 0),
                    "comments": item.get("descendants", 0),
                    "hn_id": item_id,
                    "published": datetime.fromtimestamp(item.get("time", 0), tz=timezone.utc).strftime("%Y-%m-%d %H:%M"),
                    "source": "Hacker News",
                    "icon": "HN",
                    "priority": 0,
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

def call_groq(prompt, model=None):
    """Groq APIを呼び出す（モデル指定可能）"""
    use_model = model or GROQ_MODEL_SMALL
    try:
        resp = requests.post(
            GROQ_URL,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": use_model,
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
            # 70Bで失敗したら8Bにフォールバック
            if use_model == GROQ_MODEL_LARGE and "rate limit" in error_msg.lower():
                print(f"    [FALLBACK] 8Bモデルで再試行...")
                return call_groq(prompt, model=GROQ_MODEL_SMALL)
            return None
    except Exception as e:
        print(f"    [WARN] Groq call failed: {e}")
        return None


def generate_rich_explanation(title, summary, tab_id, is_japanese=False, use_large_model=False):
    if not GROQ_API_KEY:
        return _fallback(title)

    model = GROQ_MODEL_LARGE if use_large_model else GROQ_MODEL_SMALL
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
  "why": "重要ポイントを1-2文で簡潔に。「このニュースは重要です」のような前置きは不要。いきなり具体的な理由・影響・今後の展望を書く。",
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

    text = call_groq(prompt, model=model)
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
        hotness = a.get("hotness", 0)
        if hotness >= 60:
            breaking.append({
                "text": a.get("easy", a.get("title", "")),
                "level": "red" if hotness >= 80 else "orange" if hotness >= 60 else "blue",
            })
    return breaking[:3]


# ─── メイン処理 ─────────────────────────────────────────

def main():
    print("=" * 60)
    print("Tech Pulse v6 (Groq) - ホットネス判定付きニュース取得")
    print(f"時刻: {datetime.now(JST).strftime('%Y-%m-%d %H:%M JST')}")
    print(f"API: Groq ({GROQ_MODEL_LARGE} + {GROQ_MODEL_SMALL})")
    print(f"APIキー: {'設定済み' if GROQ_API_KEY else '未設定'}")
    print("=" * 60)

    # Groq API接続テスト
    if GROQ_API_KEY:
        print("\n[0/5] Groq API 接続テスト...")
        test = call_groq("Say OK in one word.", model=GROQ_MODEL_SMALL)
        if test:
            print(f"  [OK] Groq API 正常動作")
            print(f"  モデル戦略: 上位{TOP_N_USE_LARGE}件→70B, 残り→8B")
        else:
            print(f"  [ERROR] Groq API に接続できません")

    # ── Step 1: ホットネスの温度計を取得 ──
    print("\n[1/5] ホットネス判定データ取得中...")

    # HN トップ50（グローバルのホットさ）
    hn_articles = fetch_hn_top(50)
    print(f"  -> Hacker News: {len(hn_articles)} 件")

    # はてブ ホットエントリー（日本のホットさ）
    hatena_entries = fetch_hatena_hotentry()
    print(f"  -> はてブHot: {len(hatena_entries)} 件")

    # HNをタブ別に振り分け
    hn_by_tab = {tab: [] for tab in FEEDS.keys()}
    hn_unclassified = []
    for article in hn_articles:
        tab = classify_hn_article(article["title"])
        if tab and tab in hn_by_tab:
            hn_by_tab[tab].append(article)
        else:
            hn_unclassified.append(article)

    for tab, articles in hn_by_tab.items():
        if articles:
            print(f"  -> HN→{tab}: {len(articles)} 件")
    print(f"  -> HN未分類: {len(hn_unclassified)} 件")

    # ── Step 2: 全RSSフィード取得 ──
    print("\n[2/5] RSSフィード取得中...")
    all_rss_global = []  # クロスソース検出用の全記事リスト
    tab_raw_articles = {}

    for tab_id, feeds in FEEDS.items():
        print(f"\n  [{tab_id}] {len(feeds)} ソースから取得中...")
        tab_articles = []

        for feed in feeds:
            articles = fetch_rss(feed)
            tab_articles.extend(articles)
            all_rss_global.extend(articles)
            if articles:
                print(f"    -> {feed['name']}: {len(articles)} 件")
            else:
                print(f"    -> {feed['name']}: 0 件")

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

        tab_raw_articles[tab_id] = unique_articles
        print(f"    => 候補: {len(unique_articles)} 件")

    # ── Step 3: ホットネス判定＆記事選定（タブ横断の重複除去付き） ──
    print("\n[3/5] ホットネス判定中...")
    all_data = {}
    global_seen_urls = set()     # タブ横断でURL重複を除去
    global_seen_titles = set()   # タブ横断でタイトル重複を除去

    for tab_id, articles in tab_raw_articles.items():
        # 全記事のホットネスを計算
        for article in articles:
            calc_hotness(article, hn_articles, hatena_entries, all_rss_global)

        # ホットネス順にソート
        sorted_articles = sorted(articles, key=lambda a: a.get("hotness", 0), reverse=True)

        # 他タブで既に選ばれた記事を除外（タブ横断重複除去）
        deduped = []
        for a in sorted_articles:
            url_key = a.get("url", "").split("?")[0].rstrip("/")  # クエリパラメータ除去
            title_key = re.sub(r'\W+', '', a["title"].lower())[:60]
            if url_key and url_key in global_seen_urls:
                continue
            if title_key in global_seen_titles:
                continue
            deduped.append(a)

        # 日本語記事を最低3件確保
        ja_articles = [a for a in deduped if a.get("lang") == "ja"]
        en_articles = [a for a in deduped if a.get("lang") != "ja"]

        ja_pick = ja_articles[:min(3, len(ja_articles))]
        remaining = MAX_PER_TAB - len(ja_pick)
        en_pick = en_articles[:remaining]

        # 最終的にホットネス順で並べ替え
        final = sorted(ja_pick + en_pick, key=lambda a: a.get("hotness", 0), reverse=True)
        all_data[tab_id] = final

        # 選ばれた記事をグローバル重複チェックに登録
        for a in final:
            url_key = a.get("url", "").split("?")[0].rstrip("/")
            title_key = re.sub(r'\W+', '', a["title"].lower())[:60]
            if url_key:
                global_seen_urls.add(url_key)
            global_seen_titles.add(title_key)

        # ホットネス上位をログ表示
        ja_count = len([a for a in final if a.get("lang") == "ja"])
        print(f"  [{tab_id}] {len(final)} 件（日本語 {ja_count} 件）")
        for a in final[:3]:
            reasons = ", ".join(a.get("hotness_reasons", [])[:2])
            print(f"    🔥{a['hotness']:.0f} | {a['title'][:50]}... [{reasons}]")

    # ── Step 4: Groq解説生成（モデル使い分け） ──
    total_articles = sum(len(v) for v in all_data.values())
    large_count = min(TOP_N_USE_LARGE, MAX_PER_TAB) * len(all_data)
    small_count = total_articles - large_count
    print(f"\n[4/5] Groq API で {total_articles} 件の解説を生成中...")
    print(f"  70B: {large_count} 件, 8B: {small_count} 件（トークン節約）")
    api_calls_large = 0
    api_calls_small = 0
    for tab_id, articles in all_data.items():
        print(f"  [{tab_id}] {len(articles)} 件...")
        for i, article in enumerate(articles):
            is_ja = article.get("lang") == "ja"
            # ホットネス上位N件のみ70Bモデル、残りは8Bモデル
            use_large = i < TOP_N_USE_LARGE
            model_label = "70B" if use_large else "8B"
            explanation = generate_rich_explanation(article["title"], article.get("summary", ""), tab_id, is_japanese=is_ja, use_large_model=use_large)
            article["easy"] = explanation["easy"]
            article["why"] = explanation["why"]
            article["glossary"] = explanation["glossary"]
            article["tags"] = explanation["tags"]
            article["impact"] = explanation["impact"]

            if article.get("hn_id"):
                article["reactions"] = fetch_hn_comments(article["hn_id"], limit=3)
            else:
                article["reactions"] = []

            if use_large:
                api_calls_large += 1
            else:
                api_calls_small += 1
            # Groqレート制限対策（30 req/min = 2秒間隔）
            if i < len(articles) - 1:
                time.sleep(2.5)

        print(f"    -> 完了 (70B: {api_calls_large}, 8B: {api_calls_small})")

    # ── Step 5: 速報検出＆保存 ──
    print("\n[5/5] 速報検出・データ保存中...")
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
        avg_hot = sum(a.get("hotness", 0) for a in arts) / len(arts) if arts else 0
        print(f"  {tab}: {len(arts)} 件 (平均ホットネス {avg_hot:.0f}) from {', '.join(sources)}")
    print(f"API呼び出し: 70B={api_calls_large}回, 8B={api_calls_small}回, 計{api_calls_large + api_calls_small}回")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
