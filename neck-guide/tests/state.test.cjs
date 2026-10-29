// Dependency-free state/DOM-contract tests. Not a browser or visual/accessibility audit.
const fs = require('node:fs'); const vm = require('node:vm'); const assert = require('node:assert/strict');
class Element {
  constructor() { this.children=[]; this.events={}; this.attrs={}; this.dataset={}; this.hidden=false; this.checked=false; }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children=nodes; }
  addEventListener(name, callback) { this.events[name]=callback; }
  setAttribute(name,value) { this.attrs[name]=value; }
  removeAttribute(name) { delete this.attrs[name]; }
  focus() { this.focused=true; } scrollIntoView() { this.scrolled=true; }
  click() { this.events.click(); }
  change(checked) { this.checked=checked; this.events.change(); }
}
const ids={}; ['goals','questions','summary-goals','summary-questions','step-status','restart','print','interactive',...Array.from({length:4},(_,i)=>`title-${i}`)].forEach(id=>ids[id]=new Element());
const panels=Array.from({length:4},()=>new Element()), progress=Array.from({length:4},()=>new Element());
panels.forEach((p,i)=>p.hidden=i!==0);
const next=Array.from({length:5},()=>new Element()), back=Array.from({length:3},()=>new Element()), shortcut=new Element();shortcut.dataset.go='3';
const allInputs=()=>[...ids.goals.children,...ids.questions.children].map(row=>row.children[0]);
let printed=0; const window={events:{},print(){printed++;},addEventListener(n,f){this.events[n]=f;}};
const document={getElementById:id=>ids[id],createElement:()=>new Element(),querySelectorAll:q=>({'.step':panels,'.progress li':progress,'.next':next,'.back':back,'[data-go]':[shortcut],'input[type="checkbox"]':allInputs()})[q]};
vm.runInNewContext(fs.readFileSync(require('node:path').join(__dirname,'../guide.js'),'utf8'),{document,window,Set,Number});
assert.equal(ids.interactive.hidden,false); assert.equal(ids.goals.children.length,5);assert.equal(ids.questions.children.length,5);
assert.equal(allInputs().filter(i=>i.checked).length,0);
shortcut.click();assert.equal(panels[3].hidden,false);assert.equal(ids['summary-goals'].children.length,1);assert.match(ids['summary-questions'].children[0].textContent,/what happens next/);
back[0].click();assert.equal(panels[2].hidden,false);
back[1].click();assert.equal(panels[1].hidden,false);
const walking=ids.goals.children[0].children[0];walking.change(true);
const sleep=ids.goals.children[1].children[0];sleep.change(true);
assert.equal(ids['summary-goals'].children.length,2);walking.change(false);assert.equal(ids['summary-goals'].children.length,1);assert.match(ids['summary-goals'].children[0].textContent,/sleep/);
next[0].click();assert.equal(panels[2].hidden,false);
ids.questions.children[2].children[0].change(true);next[1].click();assert.equal(panels[3].hidden,false);assert.match(ids['summary-questions'].children[0].textContent,/benefits and risks/);
assert.equal(progress.filter(p=>p.attrs['aria-current']==='step').length,1);assert.match(ids['step-status'].textContent,/Step 4 of 4/);assert.equal(ids['title-3'].focused,true);
ids.print.click();assert.equal(printed,1);window.events.beforeprint();
next[2].click();assert.equal(panels[3].hidden,false); // Bounds safe
ids.restart.click();assert.equal(panels[0].hidden,false);assert.equal(allInputs().filter(i=>i.checked).length,0);assert.equal(ids['summary-goals'].children.length,1);assert.match(ids['summary-goals'].children[0].textContent,/share what matters/);
back[2].click();assert.equal(panels[0].hidden,false);
next[3].click();next[4].click();next[0].click();assert.equal(panels[3].hidden,false);assert.equal(panels.filter(p=>!p.hidden).length,1);
console.log('PASS: initialization, 5 goals/5 questions, empty checklist, forward/back/skip, multiselect, deselect, summary, focus/progress, print, reset, bounds.');
