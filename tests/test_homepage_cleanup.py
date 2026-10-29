"""Structural regressions for the static homepage; no browser or network tests."""
from html.parser import HTMLParser
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

HTML = (Path(__file__).resolve().parents[1] / 'index.html').read_text()
class Elements(HTMLParser):
    def __init__(self):
        super().__init__(); self.items = []; self.feed(HTML)
    def handle_starttag(self, tag, attrs): self.items.append((tag, dict(attrs)))

class HomepageCleanupTests(unittest.TestCase):
    def setUp(self): self.elements = Elements().items
    def test_one_patient_portal_entry(self):
        links = [a for t,a in self.elements if t == 'a' and a.get('href') == 'portal/']
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0].get('class'), 'nav-login')
    def test_no_credential_fields(self):
        self.assertFalse([a for t,a in self.elements if t == 'input' and a.get('type') in ('password','email')])
        self.assertNotIn('data-forgot', HTML)
    def test_contact_has_no_fake_submission(self):
        self.assertNotIn('id="consult-form"', HTML)
        self.assertNotIn('Send request', HTML)
        self.assertNotIn('Thank you. This demo form', HTML)
        self.assertIn('online appointment requests aren’t connected', HTML)
        self.assertIn('Nothing can be submitted here', HTML)
    def test_office_roles_remain_reachable(self):
        roles = [a.get('data-preview-role') for t,a in self.elements if 'data-preview-role' in a]
        self.assertEqual(roles, ['employee','physician'])
        self.assertIn("showPortal(b.dataset.previewRole)", HTML)
        self.assertIn("open(b,'employee')", HTML)
    def test_changed_id_references_exist(self):
        ids = [a['id'] for _,a in self.elements if 'id' in a]
        for name in ('login','lg-title','lg-view-login','lg-view-portal','lg-tab-employee','lg-panel-employee','lg-tab-physician','lg-panel-physician','help-panel','hp-close','hp-title'):
            self.assertEqual(ids.count(name), 1, name)
        for _,a in self.elements:
            for ref in a.get('aria-controls','').split(): self.assertIn(ref, ids)
    def test_mobile_sheet_has_single_scroll_and_no_callbar(self):
        self.assertIn('.spine-help-open .callbar{display:none}', HTML)
        self.assertIn("root.classList.add('spine-help-open')", HTML)
        self.assertIn("root.classList.remove('spine-help-open')", HTML)
        self.assertIn('.hp-scroll{flex:none;overflow:visible}', HTML)
        self.assertIn('.spine-sec.open{position:relative;z-index:150}', HTML)
        self.assertIn('max-height:calc(100svh - 16px);overflow-y:auto', HTML)
        self.assertIn("$('.callbar').setAttribute('inert','')", HTML)
        self.assertIn("$('.callbar').removeAttribute('inert')", HTML)
    def test_modal_close_restores_opener(self):
        self.assertIn("b.addEventListener('click',function(){ close(); });", HTML)
        self.assertIn('opener.focus({preventScroll:true})', HTML)
    def test_warning_and_brand_retained(self):
        self.assertIn('loss of bladder or bowel control', HTML)
        self.assertIn('This isn&rsquo;t a diagnosis.', HTML)
        self.assertIn('Back to your', HTML)
        self.assertIn('kind of', HTML)
        self.assertIn('Idaho.', HTML)
    def test_javascript_syntax(self):
        scripts = re.findall(r'<script(?: [^>]*)?>(.*?)</script>', HTML, re.S)
        with tempfile.TemporaryDirectory() as d:
            for i,script in enumerate(scripts):
                if not script.strip() or script.lstrip().startswith('{'): continue
                p=Path(d)/f'{i}.js';p.write_text(script)
                subprocess.run(['node','--check',str(p)],check=True,capture_output=True)

if __name__ == '__main__': unittest.main(verbosity=2)
