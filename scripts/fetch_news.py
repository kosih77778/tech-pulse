#!/usr/bin/env python3
"""
Tech Pulse v2 - ニュース取得スクリプト（強化版）
HN API, Reddit JSON, RSSフィードからニュースを取得し、
Gemini APIで詳細な日本語解説・用語集・開発者反応を生成する
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

MAX_PER_TAB = 6

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
        {"url": "https://www.tomshardware.com/feeds/all", "name": "Tom's Hardware", "icon": "TH"},
        {"url": "https://semianalysis.com/feed/", "name": "SemiAnalysis", "icon": "SA"},
    ],
    "funding": [
        {"url": "https://techcrunch.com/category/venture/feed/", "name": "TechCrunch VC", "icon": "TC"},
        {"url": "https://news.crunchbase.com/feed/", "name": "Crunchbase News", "icon": "CB"},
    ],
}

REDDIT_SUBS = {
    "ai": "MachineLearning+artificial+LocalLLaMA",
    "devtools": "programming+webdev+devops",
    "data_dx": "dataengineering+datascience",
    "cloud": "aws+googlecloud+azure",
    "security": "netsec+cybersecurity",
    "hardware": "hardware+chipdesign",
    "funding": "startups+venturecapital",
}

# タグの日本語マッピング
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
    """RSSフィードから記事を取得"""
    try:
        resp = requests.get(feed_info["url"], timeout=15, headers={"User-Agent": "TechPulse/2.0"})
        feed = feedparser.parse(resp.text)
        articles = []
        for entry in feed.entries[:5]:
            published = ""
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                published = time.strftime("%Y-%m-%d %H:%M", entry.published_parsed)
            elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                published = time.strftime("%Y-%m-%d %H:%M", entry.updated_parsed)

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
            })
        return articles
    except Exception as e:
        print(f"  [WARN] RSS failed: {feed_info['name']}: {e}")
        return []


def fetch_hn_top(limit=25):
    """Hacker News トップ記事を取得"""
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
                })
            except Exception:
                continue
        return articles
    except Exception as e:
        print(f"  [WARN] HN failed: {e}")
        return []


def fetch_hn_comments(hn_id, limit=3):
    """HN記事のトップコメントを取得"""
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
                    comments.append({
                        "user": kid.get("by", "anon"),
                        "text": text,
                        "platform": "HN",
                    })
                if len(comments) >= limit:
                    break
            except Exception:
                continue
        return comments
    except Exception:
        return []


def fetch_reddit(subreddit, limit=10):
    """Redditサブレディットからホット記事を取得"""
    try:
        url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}"
        resp = requests.get(url, timeout=10, headers={"User-Agent": "TechPulse/2.0"}).json()
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
        print(f"  [WARN] Reddit failed: r/{subreddit}: {e}")
        return []


# ─── Gemini API 強化版 ──────────────────────────────────

def generate_rich_explanation(title, summary, tab_id):
    """Geminiで詳細な解説・用語集・タグ・重要度を生成"""
    if not GEMINI_API_KEY:
        return {
            "easy": f"「{title}」についてのニュースです。詳細は記事本文をご確認ください。",
            "why": "テック業界の最新動向として注目されています。",
            "glossary": [],
            "tags": ["ニュース"],
            "impact": 50,
        }

    available_tags = TAG_KEYWORDS.get(tab_id, TAG_KEYWORDS["ai"])
    tags_str = "、".join([f'"{k}"({v})' for k, v in available_tags.items()])

    prompt = f"""あなたはテック業界のジャーナリストです。以下のニュースを日本語で詳しく解説してください。

タイトル: {title}
内容: {summary[:600]}
カテゴリ: {tab_id}

以下のJSON形式で返してください（JSONのみ、マークダウンのコードブロック不要）:
{{
  "easy": "専門用語を使わず、中学生にもわかるように4-6文で詳しく説明。具体的な数字や比較を含めて。重要な部分は強調する。ドル表記は円換算も併記（例：3億ドル（約450億円））",
  "why": "このニュースが重要な理由を2文で説明。業界への影響や、今後どうなりそうかも含めて。",
  "glossary": [
    {{"term": "専門用語1", "definition": "その用語の意味を、例え話や具体例を使って50文字以上で丁寧に説明"}},
    {{"term": "専門用語2", "definition": "同上"}},
    {{"term": "専門用語3", "definition": "同上"}},
    {{"term": "専門用語4", "definition": "同上"}}
  ],
  "tags": ["該当するタグを2-3個選択: {tags_str}"],
  "impact": 1から100の数値で重要度を判定（90以上=業界を変える大ニュース、70-89=注目ニュース、50-69=一般ニュース、50未満=小ネタ）
}}

glossaryには記事に出てくる専門用語を3-4個含めてください。一般の人が知らないような用語を優先的に選んでください。"""

    try:
        resp = requests.post(
            f"{GEMINI_URL}?key={GEMINI_API_KEY}",
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.4, "maxOutputTokens": 1000}
            },
            timeout=45
        )
        data = resp.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]

        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            result = json.loads(json_match.group())
            tags_raw = result.get("tags", [])
            tags_ja = []
            for t in tags_raw:
                if t in available_tags:
                    tags_ja.append(available_tags[t])
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
        print(f"  [WARN] Gemini failed: {e}")

    return {
        "easy": f"「{title}」に関するニュースです。",
        "why": "テック業界の最新動向です。",
        "glossary": [],
        "tags": ["ニュース"],
        "impact": 50,
    }


# ─── 速報判定 ────────────────────────────────────────────

def detect_breaking(articles):
    """スコアや反応数が高い記事を速報として抽出"""
    breaking = []
    for a in articles:
        score = a.get("score", 0)
        impact = a.get("impact", 50)
        if score > 300 or impact >= 85:
            breaking.append({
                "text": a.get("title", ""),
                "level": "red" if impact >= 90 else "orange" if impact >= 80 else "blue",
            })
    return breaking[:2]


# ─── メイン処理 ─────────────────────────────────────────

def main():
    print("=" * 60)
    print("Tech Pulse v2 - ニュース取得開始（強化版）")
    print(f"時刻: {datetime.now(JST).strftime('%Y-%m-%d %H:%M JST')}")
    print("=" * 60)

    all_data = {}

    # HNトップ記事
    print("\n[1/4] Hacker News トップ記事を取得中...")
    hn_articles = fetch_hn_top(25)
    print(f"  -> {len(hn_articles)} 件取得")

    for tab_id, feeds in FEEDS.items():
        print(f"\n[RSS] {tab_id} タブのフィードを取得中...")
        tab_articles = []

        for feed in feeds:
            articles = fetch_rss(feed)
            tab_articles.extend(articles)
            print(f"  -> {feed['name']}: {len(articles)} 件")

        if tab_id in REDDIT_SUBS:
            print(f"  [Reddit] r/{REDDIT_SUBS[tab_id]} を取得中...")
            reddit_articles = fetch_reddit(REDDIT_SUBS[tab_id], limit=5)
            tab_articles.extend(reddit_articles)
            print(f"  -> Reddit: {len(reddit_articles)} 件")

        tab_articles.sort(key=lambda x: x.get("score", 0) + (1000 if x.get("published", "") > (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%d") else 0), reverse=True)
        tab_articles = tab_articles[:MAX_PER_TAB]

        # Geminiで詳細解説を生成
        print(f"  [Gemini] {len(tab_articles)} 件の解説を生成中...")
        for i, article in enumerate(tab_articles):
            explanation = generate_rich_explanation(article["title"], article.get("summary", ""), tab_id)
            article["easy"] = explanation["easy"]
            article["why"] = explanation["why"]
            article["glossary"] = explanation["glossary"]
            article["tags"] = explanation["tags"]
            article["impact"] = explanation["impact"]

            # HN記事なら開発者コメントも取得
            if article.get("hn_id"):
                print(f"    [HN Comments] id={article['hn_id']}")
                article["reactions"] = fetch_hn_comments(article["hn_id"], limit=3)
            else:
                article["reactions"] = []

            # API レート制限対策
            if GEMINI_API_KEY and i < len(tab_articles) - 1:
                time.sleep(5)

        all_data[tab_id] = tab_articles

    # HN記事をAIタブに追加
    ai_keywords = ["ai", "llm", "gpt", "claude", "gemini", "model", "neural", "ml", "openai", "anthropic", "deepseek", "transformer", "agent"]
    hn_for_ai = [a for a in hn_articles if any(kw in a["title"].lower() for kw in ai_keywords)][:3]
    if hn_for_ai:
        for article in hn_for_ai:
            explanation = generate_rich_explanation(article["title"], "", "ai")
            article.update(explanation)
            if article.get("hn_id"):
                article["reactions"] = fetch_hn_comments(article["hn_id"], limit=3)
            else:
                article["reactions"] = []
            if GEMINI_API_KEY:
                time.sleep(5)
        existing_titles = {a["title"] for a in all_data.get("ai", [])}
        new_hn = [a for a in hn_for_ai if a["title"] not in existing_titles]
        all_data["ai"] = (all_data.get("ai", []) + new_hn)[:MAX_PER_TAB]

    # 速報検出
    all_articles = []
    for articles in all_data.values():
        all_articles.extend(articles)
    breaking = detect_breaking(all_articles)

    # データ保存
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
    print(f"完了！合計 {total} 件（速報 {len(breaking)} 件）を {output_path} に保存")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
