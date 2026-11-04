"""Author-facing Stills source format; never add these notes to the public page."""
from html import escape
import re
from urllib.parse import quote

from site_post_metadata import dump_frontmatter


LAYOUT_MARKER = '<!-- stills-layout: body-v1 -->'
USAGE_HEADER = (
    '# 操作：修改 title 和正文；移动正文图片引用可调整顺序。\n'
    '# 补图放本包 assets/，自动命名并补引用；保持 id、目录和发布时间不变。\n'
)


def image_reference(item):
    """Create a standalone local Markdown image without changing its alt text."""
    alt = escape(str(item.get('alt', '')).replace('\r', ' ').replace('\n', ' '), quote=False)
    alt = re.sub(r'([\\`*_{}\[\]()#+\-.!|>])', r'\\\1', alt)
    return f'![{alt}]({quote(item["file"], safe="/.-_~")})'


def compose_document(meta, body):
    """Keep the standard opening fence, with usage notes above the YAML fields."""
    frontmatter = dump_frontmatter(meta)
    return frontmatter.replace('---\n', '---\n' + USAGE_HEADER, 1) + body
