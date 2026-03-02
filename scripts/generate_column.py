"""
Deep Dive Column Generator
Gemini API (free tier) を使って毎日のコラムHTMLを生成し、
columns/ フォルダと index.json を自動更新する。
"""

import os
import json
import datetime
import google.generativeai as genai

# ─── 設定 ───
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
COLUMNS_DIR = "columns"
INDEX_FILE = os.path.join(COLUMNS_DIR, "index.json")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")

today = datetime.date.today().isoformat()

# ─── 過去のテーマを読み込んで重複回避 ───
past_titles = []
if os.path.exists(INDEX_FILE):
    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        existing = json.load(f)
    past_titles = [c.get("title", "") for c in existing]
else:
    existing = []

past_str = "\n".join(f"- {t}" for t in past_titles[-30:]) if past_titles else "（なし）"

next_issue = max((c.get("issue", 0) for c in existing), default=0) + 1

# ─── Step 1: テーマ選定 ───
theme_prompt = f"""あなたはテクノロジー・ビジネス・投資に精通したコラムニストです。
今日 {today} の「Deep Dive」コラムのテーマを1つ選んでください。

条件:
- テック、AI、投資、スタートアップ、科学のどれかに関連
- 「みんなが知らない」意外性のあるテーマが望ましい
- 以下の過去テーマとは被らないこと:
{past_str}

以下の形式で回答（JSONのみ、他のテキスト不要）:
{{"title": "コラムタイトル", "category": "カテゴリ（例: AI \u00d7 Robotics）", "angle": "切り口の説明（1文）"}}
"""

theme_resp = model.generate_content(theme_prompt)
theme_text = theme_resp.text.strip()

if "```" in theme_text:
    theme_text = theme_text.split("```")[1]
    if theme_text.startswith("json"):
        theme_text = theme_text[4:]
    theme_text = theme_text.strip()

theme = json.loads(theme_text)

# ─── Step 2: コラム本文生成 ───
column_prompt = f"""あなたはテクノロジーに精通したコラムニストです。
以下のテーマで「Deep Dive」コラムのHTML本文を生成してください。

テーマ: {theme['title']}
カテゴリ: {theme['category']}
切り口: {theme['angle']}
日付: {today}
Issue: #{next_issue:03d}

【スタイル指示】
- 会話調で書く。読者に話しかけるようなトーン
- 最初に読者の興味を引くフック
- データや具体例を必ず入れる
- 最後に「So What?」セクションを入れる
- 読了5分程度

【HTML指示】
- 完全な<!DOCTYPE html>から</html>まで
- ライト背景（#fafafa系）、フォントはInter + Noto Serif JP
- .wrap, .hero, .talk, .callout, .data, .sowhat, .footer のクラス構造
- レスポンシブ対応
- 全体で250行程度

HTMLコードのみを出力してください。
"""

column_resp = model.generate_content(column_prompt)
html_content = column_resp.text.strip()

if html_content.startswith("```"):
    lines = html_content.split("\n")
    html_content = "\n".join(lines[1:])
if html_content.endswith("```"):
    html_content = html_content[:-3].strip()
if html_content.startswith("html"):
    html_content = html_content[4:].strip()

# ─── Step 3: ファイル保存 ───
os.makedirs(COLUMNS_DIR, exist_ok=True)
filename = f"{today}.html"
filepath = os.path.join(COLUMNS_DIR, filename)
with open(filepath, "w", encoding="utf-8") as f:
    f.write(html_content)
print(f"Generated: {filepath}")

# ─── Step 4: index.json 更新 ───
new_entry = {
    "issue": next_issue,
    "date": today,
    "title": theme["title"],
    "category": theme["category"],
    "file": f"columns/{filename}"
}
existing.insert(0, new_entry)
with open(INDEX_FILE, "w", encoding="utf-8") as f:
    json.dump(existing, f, ensure_ascii=False, indent=2)
print(f"Updated index.json: Issue #{next_issue:03d} - {theme['title']}")
