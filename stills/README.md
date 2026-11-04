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

1. 在 GitHub Desktop 或 Working Copy 先同步最新 `main`，把本组照片保存到 `stills/trigger_imgs/`，提交并推送；也可[网页上传](https://github.com/fivsevn/fivsevn-roll/upload/main/stills/trigger_imgs)。一次推送的照片合为一组；分两组就分两次推送。
2. 等待 [Build and deploy Roll](https://github.com/fivsevn/fivsevn-roll/actions/workflows/build.yml) 完成，再看 [Stills](https://roll.fivsevn.com/stills/)。初始标题自动使用这次上传的北京时间。
3. 修改已生成的 `stills/YYYY/MM/<id>/index.md`：`title` 改标题；第二条 `---` 下移动独立一行的 `![说明](assets/文件名)` 与文字段落即可排版。删除图片引用可取消展示，原图保留；`extra.images` 由程序维护，顶部操作注释不显示在网页。

上传时可保留原文件名，支持 JPG/JPEG、PNG、WebP、GIF。保存到发布包时会自动统一命名，原始字节保留。

保持 `id`、目录和 `extra.published_at` 不变，改顺序不用重命名照片。给已有影集加图时，放入本包 `assets/` 后提交推送，程序会按[命名规则](https://github.com/fivsevn-agy/fivsevn-spec/blob/main/content/spec-content-media-naming-001.md)自动命名并在正文末尾补引用；若已在正文所需位置引用原文件名，会就地更新路径。现有照片名称和原始字节保留。隐藏用 `status: hidden` 或 `draft`。

Bygone 使用独立的[旧照上传入口](bygone/trigger_img/README.md)，自动命名、转 WebP 并加入集合，不通过普通影集入口发布。照片列表在 `stills/bygone/index.md`，卡片标题和日期在 `site-data/bygone.json`。未编排照片放 `drafts/stills/`，不会自动展示。

网络等临时失败可重跑；坏图修复并同步到 `main` 后，在 Run workflow 勾选 `import_stills`（Bygone 用 `import_bygone`）补发未处理图片，旧 run 仍读取原坏图快照。普通影集同次手动补发的未处理图片合为一组；若修复推送已自动发布部分图片，手动只补余图，不会重新合并已发布组。

不要清空 `.publishing/stills.json` 或 `.publishing/bygone.json`；只重建则上传与同步选项都不勾选。

日常仅在线上验证成功后清理入口对应原图，不改 Git 历史。需要整理历史时，手动 Run workflow 勾选 `compact_image_history`（默认关闭）；维护后本地副本须重新对齐最新 `main`，不要合并旧历史。
