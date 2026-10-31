# Roll migration inventory

Captured on 31 October 2026 from the public WordPress API, all rendered Stills/Bygone/Motion pages, and the assets tree at `bb672ca6a2c446831eb8fb11c97a5e60b18f07f2`.

| Content | Archived result |
| --- | --- |
| Stills | 17 groups, 266 photographs |
| Bygone | 136 photographs in one collection, no per-photo pages |
| Motion | 66 existing posts; 66 distinct YouTube video IDs |
| Unconfirmed photographs | 91 originals in `drafts/stills/` |
| Other original Stills files | 10 empty placeholders and 3 Markdown files in drafts |
| Shared imagery | Camera, Bygone banner and Motion banner |
| Total asset-repository files | 509, each with source path, Git blob ID and SHA-256 |
| Fonts | 4 localized Courier Prime files, separately checksummed |

## Publication evidence

`source-posts.json` preserves public post IDs, status, original links, publication dates and exact image order. Stills evidence comprises all 17 posts in category 40206. Bygone includes both API pages (136 records) and all six rendered pagination pages. Motion includes all 66 records and all four rendered pagination pages. `site-data/history.json` preserves rendered order.

Every published photograph was matched by its full source path, not by basename or neighbouring files. Historical pinned image revisions were compared against main's blob hashes; all 402 matches were identical. No historical replacement or missing published file was found.

All 506 files under the source Stills directory are accounted for. A source file absent from public post content is marked `needs-review`, even when its directory contains published photographs. The original repository and its existing workflows remain untouched.

## Pending editorial review

The 91 draft photographs have no confirmed publication evidence in the audited Stills and Bygone pages. They remain unarranged. Their exact original paths are in `assets.json`; the main pending sets are Nantong city (32), familyday (13), urban candidshot2 (9), motionblur (8), acornerofhome (8), acroppedview (7), candidshot3 (6), urbanobjects (6), silhouette (3), and selfie (2).

“Unconfirmed” does not claim these were never shared on another service or in an unrelated article. No title, date, album order or permission decision has been inferred for them. Publication requires an explicitly edited content package.

## Presentation

Stills keeps the original camera image, `STILLS / ROLL_057`, viewfinder, load-roll typography and listing. Detail pages retain this header and the current roll row, then the ordered photographs and exact Rights Notice. The complete old `footer.rs` block is omitted from every new page at the user's request.

Rights Notice was extracted directly from the W Ren min Rd.(M) E page and visually checked against the supplied screenshot. `rights-notice.json` preserves all five paragraph strings; `templates/rights-notice.html` is their display source. Bygone retains its banner and presents only photographs, followed by the same notice.

Motion uses the legacy card markup and CSS. The comment feed, heart and input-looking strip were static decoration in the source HTML; no live comment service was present. YouTube remains an external player, so playback depends on YouTube access and video embedding permissions.

## Reference implementations

- [Flux README](https://github.com/fivsevn/fivsevn-flux/blob/main/README.md): Markdown packages, explicit publication controls, one artifact and live byte verification.
- [Savour build workflow](https://github.com/fivsevn/fivsevn-savour/blob/main/.github/workflows/build.yml): Python tests/build/check, GitHub Pages, archived images and safe bot commits.
- [Fieldlog deployment](https://github.com/fivsevn-agy/fivsevn-devlog/blob/main/.github/workflows/publish-pages.yml): shared metadata, original-image retention, build and post-deployment verification.
- [Existing YouTube reader](https://github.com/fivsevn/fivsevn-assets/blob/bb672ca6a2c446831eb8fb11c97a5e60b18f07f2/scripts/youtube_source.py): channel identity checks, full catalogue pagination, RSS/watch date verification and offline regression tests. Reader and tests are retained; the WordPress writer is not used.

The shared core metadata schema is retained unchanged. The upstream `site-post-v1` module restriction does not include Stills/Motion, so Roll declares `roll-post-v1` and validates its ordered-photo/video extension locally. No upstream repository was modified.
