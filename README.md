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

# Roll

[Stills](https://roll.fivsevn.com/stills/) 摄影与 [Motion](https://roll.fivsevn.com/motion/) 视频，共用本仓库与 GitHub Pages。

## 发布

- [Stills](stills/README.md)：照片上传到 `stills/trigger_imgs/`，一次推送发布一组。
- [Motion](motion/README.md)：视频上传到指定 YouTube 频道并公开，每小时自动同步。
- 修改旧内容：编辑对应发布包的 `index.md`。保留 `id`、目录和 `extra.published_at`；隐藏设 `status: hidden`。

| 内容 | 发布包 | 网页 |
|---|---|---|
| Stills | `stills/年/月/编号/` | `/stills/编号/` |
| Bygone | `stills/bygone/` | `/stills/bygone/` |
| Motion | `motion/年/月/时间-编号/` | `/motion/编号/` |

## 维护

- `drafts/stills/`：未编排原片，不自动发布。
- `templates/`、`site-assets/`：模板、样式和界面素材。
- `site-data/`：栏目配置、素材校验、排序和权利声明。
- `.publishing/`：照片批次与处理进度。
- `scripts/`、`schemas/`、`tests/`：发布、构建和校验。
- `_site/`：构建结果，不提交。

[Build and deploy Roll](https://github.com/fivsevn/fivsevn-roll/actions/workflows/build.yml) 负责主分支发布和每小时视频同步，定时检查无网页变化时跳过部署；`Check Roll` 检查其他分支与 PR。部署核验成功后自动清理匹配的图片入口原件。失败查看对应步骤后重跑；不要清空发布进度。

```sh
pip install -r requirements.txt
python -m unittest discover -s tests
node --test tests/test_motion_navigation.mjs
python scripts/build.py
python scripts/check.py
python -m http.server 8000 --directory _site
```
