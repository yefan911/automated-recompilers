#!/usr/bin/env python3
"""Prepare release announcements and post through a configured project account."""

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen


class PostingError(RuntimeError):
    """A failure whose message is safe to write to public workflow logs."""


def request_json(url, payload=None, headers=None, method=None):
    request_headers = {"Accept": "application/json", "User-Agent": "automated-recompilers-announcements"}
    request_headers.update(headers or {})
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    request = Request(url, data=data, headers=request_headers, method=method)
    try:
        with urlopen(request, timeout=30) as response:
            return json.load(response)
    except HTTPError as error:
        # URLs and response bodies can contain webhook tokens or echoed secrets.
        raise PostingError(f"API request failed with HTTP {error.code}; check account configuration.") from None
    except (URLError, TimeoutError, OSError, ValueError):
        raise PostingError("API response could not be confirmed; check the workflow and destination.") from None


def https_origin(value):
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise PostingError("Account service must be an HTTPS origin without embedded credentials.")
    if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise PostingError("Account service must be an origin without a path, query, or fragment.")
    return value.rstrip("/")


def required(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise PostingError(f"Missing configuration: {name}.")
    return value


def github_headers():
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    return {"Authorization": f"Bearer {token}"} if token else {}


def load_release(repository, event_file=None, tag=None):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise PostingError("Repository must have the form owner/repository.")
    event = json.loads(Path(event_file).read_text(encoding="utf-8")) if event_file else {}
    if event.get("release") and not tag:
        release = event["release"]
    else:
        suffix = "tags/" + quote(tag, safe="") if tag else "latest"
        release = request_json(f"https://api.github.com/repos/{repository}/releases/{suffix}", headers=github_headers())
    url_prefix = f"https://github.com/{repository}/releases/tag/"
    if release.get("draft") or not release.get("published_at"):
        raise PostingError("Only published releases can be announced.")
    if not str(release.get("html_url", "")).startswith(url_prefix):
        raise PostingError("Release URL does not belong to this repository.")
    if not isinstance(release.get("id"), int) or not release.get("tag_name"):
        raise PostingError("Release is missing its ID or tag.")
    return release


def make_announcement(repository, release):
    tag = " ".join(str(release["tag_name"]).split())
    title = f"Automated Recompilers {tag}"
    url = release["html_url"]
    text = (
        f"{title}\n\nPrototype ROM-to-C pipeline for GBA, N64, PS1 and SNES.\n"
        f"Help improve CPU tests and compatibility reports.\n\n{url}"
    )
    if len(text) > 300:
        text = f"Automated Recompilers: new release.\nHelp improve CPU tests and compatibility reports.\n\n{url}"
    # Counting code points is conservative for Bluesky's grapheme limit.
    if len(text) > 300:
        raise PostingError("Release URL is too long for a 300-character announcement.")
    return {"repository": repository, "release_id": release["id"], "tag": tag,
            "published_at": release["published_at"], "release_url": url, "text": text}


def destination(provider):
    if provider == "bluesky":
        return https_origin(os.environ.get("BLUESKY_SERVICE", "https://bsky.social")) + "/" + required("BLUESKY_HANDLE")
    if provider == "mastodon":
        return https_origin(required("MASTODON_SERVER")) + "/" + required("SOCIAL_ACCOUNT")
    if provider == "discord":
        webhook = required("DISCORD_WEBHOOK_URL")
        parsed = urlsplit(webhook)
        match = re.fullmatch(r"/api/(?:v10/)?webhooks/(\d+)/[^/]+", parsed.path)
        if parsed.scheme != "https" or parsed.netloc != "discord.com" or not match or parsed.query or parsed.fragment:
            raise PostingError("Discord requires a discord.com incoming webhook URL.")
        return "discord-webhook:" + match.group(1)
    raise PostingError("Choose bluesky, mastodon, or discord as SOCIAL_PROVIDER.")


def reservation_path(state_dir, announcement, provider):
    account_hash = hashlib.sha256(destination(provider).encode("utf-8")).hexdigest()[:16]
    return Path(state_dir) / f"{announcement['release_id']}-{provider}-{account_hash}.json"


def reserve(state_dir, announcement, provider):
    path = reservation_path(state_dir, announcement, provider)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as handle:
            json.dump({"status": "reserved", "provider": provider, "release_id": announcement["release_id"]}, handle, indent=2)
    except FileExistsError:
        return False
    return True


def link_facets(text, url):
    text_bytes = text.encode("utf-8")
    start = text_bytes.index(url.encode("utf-8"))
    return [{"index": {"byteStart": start, "byteEnd": start + len(url.encode("utf-8"))},
             "features": [{"$type": "app.bsky.richtext.facet#link", "uri": url}]}]


def publish(announcement, provider):
    text = announcement["text"]
    if provider == "bluesky":
        service = https_origin(os.environ.get("BLUESKY_SERVICE", "https://bsky.social"))
        session = request_json(service + "/xrpc/com.atproto.server.createSession", {
            "identifier": required("BLUESKY_HANDLE"), "password": required("BLUESKY_APP_PASSWORD")})
        key = "release-" + hashlib.sha256(
            f"{announcement['repository']}:{announcement['release_id']}".encode("utf-8")).hexdigest()[:32]
        result = request_json(service + "/xrpc/com.atproto.repo.createRecord", {
            "repo": session["did"], "collection": "app.bsky.feed.post", "rkey": key,
            "record": {"$type": "app.bsky.feed.post", "text": text,
                       "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                       "facets": link_facets(text, announcement["release_url"])}},
            headers={"Authorization": "Bearer " + session["accessJwt"]})
        return {"provider": provider, "post_id": result["uri"]}
    if provider == "mastodon":
        result = request_json(https_origin(required("MASTODON_SERVER")) + "/api/v1/statuses",
            {"status": text, "visibility": "public", "language": "en"},
            headers={"Authorization": "Bearer " + required("MASTODON_ACCESS_TOKEN"),
                     "Idempotency-Key": f"{announcement['repository']}:{announcement['release_id']}"})
        return {"provider": provider, "post_id": result["id"]}
    if provider == "discord":
        result = request_json(required("DISCORD_WEBHOOK_URL") + "?" + urlencode({"wait": "true"}),
            {"content": text, "allowed_mentions": {"parse": []}})
        return {"provider": provider, "post_id": result["id"]}
    raise PostingError("Unsupported provider.")


def send_reserved(state_dir, announcement, provider):
    path = reservation_path(state_dir, announcement, provider)
    state = json.loads(path.read_text(encoding="utf-8"))
    if state.get("status") != "reserved":
        raise PostingError("This announcement is already processed; do not resend it.")
    try:
        receipt = publish(announcement, provider)
    except (PostingError, KeyError, ValueError) as error:
        state["status"] = "unconfirmed"
        path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        if isinstance(error, PostingError):
            raise
        raise PostingError("The posting API returned an unexpected response; inspect the destination before retrying.") from None
    state.update(receipt, status="posted")
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["preview", "reserve", "send"])
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY", "yefan911/automated-recompilers"))
    parser.add_argument("--event-file")
    parser.add_argument("--tag")
    parser.add_argument("--output", type=Path, default=Path("build/social/announcement.json"))
    parser.add_argument("--state-dir", type=Path, default=Path("social-state/receipts"))
    parser.add_argument("--provider", default=os.environ.get("SOCIAL_PROVIDER", ""))
    args = parser.parse_args(argv)
    try:
        if args.command == "preview":
            announcement = make_announcement(args.repository, load_release(args.repository, args.event_file, args.tag))
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(announcement, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(announcement["text"])
            summary = os.environ.get("GITHUB_STEP_SUMMARY")
            if summary:
                with Path(summary).open("a", encoding="utf-8") as handle:
                    handle.write("### Release announcement preview\n\n" + announcement["text"] + "\n")
        else:
            announcement = json.loads(args.output.read_text(encoding="utf-8"))
            if args.command == "reserve":
                reserved = reserve(args.state_dir, announcement, args.provider)
                output = os.environ.get("GITHUB_OUTPUT")
                if output:
                    with Path(output).open("a", encoding="utf-8") as handle:
                        handle.write(f"reserved={str(reserved).lower()}\n")
                print("Reserved announcement." if reserved else "Already reserved or posted; skipping.")
            else:
                send_reserved(args.state_dir, announcement, args.provider)
                print("Announcement published; receipt recorded.")
        return 0
    except (PostingError, OSError, ValueError, KeyError) as error:
        message = str(error) if isinstance(error, PostingError) else "Announcement input or state could not be read."
        print(message, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
