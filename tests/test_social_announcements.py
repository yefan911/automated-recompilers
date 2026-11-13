"""Exercise posting isolation, repeat-run protection, and provider payloads offline."""

import json
from urllib.error import HTTPError

import pytest

from scripts import social_announcements as social


@pytest.fixture
def announcement():
    return social.make_announcement("yefan911/automated-recompilers", {
        "id": 123, "tag_name": "v0.2.0", "published_at": "2026-11-13T12:00:00Z",
        "html_url": "https://github.com/yefan911/automated-recompilers/releases/tag/v0.2.0"})


def test_preview_never_calls_posting_api(tmp_path, monkeypatch, capsys):
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"release": {
        "id": 123, "tag_name": "v0.2.0", "published_at": "2026-11-13T12:00:00Z",
        "html_url": "https://github.com/yefan911/automated-recompilers/releases/tag/v0.2.0",
        "body": "Unverified: every game works perfectly!"}}), encoding="utf-8")
    monkeypatch.setattr(social, "request_json", lambda *args, **kwargs: pytest.fail("Preview made a network request"))
    output = tmp_path / "preview.json"
    assert social.main(["preview", "--event-file", str(event), "--output", str(output)]) == 0
    text = json.loads(output.read_text(encoding="utf-8"))["text"]
    assert len(text) <= 300
    assert "every game" not in text
    assert "compatibility reports" in capsys.readouterr().out


@pytest.mark.parametrize("updates", [{"draft": True}, {"published_at": None},
    {"html_url": "https://github.com/other/repo/releases/tag/v1"}, {"id": "bad"}])
def test_release_validation_rejects_unpublished_or_wrong_repository(tmp_path, updates):
    release = {"id": 1, "tag_name": "v1", "published_at": "2026-11-13T12:00:00Z",
               "html_url": "https://github.com/yefan911/automated-recompilers/releases/tag/v1"}
    release.update(updates)
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"release": release}), encoding="utf-8")
    with pytest.raises(social.PostingError):
        social.load_release("yefan911/automated-recompilers", event)


def test_reservation_persists_and_distinguishes_destinations(announcement, tmp_path, monkeypatch):
    monkeypatch.setenv("BLUESKY_HANDLE", "project.bsky.social")
    assert social.reserve(tmp_path, announcement, "bluesky")
    assert not social.reserve(tmp_path, announcement, "bluesky")
    monkeypatch.setenv("BLUESKY_HANDLE", "another.bsky.social")
    assert social.reserve(tmp_path, announcement, "bluesky")


def test_successful_post_records_receipt_and_prevents_resending(announcement, tmp_path, monkeypatch):
    monkeypatch.setenv("BLUESKY_HANDLE", "project.bsky.social")
    calls = []
    monkeypatch.setattr(social, "publish", lambda *args: calls.append(args) or {"post_id": "at://record"})
    assert social.reserve(tmp_path, announcement, "bluesky")
    social.send_reserved(tmp_path, announcement, "bluesky")
    assert not social.reserve(tmp_path, announcement, "bluesky")
    with pytest.raises(social.PostingError):
        social.send_reserved(tmp_path, announcement, "bluesky")
    assert len(calls) == 1


def test_ambiguous_failure_is_not_automatically_retried(announcement, tmp_path, monkeypatch):
    monkeypatch.setenv("BLUESKY_HANDLE", "project.bsky.social")
    def fail(*args):
        raise social.PostingError("API response could not be confirmed.")
    monkeypatch.setattr(social, "publish", fail)
    assert social.reserve(tmp_path, announcement, "bluesky")
    with pytest.raises(social.PostingError):
        social.send_reserved(tmp_path, announcement, "bluesky")
    path = social.reservation_path(tmp_path, announcement, "bluesky")
    assert json.loads(path.read_text())["status"] == "unconfirmed"
    assert not social.reserve(tmp_path, announcement, "bluesky")


def test_http_failure_does_not_expose_webhook_or_response_body(monkeypatch):
    secret = "very-private-webhook-token"
    def fail(*args, **kwargs):
        raise HTTPError("https://discord.com/api/webhooks/123/" + secret, 403, secret, {}, None)
    monkeypatch.setattr(social, "urlopen", fail)
    with pytest.raises(social.PostingError) as failure:
        social.request_json("https://discord.com/api/webhooks/123/" + secret, {"content": "test"})
    assert secret not in str(failure.value)
    assert "403" in str(failure.value)


def test_discord_suppresses_mentions_and_confirms_delivery(announcement, monkeypatch):
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/123/secret")
    calls = []
    monkeypatch.setattr(social, "request_json", lambda *args, **kwargs: calls.append((args, kwargs)) or {"id": "456"})
    social.destination("discord")
    receipt = social.publish(announcement, "discord")
    args, _ = calls[0]
    assert args[0].endswith("?wait=true")
    assert args[1]["allowed_mentions"] == {"parse": []}
    assert receipt["post_id"] == "456"


def test_bluesky_uses_app_password_link_facets_and_stable_record_key(announcement, monkeypatch):
    monkeypatch.setenv("BLUESKY_HANDLE", "project.bsky.social")
    monkeypatch.setenv("BLUESKY_APP_PASSWORD", "private-app-password")
    announcement["text"] = "New release 🎮\n" + announcement["release_url"]
    calls = []
    def response(*args, **kwargs):
        calls.append((args, kwargs))
        return {"did": "did:plc:project", "accessJwt": "private-jwt"} if args[0].endswith("createSession") else {"uri": "at://record"}
    monkeypatch.setattr(social, "request_json", response)
    social.publish(announcement, "bluesky")
    social.publish(announcement, "bluesky")
    record = calls[1][0][1]
    assert record["rkey"] == calls[3][0][1]["rkey"]
    assert record["record"]["facets"][0]["index"]["byteStart"] == len("New release 🎮\n".encode("utf-8"))
    assert calls[0][0][1]["password"] == "private-app-password"
    assert calls[1][1]["headers"]["Authorization"] == "Bearer private-jwt"


def test_mastodon_uses_public_status_and_idempotency_key(announcement, monkeypatch):
    monkeypatch.setenv("MASTODON_SERVER", "https://mastodon.social")
    monkeypatch.setenv("MASTODON_ACCESS_TOKEN", "private-token")
    calls = []
    monkeypatch.setattr(social, "request_json", lambda *args, **kwargs: calls.append((args, kwargs)) or {"id": "456"})
    social.publish(announcement, "mastodon")
    args, kwargs = calls[0]
    assert args[0] == "https://mastodon.social/api/v1/statuses"
    assert args[1]["visibility"] == "public"
    assert kwargs["headers"]["Idempotency-Key"] == "yefan911/automated-recompilers:123"


@pytest.mark.parametrize("service", ["http://example.com", "https://token@example.com", "https://example.com/path"])
def test_account_services_reject_embedded_secrets_or_insecure_urls(service):
    with pytest.raises(social.PostingError):
        social.https_origin(service)


def test_discord_reservation_does_not_store_webhook_token(announcement, tmp_path, monkeypatch):
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/123/private-token")
    social.reserve(tmp_path, announcement, "discord")
    assert "private-token" not in next(tmp_path.iterdir()).read_text()
