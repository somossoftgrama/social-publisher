#!/usr/bin/env python3
"""Social Publisher - reads content/*.md and publishes to configured platforms."""

import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
import yaml

try:
    import httpx
except ImportError:
    print("Missing httpx. Run: pip install httpx pyyaml")
    sys.exit(1)


CONTENT_DIR = Path("content")
PUBLISHED_DIR = CONTENT_DIR / "published"


def parse_md(filepath: Path) -> dict | None:
    """Parse a markdown file with YAML frontmatter."""
    content = filepath.read_text(encoding="utf-8")
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", content, re.DOTALL)
    if not match:
        return None
    frontmatter = yaml.safe_load(match.group(1))
    body = match.group(2).strip()
    return {
        "date": frontmatter.get("date"),
        "platforms": frontmatter.get("platforms", []),
        "lang": frontmatter.get("lang", "en"),
        "body": body,
        "filepath": filepath,
    }


def post_to_x(post: dict) -> bool:
    """Post to X/Twitter via API v2."""
    api_key = os.environ.get("X_API_KEY")
    if not api_key:
        print("  ⏭️  X: no credentials configured")
        return False

    import hmac, hashlib, base64, urllib.parse, json

    # Split body into thread tweets (separated by ---)
    tweets = [t.strip() for t in re.split(r"\n---\n", post["body"]) if t.strip()]
    first = True

    for tweet in tweets:
        # Truncate to 280 chars for X
        text = tweet[:280]

        # For API v2 with OAuth 1.0a - using a simplified approach
        # We post via the v2 endpoint
        url = "https://api.twitter.com/2/tweets"
        
        # Simple OAuth 1.0a signature
        oauth_consumer_key = api_key
        oauth_consumer_secret = os.environ.get("X_API_SECRET", "")
        oauth_token = os.environ.get("X_ACCESS_TOKEN", "")
        oauth_token_secret = os.environ.get("X_ACCESS_TOKEN_SECRET", "")

        if not all([oauth_consumer_key, oauth_consumer_secret, oauth_token, oauth_token_secret]):
            print("  ⏭️  X: missing OAuth credentials")
            return False

        # Build OAuth signature
        nonce = base64.b64encode(os.urandom(32)).decode()[:32]
        timestamp = str(int(datetime.now().timestamp()))
        
        params = {
            "oauth_consumer_key": oauth_consumer_key,
            "oauth_nonce": nonce,
            "oauth_signature_method": "HMAC-SHA1",
            "oauth_timestamp": timestamp,
            "oauth_token": oauth_token,
            "oauth_version": "1.0",
        }
        
        # For POST requests, include body params in signature base
        body_json = json.dumps({"text": text})
        
        param_string = "&".join(
            f"{urllib.parse.quote(k)}={urllib.parse.quote(v)}"
            for k, v in sorted(params.items())
        )
        
        signature_base = "&".join([
            "POST",
            urllib.parse.quote(url, safe=""),
            urllib.parse.quote(param_string, safe=""),
        ])
        
        signing_key = f"{oauth_consumer_secret}&{oauth_token_secret}"
        signature = base64.b64encode(
            hmac.new(signing_key.encode(), signature_base.encode(), hashlib.sha1).digest()
        ).decode()
        
        params["oauth_signature"] = signature
        
        auth_header = "OAuth " + ", ".join(
            f'{k}="{urllib.parse.quote(v)}"' for k, v in sorted(params.items())
        )

        try:
            resp = httpx.post(
                url,
                content=body_json,
                headers={
                    "Authorization": auth_header,
                    "Content-Type": "application/json",
                },
                timeout=30,
            )
            if resp.status_code in (200, 201):
                print(f"  ✅ X: published tweet (first={first})")
                first = False
            else:
                print(f"  ❌ X: {resp.status_code} - {resp.text[:200]}")
                return False
        except Exception as e:
            print(f"  ❌ X: {e}")
            return False

    return True


def post_to_linkedin(post: dict) -> bool:
    """Post to LinkedIn."""
    access_token = os.environ.get("LINKEDIN_ACCESS_TOKEN")
    if not access_token:
        print("  ⏭️  LinkedIn: no credentials configured")
        return False

    # Get the user's LinkedIn URN
    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        # First get the user/profile ID
        me_resp = httpx.get(
            "https://api.linkedin.com/v2/userinfo",
            headers=headers,
            timeout=15,
        )
        if me_resp.status_code != 200:
            print(f"  ❌ LinkedIn me: {me_resp.status_code} - {me_resp.text[:200]}")
            return False

        user_data = me_resp.json()
        sub = user_data.get("sub", "")
        
        # Post as a share
        text = post["body"]
        # LinkedIn max ~3000 chars
        text = text[:3000]

        body = {
            "author": f"urn:li:person:{sub}",
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {
                        "text": text,
                    },
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC",
            },
        }

        resp = httpx.post(
            "https://api.linkedin.com/v2/ugcPosts",
            headers={**headers, "Content-Type": "application/json", "X-Restli-Protocol-Version": "2.0.0"},
            json=body,
            timeout=30,
        )
        if resp.status_code in (200, 201):
            print("  ✅ LinkedIn: published")
            return True
        else:
            print(f"  ❌ LinkedIn: {resp.status_code} - {resp.text[:200]}")
            return False
    except Exception as e:
        print(f"  ❌ LinkedIn: {e}")
        return False


def post_to_threads(post: dict) -> bool:
    """Post to Threads via Instagram API."""
    access_token = os.environ.get("THREADS_ACCESS_TOKEN")
    user_id = os.environ.get("THREADS_USER_ID")
    if not access_token or not user_id:
        print("  ⏭️  Threads: no credentials configured")
        return False

    text = post["body"]
    # Threads has a 500 char limit
    text = text[:500]

    try:
        # Step 1: Create media container
        container_resp = httpx.post(
            f"https://graph.threads.net/v1.0/{user_id}/threads",
            params={
                "media_type": "TEXT",
                "text": text,
                "access_token": access_token,
            },
            timeout=15,
        )
        if container_resp.status_code != 200:
            print(f"  ❌ Threads create: {container_resp.status_code} - {container_resp.text[:200]}")
            return False

        creation_id = container_resp.json().get("id")

        # Step 2: Publish the container
        pub_resp = httpx.post(
            f"https://graph.threads.net/v1.0/{user_id}/threads_publish",
            params={
                "creation_id": creation_id,
                "access_token": access_token,
            },
            timeout=15,
        )
        if pub_resp.status_code == 200:
            print("  ✅ Threads: published")
            return True
        else:
            print(f"  ❌ Threads publish: {pub_resp.status_code} - {pub_resp.text[:200]}")
            return False
    except Exception as e:
        print(f"  ❌ Threads: {e}")
        return False


def main():
    PUBLISHED_DIR.mkdir(parents=True, exist_ok=True)

    # Find all .md files in content/ (not in published/)
    md_files = sorted(CONTENT_DIR.glob("*.md"))
    if not md_files:
        print("📭 No posts to publish.")
        return

    now = datetime.now(timezone.utc)
    published_any = False

    for filepath in md_files:
        post = parse_md(filepath)
        if not post:
            print(f"⚠️  Skipping {filepath.name}: invalid frontmatter")
            continue

        post_date = post["date"]
        if not post_date:
            print(f"⚠️  Skipping {filepath.name}: no date")
            continue

        # Convert string date to datetime
        if isinstance(post_date, str):
            post_date = datetime.fromisoformat(post_date.replace("Z", "+00:00"))

        # Ensure timezone-aware for comparison
        if post_date.tzinfo is None:
            post_date = post_date.replace(tzinfo=timezone.utc)

        if post_date > now:
            continue  # Not yet time

        platforms = post["platforms"]
        if not platforms:
            print(f"⚠️  Skipping {filepath.name}: no platforms specified")
            continue

        print(f"\n📤 Publishing: {filepath.name}")
        print(f"   Date: {post_date}")
        print(f"   Platforms: {', '.join(platforms)}")

        success = True

        if "x" in platforms:
            if not post_to_x(post):
                success = False
        if "linkedin" in platforms:
            if not post_to_linkedin(post):
                success = False
        if "threads" in platforms:
            if not post_to_threads(post):
                success = False

        if success:
            # Move to published/
            dest = PUBLISHED_DIR / filepath.name
            filepath.rename(dest)
            print(f"   ✅ Moved to published/")
            published_any = True
        else:
            print(f"   ⏸️  Keeping in content/ (some publishes failed)")

    if not published_any:
        print("\n📭 No posts published this run.")


if __name__ == "__main__":
    main()
