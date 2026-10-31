"""Render text-only Motion commentary using the established Savour Markdown rules."""
from html import escape
from urllib.parse import urlparse

import markdown
from bs4 import BeautifulSoup


def render(body):
    """Return an HTML fragment; an empty body adds no comment-feed content."""
    if not body.strip():
        return ''
    rendered = markdown.markdown(
        escape(body.strip(), quote=False),
        extensions=['tables', 'fenced_code', 'sane_lists'],
    )
    fragment = BeautifulSoup(rendered, 'html.parser')
    if fragment.find('img'):
        raise ValueError('Motion commentary supports text and links; body images are not published')
    for link in fragment.select('a[href]'):
        if urlparse(link['href']).scheme not in {'', 'https', 'http', 'mailto'}:
            del link['href']
    return str(fragment)
