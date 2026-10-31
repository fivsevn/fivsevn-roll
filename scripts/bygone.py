"""Render the original Bygone cards and pagination without individual post links."""
from copy import deepcopy
import json


def render_pages(root, post, rendered_photos, template):
    """Pair explicitly published photos with their captured source-page metadata."""
    config = json.loads((root / 'site-data/bygone.json').read_text())
    metadata = {card['file']: card for card in config['cards']}
    images = post['extra']['images']
    figures = rendered_photos.select('figure')
    if len(figures) != len(images):
        raise ValueError('Bygone rendered photo count does not match the published collection')
    missing = [image['file'] for image in images if image['file'] not in metadata]
    if missing:
        raise ValueError(f'Bygone cards need reviewed display metadata: {missing}')
    page_size = config['page_size']
    pages = max(1, (len(images) + page_size - 1) // page_size)

    def route(number):
        return '/stills/bygone/' if number == 1 else f'/stills/bygone/page/{number}/'

    result = []
    for number in range(1, pages + 1):
        page = template('bygone.html')
        listing = page.select_one('.wp-block-query ul.wp-block-post-template')
        start = (number - 1) * page_size
        for index in range(start, min(start + page_size, len(images))):
            record = metadata[images[index]['file']]
            card = template('bygone-card.html').li
            figure = deepcopy(figures[index])
            figure.img['loading'] = 'eager' if index == start else 'lazy'
            card.select_one('figure').replace_with(figure)
            card.select_one('.bygone-photo-title').string = record['title']
            stamp = card.select_one('time')
            stamp['datetime'] = record['published_at']
            stamp.string = record['display_date']
            if card.select('a'):
                raise ValueError('Bygone cards must not link to individual photos or posts')
            listing.append(card)

        navigation = page.select_one('.wp-block-query-pagination')

        def arrow(target, direction, glyph):
            link = page.new_tag('a', attrs={
                'href': route(target), 'aria-label': direction.title() + ' Page',
                'class': f'wp-block-query-pagination-{direction}',
            })
            icon = page.new_tag('span', attrs={
                'aria-hidden': 'true',
                'class': f'wp-block-query-pagination-{direction}-arrow is-arrow-arrow',
            })
            icon.string = glyph
            link.append(icon)
            return link

        if number > 1:
            navigation.append(arrow(number - 1, 'previous', '←'))
        numbers = page.new_tag('div', attrs={'class': 'wp-block-query-pagination-numbers'})
        visible = sorted({1, pages} | set(range(max(1, number - 2), min(pages, number + 2) + 1)))
        previous = None
        for current in visible:
            if previous is not None:
                numbers.append('\n')
                if current > previous + 1:
                    dots = page.new_tag('span', attrs={'class': 'page-numbers dots'})
                    dots.string = '…'
                    numbers.append(dots)
                    numbers.append('\n')
            if current == number:
                item = page.new_tag('span', attrs={'class': 'page-numbers current', 'aria-current': 'page'})
            else:
                item = page.new_tag('a', attrs={'class': 'page-numbers', 'href': route(current)})
            item.string = str(current)
            numbers.append(item)
            previous = current
        navigation.append(numbers)
        if number < pages:
            navigation.append(arrow(number + 1, 'next', '→'))
        result.append((route(number), page))
    return result
