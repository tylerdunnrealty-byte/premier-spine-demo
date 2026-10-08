() => {
  const parse = c => { const m = c.match(/rgba?\(([^)]+)\)/); if (!m) return null; const p = m[1].split(/[ ,\/]+/).filter(Boolean).map(Number); return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1]; };
  const blend = (top, bot) => { const a = top[3]; return [top[0]*a + bot[0]*(1-a), top[1]*a + bot[1]*(1-a), top[2]*a + bot[2]*(1-a), 1]; };
  const lum = c => { const f = v => { v /= 255; return v <= 0.03928 ? v/12.92 : Math.pow((v+0.055)/1.055, 2.4); }; return 0.2126*f(c[0]) + 0.7152*f(c[1]) + 0.0722*f(c[2]); };
  const bgOf = el => { const stack = []; for (let e = el; e; e = e.parentElement) { const b = parse(getComputedStyle(e).backgroundColor); if (b && b[3] > 0) { stack.push(b); if (b[3] >= 1) break; } } let c = [255,255,255,1]; for (let i = stack.length - 1; i >= 0; i--) c = blend(stack[i], c); return c; };
  const out = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const seen = new Set();
  while (walker.nextNode()) {
    const t = walker.currentNode; if (!t.textContent.trim()) continue; const el = t.parentElement; if (!el || seen.has(el)) continue; seen.add(el);
    const s = getComputedStyle(el); const r = el.getBoundingClientRect(); if (r.width < 2 || r.height < 2 || s.visibility === 'hidden' || el.closest('[hidden], .sr, .skip, dialog:not([open])')) continue;
    if (s.clip && s.clip !== 'auto') continue;
    const fg = parse(s.color); if (!fg) continue; const bg = bgOf(el); const f = blend(fg, bg);
    const L1 = lum(f), L2 = lum(bg); const ratio = (Math.max(L1,L2)+0.05)/(Math.min(L1,L2)+0.05);
    const size = parseFloat(s.fontSize), bold = parseInt(s.fontWeight) >= 700; const large = size >= 24 || (bold && size >= 18.66);
    const need = large ? 3 : 4.5; if (ratio + 0.01 < need) out.push(`${el.tagName}.${el.className} "${t.textContent.trim().slice(0,30)}" ${ratio.toFixed(2)} < ${need}`);
  }
  return out;
}
