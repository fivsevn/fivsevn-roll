---
id: stills-publishing-readme
title: Stills 发布

module: stills
submodule: guide
topic: null

type: note
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
- zh

maturity: evolving
confidence: null

visibility: public
source_of_truth: site

filename_policy: entrypoint

created: null
updated: '2026-11-01'
metadata_updated: '2026-11-01'
---

# Stills 发布

1. [上传照片](https://github.com/fivsevn/fivsevn-roll/upload/main/stills/trigger_imgs)到 `stills/trigger_imgs/`，提交到 `main`。一次推送发布一组，默认标题为上传时间。
2. 等待 [Actions](https://github.com/fivsevn/fivsevn-roll/actions/workflows/build.yml) 成功，查看 [Stills](https://roll.fivsevn.com/stills/)。
3. 在 `stills/年/月/编号/index.md` 改标题、正文和 `extra.images` 图片顺序。保留 `id`、目录和 `extra.published_at`。

支持 JPG/JPEG、PNG、WebP、GIF。入口保留原文件名，发布包统一命名并保留原始字节。手机上传前先拉取最新 `main`，部署核验成功后自动清理入口原图。

隐藏用 `status: hidden`。给旧包加图时按[命名规则](https://github.com/fivsevn-agy/fivsevn-spec/blob/main/content/spec-content-media-naming-001.md)使用下一个序号，并加入 `extra.images`。

Bygone 独立维护 `stills/bygone/index.md` 和 `site-data/bygone.json`；未编排照片保存在 `drafts/stills/`。

手动补发入口图片，在 Actions 的 Run workflow 勾选 `import_stills`；只重建则不勾选。失败后修正并重跑，保留 `.publishing/stills.json`。
