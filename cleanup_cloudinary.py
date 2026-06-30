#!/usr/bin/env python3
"""Zmaze z Cloudinary videa starsie nez N dni (uz davno postnute). Drzi free tier volny."""
import datetime
import os
import cloudinary
import cloudinary.api
import appconfig

KEEP_DAYS = int(os.environ.get("CLOUDINARY_KEEP_DAYS", "14"))
CLOUD_FOLDER = "shorts"   # MUSI sediet s push_to_buffer.py

cfg = appconfig.load()
cloudinary.config(cloud_name=cfg["cloudinary_cloud_name"], api_key=cfg["cloudinary_api_key"],
                  api_secret=cfg["cloudinary_api_secret"], secure=True)
cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=KEEP_DAYS)


def parse(ts):
    return datetime.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")


def main():
    old, cursor = [], None
    while True:
        resp = cloudinary.api.resources(type="upload", resource_type="video",
                                        prefix=CLOUD_FOLDER + "/", max_results=500, next_cursor=cursor)
        for r in resp.get("resources", []):
            try:
                if parse(r["created_at"]) < cutoff:
                    old.append(r["public_id"])
            except Exception:
                pass
        cursor = resp.get("next_cursor")
        if not cursor:
            break
    if not old:
        print(f"Cloudinary: nic starsie nez {KEEP_DAYS} dni."); return
    for i in range(0, len(old), 100):
        cloudinary.api.delete_resources(old[i:i + 100], resource_type="video")
    print(f"Cloudinary: zmazanych {len(old)} starych videi.")


if __name__ == "__main__":
    main()
