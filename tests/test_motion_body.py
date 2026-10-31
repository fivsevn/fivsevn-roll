from pathlib import Path
import sys
import unittest

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from motion_body import render


class MotionBodyTests(unittest.TestCase):
    def test_empty_body_adds_no_content(self):
        self.assertEqual('', render(' \n\t'))

    def test_paragraphs_formatting_links_and_lists(self):
        body = '# 标题\n\n第一段 **粗体** 和 *强调*。\n\n第二段 [链接](https://example.com/)。\n\n- one\n- two'
        fragment = BeautifulSoup(render(body), 'html.parser')
        self.assertEqual('标题', fragment.h1.get_text())
        self.assertEqual(2, len(fragment.select('p')))
        self.assertEqual('粗体', fragment.strong.get_text())
        self.assertEqual('强调', fragment.em.get_text())
        self.assertEqual('https://example.com/', fragment.a['href'])
        self.assertEqual(['one', 'two'], [li.get_text() for li in fragment.select('li')])

    def test_fenced_code_and_tables(self):
        fragment = BeautifulSoup(render('```python\nprint("hello")\n```\n\n| A | B |\n| - | - |\n| 1 | 2 |'), 'html.parser')
        self.assertEqual('print("hello")\n', fragment.select_one('pre code').get_text())
        self.assertEqual(['A', 'B'], [th.get_text() for th in fragment.select('th')])

    def test_raw_html_is_displayed_as_text(self):
        body = '<script>alert("test")</script>\n\n<img src="https://example.com/image.jpg" onerror="alert(1)">'
        fragment = BeautifulSoup(render(body), 'html.parser')
        self.assertFalse(fragment.select('script, img'))
        self.assertIn('<script>', fragment.get_text())
        self.assertFalse(fragment.select('[onerror]'))

    def test_unsafe_link_schemes_have_no_clickable_target(self):
        body = '[bad](javascript:alert) [data](data:text/html,test) [file](file:///tmp/file) [mail](mailto:hello@example.com) [relative](/motion/)'
        links = BeautifulSoup(render(body), 'html.parser').select('a')
        self.assertEqual([None, None, None, 'mailto:hello@example.com', '/motion/'],
                         [link.get('href') for link in links])

    def test_markdown_images_are_rejected_instead_of_fetching_or_publishing(self):
        for image in ['![remote](https://example.com/image.jpg)', '![local](assets/image.jpg)']:
            with self.subTest(image=image), self.assertRaisesRegex(ValueError, 'body images are not published'):
                render(image)


if __name__ == '__main__':
    unittest.main()
