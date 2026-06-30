#!/usr/bin/env python3
"""Hotove videa z output/ -> Cloudinary -> Buffer (naplanovane na presny cas 08/15/20 Bratislava)."""
import datetime
import json
import os
import sys
import time

import requests

ROOT = os.path.dirname(os.path.abspath(__file__))
BUFFER_API = "https://api.buffer.com"
PUSHED = os.path.join(ROOT, "pushed.json")
WANT_SERVICES = {"instagram", "tiktok", "youtube"}
YT_CATEGORY = "27"          # 27 = Education (sedi na peniaze/mindset); inak 22 People & Blogs, 24 Entertainment
CLOUD_FOLDER = "shorts"      # lubovolny nazov priecinka na Cloudinary
SLOT_HOURS = [8, 15, 20]


def next_slots(n):
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo("Europe/Bratislava")
    except Exception:
        tz = datetime.timezone(datetime.timedelta(hours=2))
    now = datetime.datetime.now(tz)
    out, day = [], 0
    while len(out) < n:
        for h in SLOT_HOURS:
            t = (now + datetime.timedelta(days=day)).replace(hour=h, minute=0, second=0, microsecond=0)
            if t > now:
                out.append(t.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"))
                if len(out) >= n:
                    break
        day += 1
    return out


def load_cfg():
    import appconfig
    return appconfig.load()


def gql(token, query, variables=None):
    r = requests.post(BUFFER_API,
                      headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                      json={"query": query, "variables": variables or {}}, timeout=60)
    data = r.json()
    if "errors" in data:
        raise RuntimeError(json.dumps(data["errors"], indent=2))
    return data["data"]


def upload_cloudinary(cfg, path):
    import cloudinary
    import cloudinary.uploader
    cloudinary.config(cloud_name=cfg["cloudinary_cloud_name"], api_key=cfg["cloudinary_api_key"],
                      api_secret=cfg["cloudinary_api_secret"], secure=True)
    public_id = os.path.splitext(os.path.basename(path))[0]
    res = cloudinary.uploader.upload_large(path, resource_type="video", folder=CLOUD_FOLDER,
                                           public_id=public_id, use_filename=True,
                                           unique_filename=False, overwrite=True)
    return res["secure_url"]


def build_mutation(service):
    base = "$channelId: ChannelId!, $text: String!, $url: String!, $dueAt: DateTime!"
    if service == "instagram":
        meta = "metadata: { instagram: { type: reel, shouldShareToFeed: true } }"; decl = base; use_title = False
    elif service == "youtube":
        meta = f'metadata: {{ youtube: {{ title: $title, categoryId: "{YT_CATEGORY}", privacy: public }} }}'
        decl = base + ", $title: String!"; use_title = True
    elif service == "tiktok":
        meta = "metadata: { tiktok: { title: $title } }"; decl = base + ", $title: String!"; use_title = True
    else:
        meta = ""; decl = base; use_title = False
    q = f"""
    mutation({decl}) {{
      createPost(input: {{
        channelId: $channelId, text: $text, schedulingType: automatic,
        mode: customScheduled, dueAt: $dueAt,
        assets: [{{ video: {{ url: $url }} }}], {meta}
      }}) {{ ... on PostActionSuccess {{ post {{ id }} }} ... on MutationError {{ message }} }}
    }}"""
    return q, use_title


def read_txt(txt_path):
    if not os.path.exists(txt_path):
        return "", ""
    lines = open(txt_path, encoding="utf-8").read().split("\n")
    return (lines[0].strip() if lines else ""), "\n".join(lines[1:]).strip()[:2000]


def load_pushed():
    if not os.path.exists(PUSHED):
        return {}
    data = json.load(open(PUSHED, encoding="utf-8"))
    if isinstance(data, list):
        return {name: sorted(WANT_SERVICES) for name in data}
    return data


def save_pushed(p):
    json.dump(p, open(PUSHED, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def create_post(token, service, channel_id, text, url, title, due):
    q, use_title = build_mutation(service)
    v = {"channelId": channel_id, "text": text, "url": url, "dueAt": due}
    if use_title:
        v["title"] = title
    last = ""
    for attempt in range(2):
        try:
            res = gql(token, q, v)["createPost"]
            if res.get("message"):
                last = res["message"]
            else:
                return True, ""
        except Exception as e:
            last = str(e)
        if attempt == 0:
            time.sleep(3)
    return False, last


def main():
    args = sys.argv[1:]
    dry = "--dry-run" in args
    nums = [a for a in args if a.isdigit()]
    n = int(nums[0]) if nums else 3

    cfg = load_cfg()
    token = cfg.get("buffer_token", "").strip()
    if not token:
        print("CHYBA: chyba buffer_token"); return
    targets = cfg.get("buffer_channels") or []
    print("Kanaly: " + (", ".join(f"{c['service']}({c.get('name','')})" for c in targets) or "(ziadne)"))
    if not targets:
        print("CHYBA: ziadne kanaly v configu (buffer_channels)."); return

    pushed = load_pushed()
    target_services = {c["service"].lower() for c in targets}
    out_dir = os.path.join(ROOT, "output")
    all_videos = sorted(f for f in os.listdir(out_dir) if f.endswith(".mp4"))
    todo = [v for v in all_videos if not target_services.issubset(set(pushed.get(v, [])))][:n]
    if not todo:
        print("Ziadne nove videa."); return

    if dry:
        for v in todo:
            print("  (dry-run)", v); return

    slots = next_slots(len(todo))
    for i, vid in enumerate(todo):
        due = slots[i]
        done = set(pushed.get(vid, []))
        pending = [c for c in targets if c["service"].lower() not in done]
        if not pending:
            continue
        mp4 = os.path.join(out_dir, vid)
        title, body = read_txt(mp4[:-4] + ".txt")
        title = title or "Daily"
        yt_title = (title + " #shorts")[:100]
        print(f"\n=== {vid} === (cas {due})")
        url = upload_cloudinary(cfg, mp4)
        for c in pending:
            svc = c["service"].lower()
            t = yt_title if svc == "youtube" else title
            ok, msg = create_post(token, svc, c["id"], body, url, t, due)
            if ok:
                done.add(svc); pushed[vid] = sorted(done); save_pushed(pushed)
                print(f"  [{svc}] do fronty OK")
            else:
                print(f"  [{svc}] CHYBA: {msg}")
    print("\nHOTOVO.")


if __name__ == "__main__":
    main()
