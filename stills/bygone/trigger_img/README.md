---
id: bygone-trigger-img-readme
title: 上传 Bygone 旧照
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
audience: [self, internal]
languages: [zh]
maturity: evolving
confidence: null
visibility: public
source_of_truth: site
filename_policy: entrypoint
created: '2026-11-05'
updated: '2026-11-05'
metadata_updated: '2026-11-05'
---

# 上传 Bygone 旧照

1. 在 GitHub Desktop 或 Working Copy 先同步最新 `main`，把本批照片保存到 `stills/bygone/trigger_img/`；也可[网页上传](https://github.com/fivsevn/fivsevn-roll/upload/main/stills/bygone/trigger_img)，保留原文件名即可。
2. 提交并推送到 `main`；每张照片成为一张卡片，新批次放在 Bygone 前面，不经过普通影集入口。
3. 等待 [Actions](https://github.com/fivsevn/fivsevn-roll/actions/workflows/build.yml) 成功，再看 [Bygone](https://roll.fivsevn.com/stills/bygone/)。

系统沿用 Bygone 的统一命名，自动取下一个序号、转为 WebP，不缩放图片。支持 JPG/JPEG、PNG、WebP、静态 GIF、HEIC/HEIF；动画会报错并保留原图。摄影图片使用 quality 95，PNG 和带透明通道的图片无损保存。

标题默认使用原文件名（不含扩展名），时间取上传提交的北京时间；之后可在 `site-data/bygone.json` 修改卡片标题和显示日期。

线上验证完成后自动清理本入口，不改 Git 历史；失败时保留原图，重跑和重复上传相同字节不会重复发图。网络临时失败可重跑；坏图修复并同步到 `main` 后，在 Run workflow 勾选 `import_bygone` 补发未处理图片，旧 run 仍读取原坏图快照。

需要整理已转换旧图的历史时，手动 Run workflow 勾选 `compact_image_history`（默认关闭）；维护后本地副本须重新对齐最新 `main`，不要合并旧历史。

[发布与修改](../../README.md)
