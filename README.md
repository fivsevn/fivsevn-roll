# roll.fivsevn

Roll collects the photographs and moving images of [fivsevn.com](https://fivsevn.com/). Its public sections are [Stills](https://roll.fivsevn.com/stills/) and [Motion](https://roll.fivsevn.com/motion/).

The repository follows Flux, Savour and Fieldlog's publishing pattern: editable Markdown packages, local schemas, an offline Python build, GitHub Actions, GitHub Pages, and checksum verification after deployment. One Stills package is **one ordered group of photographs**, not one post per image.

## Repository layout

```text
stills/YYYY/MM/<group>/index.md  Metadata and ordered photo list
stills/YYYY/MM/<group>/assets/   Original filenames and original bytes
stills/2026/06/bygone/           One photo collection; no per-photo posts
drafts/stills/               Unarranged originals, excluded from the website
motion/YYYY/MM/<timestamp>-<id>/index.md  YouTube entries by publication time
site-assets/                 Local camera/banner images, fonts and CSS
templates/                   Retained legacy layout and exact Rights Notice
site-data/                   Legacy display order and verified channel identity
migration/                   Source URLs, pinned revisions, hashes and inventory
scripts/                     Build, check, sync and verification commands
tests/                       Draft isolation, rerun and YouTube identity tests
_site/                       Generated artifact; ignored by Git
```

`drafts/` is visible in this public repository, as agreed for the migration. It is never copied to `_site/`, listed in pages or the sitemap, or automatically published. No file is published merely because it shares a folder with a published photograph.

## Publish a photo group

1. Prepare a directory such as `stills/2026/11/2026-11-walk/` with one `index.md` and an `assets/` subdirectory.
2. Copy the intended photographs to `assets/`, retaining the original filenames. List only those photographs, in the intended order, under `extra.images`.
3. Use an existing group as the metadata template. Set a unique `id` matching the group directory name, a title, and a fixed timezone-aware `extra.published_at`. The archive year/month must match this publication time in Asia/Shanghai.
4. Set both `status: published` and `visibility: public` when the group is ready. `draft`, `hidden`, `private`, `internal`, or missing publication controls never imply publication.
5. Run the checks below, commit, and push to `main`. Review the Build and deploy Roll workflow and its live verification step.

For a three-photo group, the group-specific portion is:

```yaml
extra:
  profile: roll-post-v1
  published_at: '2026-11-01T18:00:00+08:00'
  author: 五月七日
  images:
    - file: assets/1.JPG
      alt: ''
    - file: assets/2.JPG
      alt: ''
    - file: assets/3.JPG
      alt: ''
```

The surrounding metadata uses the shared fivsevn core schema. The existing `site-post-v1` profile currently restricts modules to Flux, Savour and Fieldlog; Roll therefore uses an explicit local `roll-post-v1` extension with ordered images or video IDs, rather than changing the shared upstream repository or claiming compliance with a profile that excludes Roll.

The builder retains original photo bytes and creates WebP display derivatives in `_site/` for still images over 1600 pixels. Group photographs link to the original file. Bygone photographs have no links and no separate post pages. Editing `extra.images` changes the order; directory listing and filename order are never used to curate a group. Year/month folders only organize the repository: public `/stills/<group>/` pages and `/stills/<group>/assets/` addresses remain unchanged. `migration/stills-paths.json` records the archive moves.

Bygone retains the original photo cards, dates, captions and 27-card pagination. Reviewed card metadata lives in `site-data/bygone.json`; add its display metadata when adding a photograph to the collection. All Stills tabs use `roll.fivsevn/stills`, and Motion tabs use `roll.fivsevn/motion`. A Stills detail shows an expanded roll arrow and its viewfinder link returns to the Stills list.

To hide a saved package, change its status or visibility. A clean build removes its page, media, aliases and sitemap entry. Keep the package if it should remain recoverable. Editing the imported archive itself requires an intentional update to its corresponding migration checksum record; the integrity check otherwise reports the change.

## Motion and YouTube

Motion follows Savour and Fieldlog's dated archive layout: `motion/YYYY/MM/YYYY-MM-DD-HHMMSS-<id>/index.md`. The directory timestamp comes from the saved `extra.published_at` in Asia/Shanghai, so folder names sort chronologically; website pages display entries newest first. Folder moves preserve the original Markdown bytes, IDs and `/motion/<id>/` public links; `migration/motion-paths.json` records the original locations. Newly synced videos use the same layout. Stills keeps its existing portfolio grouping and display order.

The verified channel is [fivsevn](https://www.youtube.com/channel/UCIUoYaFm5uRLY9DEcdFG-VQ), ID `UCIUoYaFm5uRLY9DEcdFG-VQ`. This was checked against official channel HTML, official RSS and the existing assets-repository configuration on 31 October 2026.

The Pages workflow runs hourly at minute 17 UTC and supports manual runs. Scheduled runs import new public uploads, build, save packages, deploy, and verify the deployed bytes in the same run. Normal content pushes build saved packages without relying on YouTube availability. Select `sync_youtube` when manually requesting a refresh.

The reader checks the full public uploads catalogue, traverses continuation pages, validates channel ownership, and enriches exact publication dates from RSS, verified historical metadata and official video pages. It retains older saved entries even when YouTube no longer returns them. Duplicate IDs, reruns, hidden entries and manual title edits are preserved. A wrong channel, truncated catalogue, ambiguous date or network failure stops the run; it does not erase history.

No API key is required for the public source. The optional `YOUTUBE_FIVSEVN_CHANNEL_ID` GitHub Secret must match the reviewed ID. If an authenticated source is introduced later, use GitHub Secrets and keep credentials out of content and browser code. No WordPress password, WordPress write operation or old-site publishing workflow is used here.

The original Motion player, room frame, pagination, title links and decorative comment feed are retained. On the source page, the heart and “Drop a comment…” are decorative text, not a live comment form; this migration preserves that behavior. The new title links open local Motion detail pages.

Write optional Motion text in the body of its `index.md`, after the closing frontmatter `---`. Paragraphs, emphasis, headings, lists, links, code and tables are rendered as author messages at the top of COMMENT FEED, above the existing room comments. Empty bodies add no message. The publication time and saved author supply the message timestamp and name; there is no separate text database. The same text appears in the list and detail room. Motion detail pages show only the room, with LEAVE ROOM returning to `/motion/`.

## Build and verify

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m unittest discover -s tests -v
python scripts/build.py
python scripts/check.py
python -m http.server 8000 --directory _site
```

The build is offline after dependencies and archived assets are present. `check.py` verifies all retained asset hashes, local links, photo order, the exact five Rights Notice paragraphs, the absence of the removed `footer.rs` block, and draft exclusion including byte hashes. Tests also verify hidden-package exclusion and YouTube deduplication and failure handling.

A project-path preview can use `python scripts/build.py --base-path /fivsevn-roll`, followed by the same `--base-path` argument for `check.py`. Production reads the base path from GitHub Pages.

`_site/build-receipt.json` records the complete public file set and SHA-256 digests. After deployment, `python scripts/verify_live.py --url https://roll.fivsevn.com` compares the receipt and every page/media file with that build. A green build alone is not a verified public deployment.

## GitHub workflow

- **Check Roll** builds pull requests and non-main branches and saves a downloadable preview artifact. It cannot deploy.
- **Build and deploy Roll** is the production workflow. Pages must use **GitHub Actions** as its source, with `roll.fivsevn.com` as the custom domain. The workflow saves new video packages with a branch freshness check before publishing.
- **Archive reviewed Roll originals** is the one-time migration bootstrap, restricted to `codex/migrate-roll`. It downloads only files from the reviewed, pinned manifest, verifies every byte checksum, runs tests and builds, then commits originals and removes `migration/PENDING`. This allows the connected GitHub API to submit source code while Actions archives the large image collection. It is not an inbox and never classifies new uploads.

For disaster recovery, `python scripts/restore_assets.py` restores missing manifest files. Existing files must match their expected hashes; the command refuses to overwrite changed files. The regular production build does not depend on the old asset repository.

See [migration/REPORT.md](migration/REPORT.md) for inventory, evidence, reference implementations and remaining editorial review. The old domain and source repositories have not been changed. Original images retain their existing rights; the exact multilingual Rights Notice appears after photo content.
