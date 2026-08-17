# -*- coding: utf-8 -*-
"""Combined dashboard: 行业面板 / 科技面板 / 策略持仓(含最新变化). Self-contained HTML."""
import os
import json
import pickle

OUT = os.path.join(os.path.dirname(__file__), "output")

HTML = r"""<title>RRG 象限轮动看板</title>
<style>
  :root{--bg:#0a0d13;--panel:#121722;--panel2:#0e131d;--border:#242c3a;--ink:#e6eaf2;
    --muted:#7d8798;--accent:#38bdf8;--lead:#22c55e;--impr:#3b82f6;--weak:#f59e0b;--lag:#ef4444;--gold:#facc15;
    --mono:ui-monospace,"Cascadia Code","SF Mono",Consolas,monospace;
    --sans:-apple-system,"Segoe UI",Roboto,"PingFang SC","Microsoft YaHei",sans-serif;}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);font-size:14px;-webkit-font-smoothing:antialiased}
  .wrap{max-width:1460px;margin:0 auto;padding:16px 20px 60px}
  header{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap;border-bottom:1px solid var(--border);padding-bottom:10px}
  h1{font-size:18px;margin:0;letter-spacing:.5px}
  .sub{color:var(--muted);font-size:12px;font-family:var(--mono)}
  .tabs{display:flex;gap:6px;margin:14px 0 16px}
  .tabs button{background:var(--panel);color:var(--muted);border:1px solid var(--border);
    border-radius:8px;padding:7px 16px;font-size:13px;cursor:pointer;font-family:var(--mono)}
  .tabs button.on{background:var(--accent);color:#04121c;font-weight:700;border-color:var(--accent)}
  .pane{display:none}.pane.on{display:block}
  .subtabs{display:flex;gap:6px;margin:2px 0 14px}
  .subtabs button{background:var(--panel2);color:var(--muted);border:1px solid var(--border);
    border-radius:7px;padding:5px 14px;font-size:12.5px;cursor:pointer;font-family:var(--mono)}
  .subtabs button.on{background:#1b2740;color:var(--accent);border-color:var(--accent);font-weight:700}
  .subpane{display:none}.subpane.on{display:block}
  .legend{display:flex;gap:14px;flex-wrap:wrap;font-size:12px;color:var(--muted);margin-left:auto}
  .legend b{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:5px;vertical-align:middle}
  .grid2{display:grid;grid-template-columns:minmax(0,540px) 1fr;gap:20px}
  @media(max-width:1040px){.grid2{grid-template-columns:1fr}}
  .card{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:14px}
  .card h2{font-size:12px;margin:0 0 10px;letter-spacing:.4px;text-transform:uppercase;color:var(--muted);font-weight:600}
  .toggle{display:inline-flex;border:1px solid var(--border);border-radius:7px;overflow:hidden;margin-left:8px}
  .toggle button{background:transparent;color:var(--muted);border:0;padding:3px 10px;font-size:12px;cursor:pointer;font-family:var(--mono)}
  .toggle button.on{background:var(--accent);color:#04121c;font-weight:700}
  svg{width:100%;height:auto;display:block}
  .qlabel{font-family:var(--mono);font-size:12px;font-weight:700}
  .dot{cursor:pointer}.tip{position:fixed;pointer-events:none;background:#05070c;border:1px solid var(--border);
    border-radius:7px;padding:7px 9px;font-size:12px;font-family:var(--mono);z-index:30;opacity:0;transition:opacity .1s;max-width:240px}
  .groups{display:flex;flex-direction:column;gap:12px}
  .group{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:9px 11px}
  .ghead{display:flex;align-items:center;gap:9px;margin-bottom:8px}
  .ghead .gname{font-weight:700;font-size:13px}
  .ghead .gq{font-family:var(--mono);font-size:10.5px;padding:1px 7px;border-radius:20px;font-weight:700}
  .ghead .gn{color:var(--muted);font-size:11px;font-family:var(--mono);margin-left:auto}
  .tiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(116px,1fr));gap:6px}
  .tile{border:1px solid var(--border);border-left-width:3px;border-radius:7px;padding:6px 8px;background:var(--panel2);min-height:56px}
  .tile.gold{border-color:var(--gold);box-shadow:0 0 0 1px rgba(250,204,21,.25)}
  .tile .tk{font-family:var(--mono);font-weight:700;font-size:13px}
  .tile .nm{color:var(--muted);font-size:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .tile .rm{font-family:var(--mono);font-size:10px;color:var(--muted);margin-top:3px;display:flex;justify-content:space-between}
  .tile .rm b{color:var(--ink)}
  /* holdings */
  .hgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px}
  .hcard{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:13px}
  .hcard h3{margin:0 0 3px;font-size:14px}
  .hcard .meta{color:var(--muted);font-size:11px;font-family:var(--mono);margin-bottom:9px}
  .pill{display:inline-block;font-family:var(--mono);font-size:11.5px;padding:3px 8px;border-radius:6px;margin:2px 3px 2px 0;border:1px solid var(--border)}
  .chg{margin-top:8px;font-size:11.5px;font-family:var(--mono);display:flex;flex-direction:column;gap:3px}
  .add{color:var(--lead)}.rem{color:var(--lag)}.none{color:var(--muted)}
  .secttl{font-size:13px;color:var(--accent);font-family:var(--mono);margin:6px 0 10px;letter-spacing:.5px}
</style>
<div class="wrap">
  <header>
    <h1>RRG 象限轮动看板</h1>
    <span class="sub" id="sub"></span>
    <div class="legend">
      <span><b style="background:var(--lead)"></b>领先Q1</span><span><b style="background:var(--impr)"></b>改善Q2</span>
      <span><b style="background:var(--weak)"></b>转弱Q4</span><span><b style="background:var(--lag)"></b>落后Q3</span>
      <span><b style="background:var(--gold)"></b>金边=走强</span>
    </div>
  </header>
  <div class="tabs">
    <button data-t="ind" class="on">行业面板 (vs SPY)</button>
    <button data-t="tech">科技面板 (vs QQQ)</button>
    <button data-t="hold">策略持仓 &amp; 最新变化</button>
  </div>
  <div class="pane on" id="pane-ind"></div>
  <div class="pane" id="pane-tech"></div>
  <div class="pane" id="pane-hold"></div>
</div>
<div class="tip" id="tip"></div>
<script>
const B = __BLOB__;
const QHEX={Lead:'#22c55e',Impr:'#3b82f6',Weak:'#f59e0b',Lag:'#ef4444'};
const QN={Lead:'领先Q1',Impr:'改善Q2',Weak:'转弱Q4',Lag:'落后Q3'};
const tip=document.getElementById('tip');
function showTip(h,e){tip.innerHTML=h;tip.style.opacity=1;mv(e);}
function mv(e){tip.style.left=(e.clientX+14)+'px';tip.style.top=(e.clientY+14)+'px';}
function hide(){tip.style.opacity=0;}
document.getElementById('sub').textContent='行业截至 '+B.ind.asof+' · 科技截至 '+B.tech.asof+' · 成本 '+B.meta.cost_bps+'bps · '+B.meta.exec;

function panelHTML(id){return `
  <div class="subtabs" id="st-${id}">
    <button data-s="plot" class="on">象限图</button>
    <button data-s="tiles">个股列表</button>
  </div>
  <div class="subpane on" id="sp-plot-${id}">
    <div class="card" style="max-width:680px"><h2>相对旋转图 (RS-Ratio × RS-Momentum)
      <span class="toggle" id="tog-${id}">
      <button data-m="subs" class="on">子板块</button><button data-m="stocks">个股</button></span></h2>
      <div id="plot-${id}"></div></div>
  </div>
  <div class="subpane" id="sp-tiles-${id}">
    <div id="grp-${id}" class="groups"></div>
  </div>`;}

function drawPlot(id,D,mode){
  const pts=(mode==='subs'?D.subs:D.stocks).map(s=>({x:s.ratio,y:s.mom,st:s.state,
    g:s.strengthening,lab:mode==='subs'?s.sub:s.ticker,r:mode==='subs'?9:5,
    tip:`<b style="color:${QHEX[s.st||s.state]}">${QN[s.state]}</b> · ${mode==='subs'?s.sub:(s.ticker+' '+s.name)}<br>R ${s.ratio} · M ${s.mom}`}));
  const W=540,H=540,p=32,xs=pts.map(a=>a.x),ys=pts.map(a=>a.y);
  const xn=Math.min(96,...xs)-.5,xx=Math.max(104,...xs)+.5,yn=Math.min(96,...ys)-.5,yx=Math.max(104,...ys)+.5;
  const sx=v=>p+(v-xn)/(xx-xn)*(W-2*p),sy=v=>H-p-(v-yn)/(yx-yn)*(H-2*p),x1=sx(100),y1=sy(100);
  let s=`<svg viewBox="0 0 ${W} ${H}">`;
  s+=`<rect x="${x1}" y="${p}" width="${W-p-x1}" height="${y1-p}" fill="#22c55e" opacity=".06"/>`;
  s+=`<rect x="${p}" y="${p}" width="${x1-p}" height="${y1-p}" fill="#3b82f6" opacity=".06"/>`;
  s+=`<rect x="${p}" y="${y1}" width="${x1-p}" height="${H-p-y1}" fill="#ef4444" opacity=".06"/>`;
  s+=`<rect x="${x1}" y="${y1}" width="${W-p-x1}" height="${H-p-y1}" fill="#f59e0b" opacity=".07"/>`;
  s+=`<line x1="${p}" y1="${y1}" x2="${W-p}" y2="${y1}" stroke="#3a4356"/><line x1="${x1}" y1="${p}" x2="${x1}" y2="${H-p}" stroke="#3a4356"/>`;
  s+=`<text class="qlabel" x="${W-p-4}" y="${p+13}" text-anchor="end" fill="#22c55e">领先</text>`;
  s+=`<text class="qlabel" x="${p+4}" y="${p+13}" fill="#3b82f6">改善</text>`;
  s+=`<text class="qlabel" x="${p+4}" y="${H-p-5}" fill="#ef4444">落后</text>`;
  s+=`<text class="qlabel" x="${W-p-4}" y="${H-p-5}" text-anchor="end" fill="#f59e0b">转弱</text>`;
  pts.forEach((a,i)=>{const cx=sx(a.x),cy=sy(a.y);
    if(a.g)s+=`<circle cx="${cx}" cy="${cy}" r="${a.r+3}" fill="none" stroke="#facc15" stroke-width="2"/>`;
    s+=`<circle class="dot" data-i="${i}" cx="${cx}" cy="${cy}" r="${a.r}" fill="${QHEX[a.st]}" opacity=".9"/>`;
    if(mode==='subs')s+=`<text x="${cx+a.r+3}" y="${cy+3}" font-size="9.5" fill="#c7cedb" font-family="var(--mono)">${a.lab}</text>`;});
  s+=`</svg>`;
  const box=document.getElementById('plot-'+id);box.innerHTML=s;
  box.querySelectorAll('.dot').forEach(d=>{const a=pts[+d.dataset.i];
    d.onmousemove=e=>showTip(a.tip,e);d.onmouseleave=hide;});
}
function drawGroups(id,D){
  const subMap={};D.subs.forEach(s=>subMap[s.sub]=s);
  const host=document.getElementById('grp-'+id);host.innerHTML='';
  D.groups.forEach(g=>{
    const items=D.stocks.filter(s=>s.sub===g).sort((a,b)=>(b.strengthening-a.strengthening)||(b.mom-a.mom));
    if(!items.length)return;const gs=subMap[g];
    let h=`<div class="group"><div class="ghead"><span class="gname">${g}</span>`;
    if(gs)h+=`<span class="gq" style="background:${QHEX[gs.state]}22;color:${QHEX[gs.state]}">${QN[gs.state]} R${gs.ratio} M${gs.mom}</span>`;
    h+=`<span class="gn">${items.length}</span></div><div class="tiles">`;
    items.forEach(s=>{h+=`<div class="tile ${s.strengthening?'gold':''}" style="border-left-color:${QHEX[s.state]}">
      <div class="tk">${s.ticker}</div><div class="nm">${s.name}</div>
      <div class="rm"><span>R<b>${s.ratio}</b></span><span>M<b>${s.mom}</b></span></div></div>`;});
    h+=`</div></div>`;host.insertAdjacentHTML('beforeend',h);});
}
function initPanel(id,D){
  document.getElementById('pane-'+id).innerHTML=panelHTML(id);
  drawPlot(id,D,'subs');drawGroups(id,D);
  document.getElementById('tog-'+id).onclick=e=>{const b=e.target.closest('button');if(!b)return;
    document.querySelectorAll('#tog-'+id+' button').forEach(x=>x.classList.remove('on'));
    b.classList.add('on');drawPlot(id,D,b.dataset.m);};
  document.getElementById('st-'+id).onclick=e=>{const b=e.target.closest('button');if(!b)return;
    document.querySelectorAll('#st-'+id+' button').forEach(x=>x.classList.remove('on'));
    b.classList.add('on');
    document.getElementById('sp-plot-'+id).classList.toggle('on',b.dataset.s==='plot');
    document.getElementById('sp-tiles-'+id).classList.toggle('on',b.dataset.s==='tiles');};
}
function initHold(){
  let h='';
  for(const uni of ['行业板块','科技个股']){
    h+=`<div class="secttl">▍ ${uni} — 各策略当前持仓 & 最新调仓变化</div><div class="hgrid">`;
    const H=B.holds[uni];
    for(const name in H){const d=H[name];
      let pills=d.picks.map(t=>{const st=(d.states&&d.states[t])||'';return `<span class="pill" style="border-color:${QHEX[st]||'#333'};color:${QHEX[st]||'#ccc'}">${t}</span>`;}).join('');
      if(!d.picks.length)pills='<span class="none">现金/空仓</span>';
      let chg='';
      chg+=d.added&&d.added.length?`<span class="add">+ 新增: ${d.added.join(', ')}</span>`:'';
      chg+=d.removed&&d.removed.length?`<span class="rem">− 移除: ${d.removed.join(', ')}</span>`:'';
      if(!chg)chg='<span class="none">较上次无变化</span>';
      h+=`<div class="hcard"><h3>${name}</h3>
        <div class="meta">调仓日 ${d.date}　·　上次 ${d.prev_date}</div>
        <div>${pills}</div><div class="chg">${chg}</div></div>`;}
    h+='</div>';
  }
  document.getElementById('pane-hold').innerHTML=h;
}
document.querySelector('.tabs').onclick=e=>{const b=e.target.closest('button');if(!b)return;
  document.querySelectorAll('.tabs button').forEach(x=>x.classList.remove('on'));b.classList.add('on');
  document.querySelectorAll('.pane').forEach(x=>x.classList.remove('on'));
  document.getElementById('pane-'+b.dataset.t).classList.add('on');};
window.addEventListener('mousemove',e=>{if(tip.style.opacity==1)mv(e);});
initPanel('ind',B.ind);initPanel('tech',B.tech);initHold();
</script>
"""

def build():
    ind = json.load(open(os.path.join(OUT, "industry_rrg.json"), encoding="utf-8"))
    tech = json.load(open(os.path.join(OUT, "tech_rrg.json"), encoding="utf-8"))
    R = pickle.load(open(os.path.join(OUT, "final_results.pkl"), "rb"))
    holds = {"行业板块": R["industry"]["holds"], "科技个股": R["tech"]["holds"]}
    blob = json.dumps({"ind": ind, "tech": tech, "holds": holds,
                       "meta": {"cost_bps": R["cost_bps"], "exec": R["exec"]}}, ensure_ascii=False)
    html = HTML.replace("__BLOB__", blob)
    path = os.path.join(OUT, "dashboard.html")
    open(path, "w", encoding="utf-8").write(html)
    print("saved:", path, round(len(html) / 1024, 1), "KB")
    return path


if __name__ == "__main__":
    build()
