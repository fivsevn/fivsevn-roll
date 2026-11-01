---
id: motion-publishing-readme
title: Motion 发布

module: motion
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

# Motion 发布

视频发到 [YouTube 频道](https://www.youtube.com/channel/UCIUoYaFm5uRLY9DEcdFG-VQ)并设为公开即可。每小时自动检查；立即同步可到 [Build and deploy Roll](https://github.com/fivsevn/fivsevn-roll/actions/workflows/build.yml) → Run workflow，勾选 `sync_youtube`。

同步后在 `motion/YYYY/MM/<时间>-<id>/index.md` 修改标题或写正文。正文只在详情页的评论区显示，署名 `guest_d`，列表页不显示。保持 `id`、目录和 `extra.published_at` 不变。

隐藏用 `status: hidden` 或 `draft`。YouTube 删除或转私密不会自动撤下已保存的帖子，需要同时处理对应 `index.md`。后续同步不会覆盖已有标题、正文或隐藏决定。

[查看 Motion](https://roll.fivsevn.com/motion/)
