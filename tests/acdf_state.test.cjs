const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const buttons=['anatomy','procedure','goal'].map(view=>({dataset:{view},attrs:{},setAttribute(k,v){this.attrs[k]=v},addEventListener(k,f){this[k]=f}}));
const panels=buttons.map(b=>({id:`view-${b.dataset.view}`,hidden:false}));
const controls={hidden:true};
vm.runInNewContext(fs.readFileSync('procedures/acdf/guide.js','utf8'),{document:{querySelectorAll:s=>s==='[data-view]'?buttons:panels,querySelector:()=>controls}});
assert.equal(controls.hidden,false);
for(const name of ['anatomy','goal','procedure','procedure','anatomy']){
buttons.find(b=>b.dataset.view===name).click();
assert.equal(panels.filter(p=>!p.hidden).length,1);
assert.equal(panels.find(p=>!p.hidden).id,`view-${name}`);
assert.equal(buttons.filter(b=>b.attrs['aria-pressed']==='true').length,1);
assert.equal(buttons.find(b=>b.attrs['aria-pressed']==='true').dataset.view,name);
}
console.log('ACDF view switches, repeated clicks, exclusive selection, progressive enhancement passed');
