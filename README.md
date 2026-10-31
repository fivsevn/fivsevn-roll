# roll.fivsevn

这里统一保存和发布 fivsevn 的照片与影像：[Stills 影集](https://roll.fivsevn.com/stills/) · [Motion 影像](https://roll.fivsevn.com/motion/)。

日常发布只需要上传照片，或编辑发布包里的 `index.md`。GitHub Actions 会整理内容、构建页面、部署到 GitHub Pages，并核对线上文件。页面样式、构建和内容组织方式延续 Flux、Savour、Fieldlog。

## Stills：一次推送，一组影集

### 上传新影集

1. 打开 [Stills 照片上传入口](https://github.com/fivsevn/fivsevn-roll/upload/main/stills/trigger_imgs)。
2. 一次选择这一组的全部照片。1 张也可以，多张也可以；文件名可以保留原样。
3. 提交到 `main`。提交说明可以写操作备注，网页标题会自动使用发布时间，例如 `31 Oct, 2026 17:04`。
4. 等待 [Build and deploy Roll](https://github.com/fivsevn/fivsevn-roll/actions/workflows/build.yml) 完成，再查看 [Stills](https://roll.fivsevn.com/stills/)。
5. 如需修改标题、照片顺序或补充文字，编辑自动生成的 `index.md`，再提交到 `main` 即可。

**一次 push 中新增或修改的照片，合起来生成一则发布。** GitHub 网页一次上传并提交，就是一组；若一次 Git push 包含多个提交，也会按这次推送最终新增或修改的照片合成一组。要发布两组影集，请分两次推送。自动导入只读取 `stills/trigger_imgs/`，不会把草稿目录或历史资源自动编排成帖子。

使用 Working Copy、手机快捷指令或本地 Git 时，仓库设为 `fivsevn/fivsevn-roll`，分支设为 `main`，照片保存到 `stills/trigger_imgs/`。每次上传前先拉取最新 `main`，因为发布机器人会把生成的发布包和处理记录提交回来。

### 自动生成什么

```text
stills/2026/10/2026-10-31-170400-<批次标识>/
├── index.md
└── assets/
    ├── 01.JPG
    ├── 02.JPG
    └── 03.JPG
```

- 一组对应一个 `index.md`，照片列在 `extra.images` 中。默认顺序按上传目录中的相对文件路径排序；想预先控制顺序，可命名为 `01`、`02`、`03` 等。
- 默认标题和归档年月来自这次上传提交的**提交时间**，统一使用 `Asia/Shanghai`，精确发布时间保存为带时区的 `extra.published_at`。它不是照片的 EXIF 拍摄时间。
- 文件夹名包含时间和批次标识，重复运行同一次发布不会再建一组，也不会覆盖已经编辑过的标题或正文。
- 原始照片的文件名、相对目录和文件字节保存在发布包的 `assets/` 中。较大的静态照片会在构建时另生成显示用 WebP；原图仍保留。
- 只有本组已公开部署且线上文件校验通过后，才会清理上传入口里仍与本次上传一致的文件；原始照片已保存在发布包的 `assets/`，不会丢失。失败、尚未验证或已经被改动的入口文件会保留。再次上传并推送照片会形成新的发布；修改已有影集请直接编辑已生成的发布包。

上传支持 **JPG/JPEG、PNG、WebP、GIF**，扩展名大小写不限，也可以使用中文文件名和子目录。HEIC/HEIF、TIFF、BMP 等请先导出为上述格式。图片会先做格式和内容校验；不符合要求的批次会停止，原文件保留。

### 修改标题、照片顺序和正文

找到该组的 `stills/YYYY/MM/<组名>/index.md`，点击编辑。元数据已经自动填好，保留其他字段即可。

**改标题：**修改已有的 `title`，不用改文件夹、`id` 或发布时间。

```yaml
title: 雨后的街角
```

**改照片顺序：**调整已有 `extra.images` 下的列表顺序。列表中只放本组需要展示的照片；`alt` 可以填写图片说明。

```yaml
  images:
    - file: assets/03.JPG
      alt: 雨后的街角
    - file: assets/01.JPG
      alt: 路边等车的人
    - file: assets/02.JPG
      alt: 暮色中的路口
```

网页只展示 `extra.images` 明确列出的照片；同一个 `assets/` 里未被列出的文件不会因此自动出现在页面上。要给已有影集增加照片，将文件上传到它的 `assets/`，再加入该列表。

**写正文：**在元数据结束的第二条 `---` 下方写文字。没有文字就留空。例如：

```markdown
这组照片拍于一个下雨的下午。

沿着熟悉的路走了一圈，记录下几处短暂的停留。
```

Stills 详情页的顺序是：**顶部导航 → 本组照片 → 正文 → 原有三语 Rights Notice**。首页的作品列表不显示正文。支持段落、粗体、链接、列表、标题、代码和表格；照片仍放在 `extra.images`，不在正文里另写 Markdown 图片。原始 HTML 按文本显示。

修改 `title`、正文或照片顺序不需要改 `id` 和 `extra.published_at`。保持这两个字段及目录不变，可以保留原来的页面地址。正常推送已有发布包的修改，只会更新这则发布，不会再生成一组。

### 草稿、Bygone 和分页

- **未编排的照片**放在 `drafts/stills/`。仓库是公开的，草稿文件也可以被直接访问，但不会进入网站、站点地图或自动发布流程。`stills/trigger_imgs/` 是发布入口，不是草稿箱。
- 已有发布包要暂时下线，可把 `status` 改为 `draft` 或 `hidden`，或把 `visibility` 改为 `private`。后续构建会移除它的网页和公开构建中的媒体；仓库里的文件仍保留。
- **Bygone 独立保存在 `stills/bygone/`**，不放入年月目录，也不走新影集上传入口。它是一整个照片集合，只有集合分页，没有每张照片的独立帖子。增加照片时还需要更新 `site-data/bygone.json` 中对应的显示资料。若为 Bygone 写正文，会在集合最后一页、权利声明之前显示一次。
- 普通 Stills 影集保留作品集的现有编排。每页数量由 `site-data/stills.json` 的 `page_size` 控制，目前是 30 组；未超过这个数量时不显示翻页按钮。超过后使用居中的数字和 `« / »`，详情页的 `viewfinder` 会返回包含该组的列表页。

### 手动补发与重跑

打开 [Actions → Build and deploy Roll](https://github.com/fivsevn/fivsevn-roll/actions/workflows/build.yml)，选择 **Run workflow**，分支使用 `main`。

- 勾选 `import_stills`：把上传入口里尚未处理的图片合成一组。普通图片 push 会自动处理，不需要再手动点一次。
- `import_stills` 和 `sync_youtube` 都不勾选：只重新构建已有内容；适合检查或重发已经编辑好的发布包。
- 同一个处理事件重复运行不会重复建组。`.publishing/stills.json` 保存处理记录，日常不要手动清空它。

如果工作流失败，先看失败步骤的提示。修正文件后再推送，或重新运行对应工作流；不要通过删除处理记录来重试。文件是否已经发布，以生成的发布包和工作流最后的线上校验结果为准。

## Motion：从 YouTube 自动同步

Motion 关联 [fivsevn 的 YouTube 频道](https://www.youtube.com/channel/UCIUoYaFm5uRLY9DEcdFG-VQ)。定时任务每小时自动检查一次新公开视频；想立即同步，可在 **Build and deploy Roll → Run workflow** 中勾选 `sync_youtube`。不需要手动上传视频，也不需要公开 API 密钥。

同步后保存为 `motion/YYYY/MM/YYYY-MM-DD-HHMMSS-<id>/index.md`，网站按视频发布时间从新到旧排列。后续同步会跳过已保存的视频，保留历史内容以及手动修改过的标题、正文和发布状态。

要写视频附言，就编辑对应 `index.md` 第二条 `---` 下面的正文。**Motion 首页和分页列表不显示附言，点进具体帖子后才显示**：文字位于 COMMENT FEED 顶部，用户名统一为 `guest_d`。这只是站内附言的显示名称，不会修改 YouTube 视频标题或频道名称。`LEAVE ROOM` 会返回原来的列表页和该条视频的位置，并尽量保持退出时的屏幕高度。

页面中的心形、既有评论和 “Drop a comment…” 保留原来的装饰形式，不是真正的在线评论提交框。

## 目录速查

```text
stills/trigger_imgs/            新影集的照片上传入口
stills/YYYY/MM/<组名>/          普通 Stills 发布包：index.md + assets/
stills/bygone/                 独立的 Bygone 历史影集
drafts/stills/                 未编排照片，不进入网站
motion/YYYY/MM/<时间>-<id>/     YouTube 影像发布包
.publishing/                   自动导入状态，不手动清空
site-data/                     展示顺序、分页数量、频道资料等
site-assets/                   相机与影集横幅、字体、样式和浏览行为
templates/                     页面模板和三语权利声明
migration/                     原始来源、校验值、迁移映射及报告
scripts/                       导入、构建、检查和线上验证工具
tests/                         自动测试
_site/                         自动生成的网站，不手动编辑、不提交
```

仓库按年月归档，网页地址仍是 `/stills/<组名>/`、`/motion/<id>/`；Bygone 使用 `/stills/bygone/`。移动旧归档的记录保存在 `migration/stills-paths.json` 和 `migration/motion-paths.json`。

## 本地检查与维护

日常上传不需要运行下面的命令。修改构建程序、模板或发布逻辑时，可以在本地检查：

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m unittest discover -s tests -v
node --test tests/test_motion_navigation.mjs
python scripts/build.py
python scripts/check.py
python -m http.server 8000 --directory _site
```

构建在依赖和图片齐备后可以离线进行；抓取 YouTube 与部署验证需要联网。项目子路径预览可给 `build.py` 和 `check.py` 都加上 `--base-path /fivsevn-roll`。

- **Check Roll**：检查 PR 和非 `main` 分支，生成可下载的预览文件，不部署。
- **Build and deploy Roll**：发布 `main`，保存新内容，部署后核对页面和媒体文件。GitHub Pages 的来源设为 **GitHub Actions**，自定义域名是 `roll.fivsevn.com`。
- **Archive reviewed Roll originals**：只用于最初迁移，不是日常发布入口。

`_site/build-receipt.json` 记录构建文件及 SHA-256 校验值。部署后工作流会执行线上校验；本地也可对同一份构建运行 `python scripts/verify_live.py --url https://roll.fivsevn.com`。构建通过与线上文件验证通过是两个不同步骤。

历史资源保留原始字节，迁移清单记录其校验值。修改这些已归档原图时，需要同步维护对应的迁移记录，否则完整性检查会提示差异。`scripts/restore_assets.py` 可按固定来源恢复缺失的历史资源，不会覆盖已经改变的文件。常规发布不依赖旧 assets 仓库或 WordPress。

详细迁移证据见 [migration/REPORT.md](migration/REPORT.md)。Roll 使用本地 `roll-post-v1` 扩展与核心元数据校验；原来的主站及其仓库不由此流程改动，原有三语 Rights Notice 继续保留。
