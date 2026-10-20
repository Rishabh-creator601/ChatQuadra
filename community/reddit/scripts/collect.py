"""Collect recent posts and comments from the type subreddits via the Arctic Shift archive.

Reddit's own endpoints require login, so we read the public Arctic Shift archive
(https://arctic-shift.photon-reddit.com). Usernames are replaced with a salted hash at
download time and never written to disk. Output goes to community/reddit/raw/ (gitignored).

Usage:  python -P community/reddit/scripts/collect.py [--comments 3000] [--posts 600] [--only ESTJ ...]
"""
import argparse
import hashlib
import json
import secrets
import time
from pathlib import Path

import requests

API = "https://arctic-shift.photon-reddit.com/api"
TYPES = ["INTJ", "INTP", "ENTJ", "ENTP", "INFJ", "INFP", "ENFJ", "ENFP",
         "ISTJ", "ISFJ", "ESTJ", "ESFJ", "ISTP", "ISFP", "ESTP", "ESFP"]
SUBREDDITS = TYPES + ["mbti"]
MAX_AGE_DAYS = 730
BOTS = {"AutoModerator", "[deleted]", "sneakpeekbot", "RemindMeBot", "B0tRank"}
FIELDS = {
    "comments": "id,author,author_flair_text,body,score,created_utc,link_id,parent_id",
    "posts": "id,author,author_flair_text,title,selftext,score,num_comments,created_utc,link_flair_text",
}

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "raw"
SESSION = requests.Session()
SESSION.headers["User-Agent"] = "chatquadra-research/0.1 (persona style study)"


def salt() -> str:
    path = RAW / ".salt"
    if not path.exists():
        path.write_text(secrets.token_hex(16))
    return path.read_text().strip()


def get(kind: str, subreddit: str, before: int | None) -> list[dict]:
    params = {"subreddit": subreddit, "limit": 100, "sort": "desc", "fields": FIELDS[kind]}
    if before:
        params["before"] = before
    for attempt in range(6):
        try:
            r = SESSION.get(f"{API}/{kind}/search", params=params, timeout=60)
            if r.status_code == 200:
                return r.json().get("data") or []
            print(f"  {subreddit} {kind}: HTTP {r.status_code}, retrying")
        except (requests.RequestException, ValueError) as e:
            print(f"  {subreddit} {kind}: {e.__class__.__name__}, retrying")
        time.sleep(2 ** attempt)
    return []


def clean(item: dict, kind: str, subreddit: str, pepper: str) -> dict | None:
    author = item.get("author") or "[deleted]"
    if author in BOTS or author.lower().endswith("bot"):
        return None
    text = item.get("body") if kind == "comments" else item.get("selftext") or ""
    if (text or "").strip() in {"[deleted]", "[removed]"}:
        text = ""
    if kind == "comments" and not text.strip():
        return None
    out = {
        "id": item["id"],
        "sub": subreddit,
        "kind": kind[:-1],
        "author_hash": hashlib.sha256((pepper + author).encode()).hexdigest()[:16],
        "flair": (item.get("author_flair_text") or "").strip(),
        "score": item.get("score"),
        "created_utc": int(item.get("created_utc") or 0),
        "text": text,
    }
    if kind == "posts":
        out["title"] = item.get("title") or ""
        out["num_comments"] = item.get("num_comments")
        out["post_flair"] = item.get("link_flair_text")
    else:
        out["is_top_level"] = (item.get("parent_id") or "").startswith("t3_")
    return out


def collect(kind: str, subreddit: str, target: int, pepper: str) -> int:
    path = RAW / f"{kind}_{subreddit}.jsonl"
    cutoff = int(time.time()) - MAX_AGE_DAYS * 86400
    seen, before, kept = set(), None, 0
    with path.open("w", encoding="utf-8") as f:
        while kept < target:
            batch = get(kind, subreddit, before)
            if not batch:
                break
            for item in batch:
                if item["id"] in seen:
                    continue
                seen.add(item["id"])
                row = clean(item, kind, subreddit, pepper)
                if row:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
                    kept += 1
            oldest = min(int(x.get("created_utc") or 0) for x in batch)
            if oldest < cutoff or oldest == before:
                break
            before = oldest
            time.sleep(1.0)
    print(f"{subreddit:>5} {kind:<8} {kept}")
    return kept


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--comments", type=int, default=3000)
    ap.add_argument("--posts", type=int, default=600)
    ap.add_argument("--only", nargs="*", help="subset of subreddits")
    args = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    pepper = salt()
    for sub in args.only or SUBREDDITS:
        collect("comments", sub, args.comments * (2 if sub == "mbti" else 1), pepper)
        collect("posts", sub, args.posts, pepper)


if __name__ == "__main__":
    main()
