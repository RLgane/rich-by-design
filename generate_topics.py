#!/usr/bin/env python3
"""Doplni banku tem (topics_bank.json) cez GitHub Models (zadarmo) ak je malo nepouzitych.
V GitHub Actions: token z GITHUB_TOKEN + permission models:read. Lokalne: MODELS_TOKEN = PAT s pravom 'models'."""
import json
import os
import re
import sys

import requests

ROOT = os.path.dirname(os.path.abspath(__file__))
BANK = os.path.join(ROOT, "topics_bank.json")
STATE = os.path.join(ROOT, "used_topics.json")

TARGET = int(os.environ.get("TOPICS_TARGET", "15"))
MODEL = os.environ.get("MODELS_MODEL", "openai/gpt-4o-mini")
BASE = os.environ.get("MODELS_BASE_URL", "https://models.github.ai/inference")
TOKEN = os.environ.get("MODELS_TOKEN") or os.environ.get("GITHUB_TOKEN")

# >>> NISA: PENIAZE & MINDSET <<<
# Drzime sa VSEOBECNYCH principov a psychologie penazi. ZIADNE konkretne financne/investicne
# rady, ziadne "kup toto", ziadne nazvy akcii/krypta/produktov, ziadne vymyslene cisla.
SYSTEM = ("You are a viral short-form video scriptwriter for a MONEY MINDSET channel. "
          "You teach the PSYCHOLOGY and PRINCIPLES of money and wealth: habits, behavior, "
          "discipline, long-term thinking, common mistakes, timeless wisdom. "
          "You ONLY use well-known, widely-accepted principles and verifiable, famous facts or quotes. "
          "You NEVER give specific financial or investment advice, never name specific stocks, coins, "
          "or products, never promise returns, and never invent numbers or statistics. "
          "Write EVERY SCRIPT for TEXT-TO-SPEECH delivery: use short, punchy sentences. "
          "Direct second-person 'you' address. Use contractions. Natural spoken rhythm. "
          "Avoid long flowing clauses and complex punctuation that sound flat or awkward read aloud. "
          "Keep it conversational like you're talking to one person, not lecturing. "
          "You output strict JSON, nothing else.")

EXAMPLE = {
    "title": "3 Money Habits That Quietly Build Wealth",
    "segments": [
        {"text": "You're budgeting wrong. Rich people budget to think, not to spend less.", "keywords": "city skyline night"},
        {"text": "The second one's the one everybody skips.", "keywords": "person walking city street"},
        {"text": "They pay themselves first, before a single bill is touched.", "keywords": "saving coins jar"},
        {"text": "They treat their time like money, because one buys the other back.", "keywords": "clock close up"},
        {"text": "That's why they budget to think, not just to save.", "keywords": "city skyline night"},
        {"text": "Want to stop wasting your paycheck? Follow for more.", "keywords": "city skyline sunrise"},
    ],
    "description": "Wealthy people think differently about money. Master these three habits and watch your mindset shift. Follow to become the investor you always wanted to be. \U0001F4B0",
    "hashtags": ["#moneymindset", "#wealth", "#money", "#mindset", "#financialfreedom", "#shorts", "#fyp", "#success"],
}


def build_prompt(n, existing_titles):
    return (
        f"Generate {n} NEW faceless short-form video topics for TikTok / Reels / YouTube Shorts.\n"
        "Niche: MONEY MINDSET & WEALTH PSYCHOLOGY - habits, discipline, long-term thinking, "
        "behavior of self-made people, common money mistakes, delayed gratification, value of time, "
        "lifestyle inflation, the psychology of saving and spending, timeless money wisdom and famous quotes.\n"
        "Return ONLY a JSON array (no markdown). Each item EXACTLY this schema:\n"
        f"{json.dumps(EXAMPLE, ensure_ascii=False, indent=2)}\n\n"
        "Rules (make it feel PRO and VIRAL):\n"
        "- title: catchy, like '3 Money Habits That Quietly Build Wealth' or 'Why The Rich Think Differently'.\n"
        "- exactly 6 segments.\n"
        "- Segment 1 = THE HOOK: a bold, counter-intuitive claim under 12 words, directly addressing 'you'. "
        "NEVER start with 'Did you know' or 'The wealthy'. Examples: 'You're budgeting wrong.' or 'Rich people lie about money.' "
        "Make the reader STOP scrolling.\n"
        "- Segment 2 = UNIQUE topic-specific tease: NOT a generic filler phrase like 'the next one feels backwards'. "
        "MUST directly reference the actual content you're about to reveal (specific detail, contradiction, or consequence). "
        "Vary the wording every time. Example for habits topic: 'The second one's the one everybody skips.' "
        "Example for money psychology topic: 'This is why you sabotage yourself.' Tie it to THIS topic's idea, never reuse.\n"
        "- the SECOND-TO-LAST segment loops back to the opening hook (seamless rewatch).\n"
        "- Segment 6 (LAST): write a UNIQUE call-to-follow line tailored to THIS SPECIFIC TOPIC. "
        "NEVER repeat the same closing sentence across different videos. "
        "Options: 'Want to stop wasting your paycheck? Follow for more.' or 'Ready to think like the wealthy? Follow.' "
        "or 'Stop leaving money on the table. Follow for the real moves.' "
        "Make it feel like a direct consequence of the topic, not a template.\n"
        "- Write for TEXT-TO-SPEECH voiceover: short, punchy sentences with natural spoken rhythm. "
        "Use contractions ('don't', 'you're', 'that's'). Direct 'you' address. Simple words. "
        "Avoid long flowing clauses that sound flat or robotic when read aloud. "
        "No hype, no exclamation spam. Conversational, not lecturing.\n"
        "- every idea passes the 'I want to screenshot this' test.\n"
        "- each 'keywords': 1-3 ENGLISH words for real Pexels footage that VISUALLY MATCHES the idea "
        "(concrete and topic-locked: e.g. 'city skyline night', 'businessman walking', 'coins stacking', "
        "'luxury car', 'person reading book', 'sunrise window' - never abstract like 'success').\n"
        "- CRITICAL: teach PRINCIPLES and PSYCHOLOGY only. Do NOT give specific financial or investment "
        "advice, do NOT name any stock, crypto, fund, or product, do NOT promise returns, do NOT invent "
        "statistics or numbers. Keep claims timeless and widely accepted.\n"
        "- description: one engaging sentence summarizing the topic + a UNIQUE, topic-specific call-to-follow line. "
        "NEVER use the exact same closing sentence across different videos. Examples: "
        "'Follow to become the investor you always wanted to be.' or 'Follow before you leave money on the table.' "
        "or 'Follow if you're ready to stop self-sabotaging with money.' "
        "Make the closing feel like a natural consequence of that specific topic, not a reusable template. "
        "Optional ONE emoji at the very END of the description only (never inside a segment text).\n"
        "- hashtags: 6-8 relevant tags including #shorts #fyp.\n"
        f"- Do NOT reuse these existing titles: {existing_titles}\n"
        "Return ONLY the JSON array."
    )


def call_model(user_text):
    r = requests.post(
        BASE.rstrip("/") + "/chat/completions",
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
        json={"model": MODEL, "temperature": 0.95,
              "messages": [{"role": "system", "content": SYSTEM},
                           {"role": "user", "content": user_text}]},
        timeout=180,
    )
    if r.status_code >= 400:
        raise RuntimeError(f"Models API {r.status_code}: {r.text[:500]}")
    return r.json()["choices"][0]["message"]["content"]


def extract_json(s):
    s = s.strip()
    s = re.sub(r"^```(?:json)?", "", s).strip()
    s = re.sub(r"```$", "", s).strip()
    a, b = s.find("["), s.rfind("]")
    if a != -1 and b != -1:
        s = s[a:b + 1]
    return json.loads(s)


def valid(t):
    if not isinstance(t, dict) or "title" not in t or "segments" not in t:
        return False
    if not isinstance(t["segments"], list) or len(t["segments"]) < 4:
        return False
    for seg in t["segments"]:
        if "text" not in seg or "keywords" not in seg:
            return False
    t.setdefault("description", t["title"] + " Follow to unlock your wealth potential.")
    t.setdefault("hashtags", ["#moneymindset", "#wealth", "#mindset", "#shorts", "#fyp"])
    return True


def main():
    if not TOKEN:
        print("CHYBA: chyba MODELS_TOKEN/GITHUB_TOKEN"); sys.exit(1)
    bank = json.load(open(BANK, encoding="utf-8"))
    used = json.load(open(STATE, encoding="utf-8")) if os.path.exists(STATE) else []
    titles = {t["title"] for t in bank}
    unused = [t for t in bank if t["title"] not in used]
    need = TARGET - len(unused)
    if need <= 0:
        print(f"Banka OK: {len(unused)} nepouzitych tem."); return
    print(f"Generujem ~{need} novych tem cez {MODEL}...")
    items = extract_json(call_model(build_prompt(need + 3, sorted(titles))))
    added = 0
    for t in items:
        if not valid(t) or t["title"] in titles:
            continue
        bank.append(t); titles.add(t["title"]); added += 1
    json.dump(bank, open(BANK, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"Pridanych {added} tem. Banka ma {len(bank)} tem.")


if __name__ == "__main__":
    main()
