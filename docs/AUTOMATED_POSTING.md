# Automated Project Announcements

The [Release Announcements workflow](../.github/workflows/social-announcements.yml) prepares a short post when a GitHub release is published. It can publish through one configured **Bluesky project account, Mastodon project account, or Discord channel webhook**. GitHub runs the workflow; your PC can be turned off.

The initial setup produces previews. Live posting starts when an account is connected and `SOCIAL_POSTING_ENABLED` is set to `true`. Account creation is a separate step: use a project identity you control and complete the platform's email/login verification. This repository does not create accounts or store login passwords.

## Announcement content

Each post names a published release, describes the project as a prototype, invites CPU tests and compatibility reports, and links to the release. It does not infer game playability from commit messages or claim that untested features work.

Example:

```text
Automated Recompilers v0.2.0

Prototype ROM-to-C pipeline for GBA, N64, PS1 and SNES.
Help improve CPU tests and compatibility reports.

https://github.com/yefan911/automated-recompilers/releases/tag/v0.2.0
```

## Connect an account

Open the repository's **Settings → Secrets and variables → Actions**. Put public account configuration in **Variables** and credentials in **Secrets**. Do not put credentials in an issue, commit, or chat message.

| Destination | Variables | Secrets |
| --- | --- | --- |
| Bluesky | `SOCIAL_PROVIDER=bluesky`, `BLUESKY_HANDLE=<project handle>`; optional `BLUESKY_SERVICE` (defaults to `https://bsky.social`) | `BLUESKY_APP_PASSWORD` |
| Mastodon | `SOCIAL_PROVIDER=mastodon`, `MASTODON_SERVER=<HTTPS instance origin>`, `SOCIAL_ACCOUNT=<project account handle>` | `MASTODON_ACCESS_TOKEN` |
| Discord | `SOCIAL_PROVIDER=discord` | `DISCORD_WEBHOOK_URL` |

- **Bluesky:** Create or use a project account, then generate an app password in that account's settings. Suggested display name: **Automated Recompilers**. Suggested bio: **Automated release updates for the experimental GBA/N64/PS1/SNES ROM-to-C project. Maintained by @yefan911.** Check handle availability during signup.
- **Mastodon:** Choose an instance and create or use a project account. Mark its profile as automated. In **Preferences → Development**, register an application with `write:statuses` and store its user access token.
- **Discord:** In a channel you manage, open **Edit Channel → Integrations → Webhooks**, create a webhook named **Automated Recompilers**, and copy its URL into the secret. A webhook does not require a separate Discord bot account. Posts suppress all mentions.

The workflow uses the repository's built-in `GITHUB_TOKEN` to maintain posting receipts. It needs permission to write the separate `social-posting-state` branch. If repository rules prohibit the Actions bot from creating/writing that branch, scope an exception to that branch before enabling delivery.

## Preview and enable

1. Open **Actions → Release Announcements → Run workflow** on `main`.
2. Enter an existing published release tag, or leave it blank for the latest stable release. Keep **Publish** unchecked.
3. Inspect the run summary and download `release-announcement-preview` to review the text.
4. Connect the account configuration above. Set the repository variable **`SOCIAL_POSTING_ENABLED=true`**.
5. Run the workflow again with the same release tag and **Publish** checked. Subsequent published releases will post automatically.

Creating a release is separate from posting: the workflow announces actual published releases and does not create releases. It does not post on every commit. Weekly digests and Reddit posting are not configured by this workflow.

To pause posting, set `SOCIAL_POSTING_ENABLED=false` or disable the workflow. Preview runs still work without social account credentials.

## Repeat runs and delivery failures

Before contacting a social API, the workflow reserves the release/destination pair in `social-posting-state/receipts`. That reservation is committed and pushed first. After a confirmed response, it records the returned post ID. Repeated runs skip an existing reservation, including after a timeout or runner interruption.

If a result is unconfirmed, check the account/channel and the failed run. If the post exists, retain the receipt. If it is definitely absent, remove the corresponding receipt on `social-posting-state` and rerun manually. The workflow does not automatically resend an ambiguous request. Keep the state branch so that old releases stay recorded.

Changing to another account creates a separate destination record. Disconnect old credentials when changing accounts. Social service responses and webhook URLs are not included in public error logs or receipt files.

## Local preview

```sh
python scripts/social_announcements.py preview --tag v0.1.0-beta
```

On this Windows development machine, use `py` in place of `python`. The result is written to `build/social/announcement.json`. Previewing a public release requires no social login. Offline tests exercise delivery payloads and failure handling without publishing:

```sh
python -m pytest -q tests/test_social_announcements.py
```

## API references

- [GitHub release and manual workflow events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows).
- [Bluesky post creation](https://docs.bsky.app/blog/create-post) and [UTF-8 link facets](https://docs.bsky.app/docs/advanced-guides/post-richtext).
- [Mastodon status publishing](https://docs.joinmastodon.org/methods/statuses/).
- [Discord incoming webhooks](https://discord.com/developers/docs/resources/webhook).
