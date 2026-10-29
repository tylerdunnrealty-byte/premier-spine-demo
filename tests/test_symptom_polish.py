"""Narrow symptom-section invariants; no clinical or visual validation implied."""
from pathlib import Path
from html.parser import HTMLParser
import re, unittest
HTML=(Path(__file__).resolve().parents[1]/'index.html').read_text()
class Tags(HTMLParser):
 def __init__(self): super().__init__(); self.tags=[]; self.feed(HTML)
 def handle_starttag(self,t,a): self.tags.append((t,dict(a)))
class SymptomPolish(unittest.TestCase):
 def test_four_native_choices(self):
  choices=[(t,a) for t,a in Tags().tags if a.get('class')=='pick']
  self.assertEqual([a['data-spin'] for t,a in choices],['neck','low','arm','unsure'])
  for t,a in choices:
   self.assertEqual(t,'button');self.assertEqual(a['type'],'button');self.assertEqual(a['aria-pressed'],'false');self.assertEqual(a['aria-controls'],'help-panel')
 def test_no_pain_score_or_intake(self):
  section=HTML.split('<section class="spine-sec')[1].split('</section>')[0]
  self.assertNotIn('<input',section);self.assertNotIn('<form',section);self.assertNotIn('id="meter"',section)
  self.assertIn('What to discuss at your visit',section);self.assertIn('Call our team',section)
  self.assertIn('loss of bladder or bowel control',section)
 def test_accessible_name_and_targets(self):
  tags=Tags().tags;panel=next(a for t,a in tags if a.get('id')=='help-panel')
  self.assertEqual(panel['aria-labelledby'],'hp-title')
  close=next(a for t,a in tags if a.get('id')=='hp-close')
  self.assertEqual(close['aria-label'],'Close spine information')
  ids=[a['id'] for t,a in tags if 'id' in a]
  self.assertEqual(len(ids),len(set(ids)))
 def test_no_slider_runtime(self):
  self.assertNotIn('function setMeter(',HTML);self.assertNotIn('var MSG=[',HTML)
  self.assertIn('if(isOpen) title.focus',HTML)
 def test_calm_scoped_styles(self):
  self.assertIn('.help-panel .hp-sec h3{font:600 1rem',HTML)
  self.assertIn('.hp-close{width:44px;height:44px}',HTML)
  self.assertNotIn("duo.style.setProperty('--px'",HTML)
if __name__=='__main__':unittest.main()
