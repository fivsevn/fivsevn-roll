---
id: roll-readme
title: roll.fivsevn

module: system
submodule: roll
topic: null

type: index
status: active
canonical: true

summary: null

parents: []
related: []

tags: []

audience:
- self
- internal
languages:
- en

maturity: evolving
confidence: null

visibility: public
source_of_truth: site

filename_policy: entrypoint

created: null
updated: '2026-11-01'
metadata_updated: '2026-11-01'
---

# roll.fivsevn

Source for [Stills](https://roll.fivsevn.com/stills/) and [Motion](https://roll.fivsevn.com/motion/). Python builds a static GitHub Pages site from editable Markdown packages and local media. Roll owns its photography, unfinished photo archives, templates, and YouTube synchronization.

## Publish and edit

- [Stills publishing guide](stills/README.md) and [image upload entry](stills/trigger_imgs/README.md).
- [Motion publishing guide](motion/README.md).
- Edit an existing package's `index.md` to change its title, body, publication status, or image order. Keep its ID and publication instant stable.

| Content | Source | Public address |
|---|---|---|
| Stills album | `stills/YYYY/MM/<id>/index.md` with `assets/` | `/stills/<id>/` |
| Bygone collection | `stills/bygone/index.md`, `assets/`, `site-data/bygone.json` | `/stills/bygone/` and collection pagination |
| Motion room | `motion/YYYY/MM/YYYY-MM-DD-HHMMSS-<id>/index.md` | `/motion/<id>/` |

One push to `stills/trigger_imgs/` becomes one album, regardless of image count. The upload commit time in Asia/Shanghai supplies its initial title and `extra.published_at`. The importer reads the exact push snapshot, sorts uploaded paths, checks the complete batch, and saves the package and event ledger together. Replaying the event preserves later editorial changes. A later push creates a new album.

Motion checks the verified public uploads playlist of the configured YouTube channel every hour. It follows continuation pages and obtains evidenced publication dates before saving new rooms. Existing video IDs, including hidden records, prevent duplicate imports. Editing a saved room is independent of later YouTube title changes.

## Metadata and media

All five boards use the [shared site-post profile](https://github.com/fivsevn-agy/fivsevn-spec/blob/main/content/spec-content-site-post-001.md) and [publication media names](https://github.com/fivsevn-agy/fivsevn-spec/blob/main/content/spec-content-media-naming-001.md). Local copies of the helper and schemas support offline builds; CI checks them against spec.

Publication images are `YYYYMMDD-HHMMSS-<board>-<package-key>-NNN.ext`. The key is derived from the stable package ID; titles, image order and image bytes do not determine it. Stills preserves original bytes and creates display WebP derivatives only in `_site/`. Shared camera images, banners, fonts and unarranged original drafts retain their own names.

A public page requires both `visibility: public` and `status: active`, `publish`, or `published`. Draft and hidden packages remain saved but are excluded from website output. The source repository is public: these controls do not restrict access to source files.

## Rendering

Stills retains its camera header and portfolio list. Album details show `◁ viewfinder`, the selected roll, photos in `extra.images` order, optional Markdown body, then the rights notice. The camera returns to the main blog. The portfolio list has no redundant viewfinder. Stills pagination follows `site-data/stills.json`; a detail link returns to the appropriate list page.

Bygone stays independent of chronological albums. It has collection pagination without photo detail pages. Each collection page includes `◁ viewfinder` to return to Stills. Its displayed titles and dates come from `site-data/bygone.json`; they remain independent of media filenames. Optional collection notes appear once, after the final photo page and before the rights notice.

Motion lists video rooms without body text. Listings and details share a centered, viewport-fitted frame. The complete sample feed stays visible without internal scrolling on listings and details with no notes. Details remain stationary; authored notes scroll inside the comment feed only when the content exceeds its available space. Room details add authored Markdown as `guest_d` comments using the same natural spacing and typography as the existing feed. `LEAVE ROOM` restores the source list page and room position. The heart, sample comments, viewer count and comment input are part of the existing visual interface. Videos play through YouTube embeds; no video files or local thumbnails are downloaded.

## Build and deploy

`Build and deploy Roll` handles main-branch pushes, hourly YouTube checks, and manual runs. `Check Roll` validates pull requests and other branches without deployment.

1. Validate shared contracts, image names and behavioral tests.
2. Import the push's Stills batch or explicitly requested pending batch; synchronize YouTube on scheduled or requested runs.
3. Build a clean `_site/` using the configured Pages base path; check media hashes, ordering, links and publication boundaries.
4. Save generated packages and upload state without overwriting concurrent branch changes.
5. Deploy the artifact and verify all public files against the build receipt.
6. Remove only inbox originals that still match the verified upload and saved package.

Failures preserve matching upload inputs for a later successful run. `.publishing/stills.json` records event identities and file digests; do not clear it to retry. Manual runs with neither import option rebuild saved content. `sync_youtube` requests immediate video discovery; `import_stills` explicitly publishes pending inbox images as one batch.

GitHub Pages uses the Actions deployment source and `CNAME` specifies `roll.fivsevn.com`. YouTube channel identity is in `site-data/youtube.json`; `YOUTUBE_FIVSEVN_CHANNEL_ID` may override it through Actions Secrets. There is no WordPress credential or API dependency.

## Development

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m unittest discover -s tests -v
node --test tests/test_motion_navigation.mjs
python scripts/site_post_metadata.py check --site stills --root stills --schema-dir schemas
python scripts/site_post_metadata.py check --site motion --root motion --schema-dir schemas
python scripts/media_naming.py check --site stills --root stills
python scripts/build.py
python scripts/check.py
python -m http.server 8000 --directory _site
```

Use the same `--base-path /fivsevn-roll` on build and check for a project-path preview. `scripts/verify_live.py --url https://roll.fivsevn.com` verifies a deployment against the current build receipt.

| Path | Purpose |
|---|---|
| `templates/`, `site-assets/` | Layout, styles, fonts and browser navigation |
| `site-data/` | Portfolio configuration, collection cards, video channel, stable ordering, rights text and retained-file checksums |
| `drafts/stills/` | Unarranged original material, excluded from all website output and imports |
| `.publishing/` | Durable upload ledger |
| `scripts/`, `schemas/`, `tests/` | Import, build, validation and regression coverage |
| `_site/` | Generated deployment artifact; never edit or commit |

`site-data/originals.json` checks retained file paths, sizes and SHA-256 values. Deliberate replacements of covered files require matching checksum updates. Normal uploads and builds run entirely from this repository's current source.
