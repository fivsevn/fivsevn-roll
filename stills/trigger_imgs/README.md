---
id: stills-trigger-imgs-readme
title: 上传影集

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

# 上传影集

1. [选择本组全部照片](https://github.com/fivsevn/fivsevn-roll/upload/main/stills/trigger_imgs)，保留原文件名即可。
2. 提交到 `main`；一次推送就是一则影集。1 张或多张都可以。
3. 等待 [Actions](https://github.com/fivsevn/fivsevn-roll/actions/workflows/build.yml) 成功，再看 [Stills](https://roll.fivsevn.com/stills/)。

标题默认使用发布时间，之后在 `stills/YYYY/MM/<id>/index.md` 修改标题和正文；正文中的图片引用与段落顺序就是影集排版，`extra.images` 由程序维护。顶部注释说明操作，不显示在网页。照片自动统一命名并保留原始字节。支持 JPG/JPEG、PNG、WebP、GIF；手机上传前先拉取最新 `main`。

给已有影集加图请放入该包的 `assets/`，不要再次放到本入口。提交推送后自动命名并在正文末尾补引用；已写入正文的原文件名引用会就地更新，可再移动到所需位置。

线上验证完成后自动清理本入口；失败时保留图片，重跑不会重复建组。未编排照片放 `drafts/stills/`。

[发布与修改](../README.md)
