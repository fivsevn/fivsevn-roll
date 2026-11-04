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
updated: '2026-11-05'
metadata_updated: '2026-11-05'
---

# Stills 发布

1. [上传照片](https://github.com/fivsevn/fivsevn-roll/upload/main/stills/trigger_imgs)到 `stills/trigger_imgs/`，提交到 `main`。一次推送的照片合为一组；分两组就分两次推送。
2. 等待 [Build and deploy Roll](https://github.com/fivsevn/fivsevn-roll/actions/workflows/build.yml) 完成，再看 [Stills](https://roll.fivsevn.com/stills/)。初始标题自动使用这次上传的北京时间。
3. 修改已生成的 `stills/YYYY/MM/<id>/index.md`：`title` 改标题，`extra.images` 调整顺序，第二条 `---` 下写正文。正文显示在照片与权利声明之间。

上传时可保留原文件名，支持 JPG/JPEG、PNG、WebP、GIF。保存到发布包时会自动统一命名，原始字节保留。手机上传推荐网页或直接调用 GitHub 的快捷指令；Bygone 历史清理后，旧本地副本请重新克隆，不要合并旧历史。

保持 `id`、目录和 `extra.published_at` 不变。改顺序不用重命名照片；给已有包加图时按[命名规则](https://github.com/fivsevn-agy/fivsevn-spec/blob/main/content/spec-content-media-naming-001.md)使用下一个序号，并加入 `extra.images`。隐藏用 `status: hidden` 或 `draft`。

Bygone 使用独立的[旧照上传入口](bygone/trigger_img/README.md)，自动命名、转 WebP 并加入集合，不通过普通影集入口发布。照片列表在 `stills/bygone/index.md`，卡片标题和日期在 `site-data/bygone.json`。未编排照片放 `drafts/stills/`，不会自动展示。

失败先看 Actions 的失败步骤，修正后重跑；不要清空 `.publishing/stills.json` 或 `.publishing/bygone.json`。只有线上文件验证成功后，上传入口的对应原图才会清理。手动补发普通影集入口剩余图片时，在 Run workflow 勾选 `import_stills`；Bygone 用 `import_bygone`；只重建则上传与同步选项都不勾选。
