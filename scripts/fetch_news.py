#!/usr/bin/env python3
"""
Tech Pulse - ニュース取得スクリプト
HN API, Reddit JSON, RSSフィードからニュースを取得し、
Gemini APIでやさしい日本語解説を生成する
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

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

# 1タブあたり最大記事数
MAX_PER_TAB = 8

# ─── RSSフィード定義（タブ別） ───────────────────────────
FEEDS = {
    "ai": [
        {"url": "https://blog.google/technology/ai/rss/", "name": "Google AI Blog", "icon": "G"},
        {"url": "https://openai.com/blog/rss.xml", "name": "OpenAI Blog", "icon": "O"},
        {"url": "https://www.anthropic.com/feed.xml", "name": "Anthropic", "icon": "A"},
        {"url": "https://huggingface.co/blog/feed.xml", "name": "Hugging Face", "icon": "HF"},
        {"url": "https://ai.meta.com/blog/rss/", "name": "Meta AI", "icon": "M"},
        {"url": "https://techcrunch.com/category/artificial-intelligence/feed/", "name": "TechCrunch AI", "icon": "TC"},
    ],
    "devtools": [
        {"url": "https://github.blog/feed/", "name": "GitHub Blog", "icon": "GH"},
        {"url": "https://devblogs.microsoft.com/devops/feed/", "name": "Azure DevOps Blog", "icon": "MS"},
        {"url": "https://blog.rust-lang.org/feed.xml", "name": "Rust Blog", "icon": "Rs"},
        {"url": "https://nodejs.org/en/feed/blog.xml", "name": "Node.js Blog", "icon": "NJ"},
        {"url": "https://devblogs.microsoft.com/typescript/feed/", "name": "TypeScript Blog", "icon": "TS"},
    ],
    "data_dx": [
        {"url": "https://blog.getdbt.com/rss/", "name": "dbt Blog", "icon": "dbt"},
        {"url": "https://www.databricks.com/feed", "name": "Databricks", "icon": "DB"},
        {"url": "https://cloud.google.com/blog/products/data-analytics/rss", "name": "GCP Data", "icon": "G"},
        {"url": "https://aws.amazon.com/blogs/big-data/feed/", "name": "AWS Big Data", "icon": "AW"},
    ],
    "cloud": [
        {"url": "https://aws.amazon.com/blogs/aws/feed/", "name": "AWS Blog", "icon": "AW"},
        {"url": "https://cloud.google.com/blog/rss", "name": "GCP Blog", "icon": "G"},
        {"url": "https://azure.microsoft.com/en-us/blog/feed/", "name": "Azure Blog", "icon": "AZ"},
        {"url": "https://www.hashicorp.com/blog/feed.xml", "name": "HashiCorp", "icon": "HC"},
    ],
    "security": [
        {"url": "https://krebsonsecurity.com/feed/", "name": "Krebs on Security", "icon": "KS"},
        {"url": "https://www.bleepingcomputer.com/feed/", "name": "BleepingComputer", "icon": "BC"},
        {"url": "https://thehackernews.com/feeds/posts/default", "name": "The Hacker News", "icon": "HN"},
        {"url": "https://blog.cloudflare.com/rss/", "name": "Cloudflare Blog", "icon": "CF"},
    ],
    "hardware": [
        {"url": "https://www.anandtech.com/rss/", "name": "AnandTech", "icon": "AT"},
        {"url": "https://www.tomshardware.com/feeds/all", "name": "Tom's Hardware", "icon": "TH"},
        {"url": "https://semianalysis.com/feed/", "name": "SemiAnalysis", "icon": "SA"},
    ],
    "funding": [
        {"url": "https://techcrunch.com/category/venture/feed/", "name": "TechCrunch VC", "icon": "TC"},
        {"url": "https://news.crunchbase.com/feed/", "name": "Crunchbase News", "icon": "CB"},
    ],
}

# HN/Reddit のサブレディットマッピング
REDDIT_SUBS = {
    "ai": "MachineLearning+artificial+LocalLLaMA",
    "devtools": "programming+webdev+devops",
    "data_dx": "dataengineering+datascience",
    "cloud": "aws+googlecloud+azure",
    "security": "netsec+cybersecurity",
    "hardware": "hardware+chipdesign",
    "funding": "startups+venturecapital",
}


# ─── ニュース取得関数 ─────────────────────────────────────

def fetch_rss(feed_info: dict) -> list[dict]:
    """RSSフィードから記事を取得"""
    try:
        resp = requests.get(feed_info["url"], timeout=15, headers={"User-Agent": "TechPulse/1.0"})
        feed = feedparser.parse(resp.text)
        articles = []
        for entry in feed.entries[:5]:
            published = ""
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                published = time.strftime("%Y-%m-%d %H:%M", entry.published_parsed)
            elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                published = time.strftime("%Y-%m-%d %H:%M", entry.updated_parsed)

            # 本文の抽出（HTML除去）
            summary = ""
            if hasattr(entry, "summary"):
                summary = re.sub(r"<[^>]+>", "", entry.summary)[:500]

            articles.append({
                "title": entry.get("title", "No title"),
                "url": entry.get("link", ""),
                "summary": summary,
                "published": published,
                "source": feed_info["name"],
                "icon": feed_info["icon"],
            })
        return articles
    except Exception as e:
        print(f"  [WARN] RSS fetch failed for {feed_info['name']}: {e}")
        return []


def fetch_hn_top(limit=15) -> list[dict]:
    """Hacker News トップ記事を取得"""
    try:
        ids = requests.get("https://hacker-news.firebaseio.com/v0/topstories.json", timeout=10).json()
        articles = []
        for item_id in ids[:limit]:
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
            })
        return articles
    except Exception as e:
        print(f"  [WARN] HN fetch failed: {e}")
        return []


def fetch_reddit(subreddit: str, limit=10) -> list[dict]:
    """Redditサブレディットからホット記事を取得"""
    try:
        url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}"
        resp = requests.get(url, timeout=10, headers={"User-Agent": "TechPulse/1.0"}).json()
        articles = []
        for post in resp.get("data", {}).get("children", []):
            d = post["data"]
            if d.get("stickied"):
                continue
            articles.append({
                "title": d.get("title", ""),
                "url": d.get("url", ""),
                "score": d.get("score", 0),
                "comments": d.get("num_comments", 0),
                "subreddit": d.get("subreddit", ""),
                "published": datetime.fromtimestamp(d.get("created_utc", 0), tz=timezone.utc).strftime("%Y-%m-%d %H:%M"),
                "source": f"r/{d.get('subreddit', '')}",
                "icon": "Re",
            })
        return articles
    except Exception as e:
        print(f"  [WARN] Reddit fetch failed for r/{subreddit}: {e}")
        return []


# ─── Gemini APIで解説生成 ──────────────────────────────────

def generate_easy_explanation(title: str, summary: str) -> dict:
    """Geminiを使って、やさしい日本語解説を生成"""
    if not GEMINI_API_KEY:
        return {
            "easy": f"「{title}」についてのニュースです。",
            "why": "テック業界の動向を把握するために重要です。",
            "glossary": []
        }

    prompt = f"""以下のテックニュースについて、日本語で3つの情報を返してください。

タイトル: {title}
内容: {summary[:300]}

以下のJSON形式で返してください（JSONのみ、他の文字は不要）:
{{
  "easy": "専門用語を使わず、中学生にもわかるように2-3文で説明",
  "why": "このニュースが重要な理由を1文で（「〜だから重要」の形式で）",
  "glossary": [
    {{"term": "専門用語1", "definition": "その用語のやさしい説明"}},
    {{"term": "専門用語2", "definition": "その用語のやさしい説明"}}
  ]
}}

glossaryには記事に出てくる専門用語を2-4個含めてください。"""

    try:
        resp = requests.post(
            f"{GEMINI_URL}?key={GEMINI_API_KEY}",
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.3, "maxOutputTokens": 500}
            },
            timeout=30
        )
        data = resp.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]

        # JSON部分を抽出
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            result = json.loads(json_match.group())
            return {
                "easy": result.get("easy", ""),
                "why": result.get("why", ""),
                "glossary": result.get("glossary", [])
            }
    except Exception as e:
        print(f"  [WARN] Gemini API failed: {e}")

    return {
        "easy": f"「{title}」に関するニュースです。",
        "why": "テック業界の最新動向です。",
        "glossary": []
    }


# ─── メイン処理 ─────────────────────────────────────────

def main():
    print("=" * 60)
    print("Tech Pulse - ニュース取得開始")
    print(f"時刻: {datetime.now(JST).strftime('%Y-%m-%d %H:%M JST')}")
    print("=" * 60)

    all_data = {}

    # HNのトップ記事を取得（タブ分類に使う）
    print("\n[1/4] Hacker News トップ記事を取得中...")
    hn_articles = fetch_hn_top(20)
    print(f"  → {len(hn_articles)} 件取得")

    for tab_id, feeds in FEEDS.items():
        print(f"\n[RSS] {tab_id} タブのフィードを取得中...")
        tab_articles = []

        # RSSフィードから取得
        for feed in feeds:
            articles = fetch_rss(feed)
            tab_articles.extend(articles)
            print(f"  → {feed['name']}: {len(articles)} 件")

        # Redditから取得
        if tab_id in REDDIT_SUBS:
            print(f"  [Reddit] r/{REDDIT_SUBS[tab_id]} を取得中...")
            reddit_articles = fetch_reddit(REDDIT_SUBS[tab_id], limit=5)
            tab_articles.extend(reddit_articles)
            print(f"  → Reddit: {len(reddit_articles)} 件")

        # スコアや日時でソート（新しい順）
        tab_articles.sort(key=lambda x: x.get("published", ""), reverse=True)
        tab_articles = tab_articles[:MAX_PER_TAB]

        # Geminiでやさしい解説を生成
        print(f"  [Gemini] {len(tab_articles)} 件の解説を生成中...")
        for i, article in enumerate(tab_articles):
            explanation = generate_easy_explanation(article["title"], article.get("summary", ""))
            article["easy"] = explanation["easy"]
            article["why"] = explanation["why"]
            article["glossary"] = explanation["glossary"]

            # API レート制限対策（無料枠: 15 req/min）
            if GEMINI_API_KEY and i < len(tab_articles) - 1:
                time.sleep(4.5)

        all_data[tab_id] = tab_articles

    # HN記事をAIタブに追加
    hn_for_ai = [a for a in hn_articles if any(
        kw in a["title"].lower() for kw in ["ai", "llm", "gpt", "claude", "gemini", "model", "neural", "ml", "openai", "anthropic"]
    )][:3]
    if hn_for_ai:
        for article in hn_for_ai:
            explanation = generate_easy_explanation(article["title"], "")
            article.update(explanation)
            if GEMINI_API_KEY:
                time.sleep(4.5)
        all_data["ai"] = (all_data.get("ai", []) + hn_for_ai)[:MAX_PER_TAB]

    # データ保存
    output = {
        "updated_at": datetime.now(JST).strftime("%Y-%m-%d %H:%M JST"),
        "updated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tabs": all_data,
        "hn_top": hn_articles[:10],
    }

    output_path = DATA_DIR / "news.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    total = sum(len(v) for v in all_data.values())
    print(f"\n{'=' * 60}")
    print(f"完了！合計 {total} 件の記事を {output_path} に保存")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
