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

1. [选择本批照片](https://github.com/fivsevn/fivsevn-roll/upload/main/stills/bygone/trigger_img)，保留原文件名即可。
2. 提交到 `main`；每张照片成为一张卡片，新批次放在 Bygone 前面。
3. 等待 [Actions](https://github.com/fivsevn/fivsevn-roll/actions/workflows/build.yml) 成功，再看 [Bygone](https://roll.fivsevn.com/stills/bygone/)。

系统沿用 Bygone 的统一命名，自动取下一个序号、转为 WebP，不缩放图片。支持 JPG/JPEG、PNG、WebP、静态 GIF、HEIC/HEIF；动画会报错并保留原图。摄影图片使用 quality 95，PNG 和带透明通道的图片无损保存。

标题默认使用原文件名（不含扩展名），时间取上传提交的北京时间；之后可在 `site-data/bygone.json` 修改卡片标题和显示日期。推荐网页或直接调用 GitHub 的快捷指令上传；历史清理后，旧 Working Copy 副本请重新克隆，不要合并旧历史。

线上验证完成后自动清理本入口和已转换旧图的 `main` 历史；失败时保留原图，重跑和重复上传相同字节不会重复发图。手动补发可在 Run workflow 勾选 `import_bygone`。

[发布与修改](../../README.md)
