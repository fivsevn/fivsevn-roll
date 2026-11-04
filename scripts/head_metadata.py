"""Build search and sharing tags without changing authored page content."""
from html import escape
import re

from bs4 import BeautifulSoup


def compact_text(value, fallback=''):
    text = re.sub(r'\s+', ' ', str(value or fallback)).strip()
    return text if len(text) <= 160 else text[:159].rstrip() + '…'


def metadata_head(title, description, canonical, *, site_name, image=None, image_alt='', article=False, noindex=False):
    description = compact_text(description, title)
    values = [
        ('name', 'description', description),
        ('property', 'og:title', title),
        ('property', 'og:description', description),
        ('property', 'og:url', canonical),
        ('property', 'og:type', 'article' if article else 'website'),
        ('property', 'og:site_name', site_name),
        ('name', 'twitter:card', 'summary_large_image' if image else 'summary'),
        ('name', 'twitter:title', title),
        ('name', 'twitter:description', description),
    ]
    if image:
        values.extend([('property', 'og:image', image), ('name', 'twitter:image', image)])
        if image_alt:
            values.extend([('property', 'og:image:alt', image_alt), ('name', 'twitter:image:alt', image_alt)])
    if noindex:
        values.append(('name', 'robots', 'noindex, follow'))
    return '<link rel="canonical" href="' + escape(canonical, quote=True) + '">' + ''.join(
        f'<meta {attribute}="{name}" content="{escape(str(value), quote=True)}">'
        for attribute, name, value in values
    )


def add_missing_metadata(document, metadata):
    """Add missing tags to a retained head while keeping every body byte intact."""
    match = re.search(r'<head\b[^>]*>(.*?)</head\s*>', document, re.I | re.S)
    if not match:
        return document
    existing = BeautifulSoup(match.group(1), 'html.parser')
    additions = []
    for tag in BeautifulSoup(metadata, 'html.parser').find_all(['meta', 'link']):
        if tag.name == 'link':
            present = existing.select_one('link[rel~="canonical"]')
        else:
            attribute = 'name' if tag.has_attr('name') else 'property'
            present = any(str(item.get(attribute, '')).lower() == tag[attribute].lower() for item in existing.find_all('meta'))
        if not present:
            additions.append(str(tag))
    return document[:match.end(1)] + ''.join(additions) + document[match.end(1):]

