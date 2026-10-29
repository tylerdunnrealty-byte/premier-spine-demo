"""Dependency-free source checks; not a browser/accessibility conformance test."""
from html.parser import HTMLParser
from pathlib import Path
root = Path(__file__).resolve().parents[1]
html = (root / 'index.html').read_text()
js = (root / 'guide.js').read_text()
css = (root / 'guide.css').read_text()
class Check(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.assets = [], []
    def handle_starttag(self, tag, pairs):
        attrs = dict(pairs)
        if 'id' in attrs: self.ids.append(attrs['id'])
        if tag in ('script', 'link', 'img'): self.assets.append(attrs.get('src', attrs.get('href', '')))
check = Check()
check.feed(html)
assert len(check.ids) == len(set(check.ids)), 'Duplicate IDs'
assert check.assets == ['guide.css', 'guide.js'], 'Unexpected page assets'
for api in ('localStorage', 'sessionStorage', 'fetch(', 'XMLHttpRequest', 'sendBeacon', 'document.cookie'):
    assert api not in js, f'Unexpected persistence or network API: {api}'
assert '@media print' in css and 'prefers-reduced-motion' in css
assert 'tel:2087703536' in html
assert html.count('class="step"') == 4
assert 'type="range"' not in html and '<form' not in html
assert 'needs Dr. Yakel / Sarah review' in html
print('PASS: IDs, local assets, persistence/network exclusions, print/reduced-motion rules, contact, scope and review label.')
