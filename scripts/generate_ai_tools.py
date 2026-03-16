"""
AI Tools Trend Generator
data/ai-tools-config.json を読み、Gemini API で各ツールの最新動向を調査し、
data/ai-tools-trends.json に出力する。
"""

import os
import json
import datetime
import google.generativeai as genai

CONFIG_PATH = "data/ai-tools-config.json"
OUTPUT_PATH = "data/ai-tools-trends.json"

genai.configure(api_key=os.environ.get("GEMINI_API_KEY", ""))
model = genai.GenerativeModel("gemini-2.0-flash")

today = datetime.date.today().isoformat()

# ─── 設定読み込み ───
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = json.load(f)

# ─── ツール一覧をプロンプト用に整形 ───
tool_list = ""
cat_ids = []
for cat in config["categories"]:
    tool_names = ", ".join(t["name"] for t in cat["tools"])
    tool_list += f"- {cat['name']} (id: {cat['id']}): {tool_names}\n"
    cat_ids.append(cat["id"])

# ─── Gemini に一括問い合わせ ───
prompt = f"""あなたはAIツールの最新動向に精通したテクノロジーアナリストです。
今日は {today} です。

以下のAIツールカテゴリとツールについて、最新のトレンド情報をJSON形式で提供してください。
Web検索を活用して、できるだけ最新の情報を反映してください。

カテゴリとツール:
{tool_list}

各カテゴリについて:
- trend_summary: カテゴリ全体の最新動向（1-2文、日本語）

各ツールについて:
- trend: 最新の動向やアップデート情報（2-3文、日本語）
- highlights: 注目ポイント（1-3個の短いフレーズ、配列）
- momentum: "up"（勢いあり）/ "stable"（安定）/ "down"（低調）

以下の正確なJSON形式で回答してください（JSONのみ、他のテキスト不要）:
{{
  "categories": [
    {{
      "id": "カテゴリid",
      "trend_summary": "...",
      "tools": [
        {{
          "name": "ツール名（入力と完全一致させること）",
          "trend": "...",
          "highlights": ["...", "..."],
          "momentum": "up|stable|down"
        }}
      ]
    }}
  ]
}}

カテゴリIDは以下の順序で出力: {", ".join(cat_ids)}
"""

response = model.generate_content(prompt)
text = response.text.strip()

# コードフェンス除去
if "```" in text:
    text = text.split("```")[1]
    if text.startswith("json"):
        text = text[4:]
    text = text.strip()

try:
    trends = json.loads(text)
    trends["generated_at"] = datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=9))
    ).strftime("%Y-%m-%d %H:%M JST")

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(trends, f, ensure_ascii=False, indent=2)
    print(f"Generated: {OUTPUT_PATH}")

except json.JSONDecodeError as e:
    print(f"ERROR: Failed to parse Gemini response: {e}")
    print(f"Raw response: {text[:500]}")
    exit(1)
