// Isolated logic regression using a minimal DOM stub, NOT browser/rendering QA.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const html = fs.readFileSync(require('node:path').join(__dirname, '../index.html'), 'utf8');
const code = html.slice(html.indexOf('  var FIRST='), html.indexOf('  /* ---------- hero: subtle cursor'));
const nodes = new Map(), timers = new Map(); let timerId=0;
function node(id) {
 const classes=new Set();
 return {id, attrs:{}, dataset:{}, listeners:{}, children:[], scrollTop:10, offsetWidth:100, offsetParent:{}, disabled:false,
 classList:{add(...xs){xs.forEach(x=>classes.add(x))},remove(...xs){xs.forEach(x=>classes.delete(x))},toggle(x,on){on?classes.add(x):classes.delete(x)},contains(x){return classes.has(x)}},
 setAttribute(k,v){this.attrs[k]=String(v)},removeAttribute(k){delete this.attrs[k]},getAttribute(k){return this.attrs[k]},
 addEventListener(k,v){this.listeners[k]=v},appendChild(x){this.children.push(x)},closest(s){return this.inside?panel:null},
 focus(){document.activeElement=this},getBoundingClientRect(){return {top:100,bottom:500}},scrollIntoView(){}};
}
const $=s=>{if(!nodes.has(s))nodes.set(s,node(s));return nodes.get(s)};
const panel=$('#help-panel'), root=node('root');
panel.contains=el=>el===panel||el===$('#hp-title')||el.inside||['#hp-close','#hp-call','#hp-ask'].includes(el.id);
const picks=['neck','low','arm','unsure'].map(x=>{let n=node(x); n.dataset.spin=x; return n});
const chips=picks.map(p=>{let n=node('chip-'+p.id);n.dataset.spin=p.id;n.inside=true;return n});
const $$=s=>s==='[data-spin]'?[...picks,...chips]:s==='button,a[href],input'?[...chips,$('#hp-close'),$('#hp-call'),$('#hp-ask')]:[];
const document={activeElement:null,listeners:{},createElement:()=>node('new'),addEventListener(k,v){this.listeners[k]=v}};
const mq={matches:true,addEventListener(k,v){this.change=v}};
const window={__spine:{focusRegion(){},releaseFocus(){}},addEventListener(){}};
const ctx={$, $$, root, document, window,matchMedia:()=>mq,reduce:true,innerHeight:1000,setTimeout:f=>{timers.set(++timerId,f);return timerId},clearTimeout:id=>timers.delete(id)};
vm.createContext(ctx);vm.runInContext(code,ctx);
function flush(){for(const [id,f]of [...timers]){timers.delete(id);f()}}
function event(key,shiftKey=false){let e={key,shiftKey,preventDefault(){this.prevented=true}};document.listeners.keydown(e);return e}
for(const key of ['neck','low','arm','unsure','hand']){
 ctx.openPanel(key,picks[0]); flush();
 assert.equal(panel.attrs['aria-hidden'],'false'); assert.equal(panel.attrs.role,'dialog');assert.equal(panel.attrs['aria-modal'],'true');
 assert.equal(picks.filter(p=>p.attrs['aria-pressed']==='true').length,1);
 assert.equal(chips.filter(p=>p.attrs['aria-pressed']==='true').length,1);
 assert.equal(panel.scrollTop,0);assert.equal($('.hp-scroll').scrollTop,0);
}
ctx.closePanel();flush();assert.equal(document.activeElement,picks[0]);assert.equal(panel.attrs['aria-hidden'],'true');
ctx.openPanel('neck',picks[0]);flush();assert.equal(document.activeElement,$('#hp-title'));
assert.equal(event('Tab',true).prevented,true);assert.equal(document.activeElement,$('#hp-ask'));
assert.equal(event('Tab').prevented,true);assert.equal(document.activeElement,chips[0]);
event('Escape');flush();assert.equal(ctx.isOpen,false);assert.equal(document.activeElement,picks[0]);
ctx.openPanel('low',picks[1]);ctx.closePanel();flush();assert.equal(document.activeElement,picks[1]); // no stale title-focus timer
ctx.openPanel('arm',picks[2]);mq.matches=false;mq.change();assert.equal(panel.attrs.role,'region');assert.equal(panel.attrs['aria-modal'],undefined);assert.equal(root.classList.contains('lock'),false);
mq.matches=true;mq.change();assert.equal(panel.attrs.role,'dialog');assert.equal(root.classList.contains('lock'),true);
ctx.closePanel();flush();assert.equal($('.callbar').attrs.inert,undefined);
ctx.openPanel('arm',picks[2]);flush(); $('#hp-extra').children.at(-1).listeners.click();assert.equal(document.activeElement,$('#hp-title'));assert.equal(ctx.cur,'hand');
document.activeElement=node('outside');assert.equal(event('Tab').prevented,true);assert.equal(document.activeElement,chips[0]);
ctx.closePanel();ctx.openPanel('neck',picks[0]);flush();assert.equal(document.activeElement,$('#hp-title'));
ctx.closePanel();flush();
ctx.openPanel('invalid',picks[3]);assert.equal(ctx.isOpen,false);
console.log('PASS: five content states; one selected per group; scroll reset; mobile semantics; focus trap; Escape/restore; rapid close; resize; invalid state.');
