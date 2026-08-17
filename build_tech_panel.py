# -*- coding: utf-8 -*-
"""Generate tech_panel.html (a dark terminal RRG panel) from tech_rrg.json."""
import os
import json

OUT = os.path.join(os.path.dirname(__file__), "output")
data = json.load(open(os.path.join(OUT, "tech_rrg.json"), encoding="utf-8"))
DATA_JS = json.dumps(data, ensure_ascii=False)

HTML = r"""<title>Tech RRG 象限面板</title>
<style>
  :root{
    --bg:#0a0d13; --panel:#121722; --panel2:#0e131d; --border:#242c3a;
    --ink:#e6eaf2; --muted:#7d8798; --accent:#38bdf8;
    --lead:#22c55e; --impr:#3b82f6; --weak:#f59e0b; --lag:#ef4444; --gold:#facc15;
    --mono:ui-monospace,"Cascadia Code","SF Mono",Consolas,monospace;
    --sans:-apple-system,"Segoe UI",Roboto,"PingFang SC","Microsoft YaHei",sans-serif;
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);
       -webkit-font-smoothing:antialiased;font-size:14px}
  .wrap{max-width:1440px;margin:0 auto;padding:18px 20px 60px}
  header{display:flex;align-items:baseline;gap:16px;flex-wrap:wrap;
         border-bottom:1px solid var(--border);padding-bottom:12px;margin-bottom:16px}
  h1{font-size:19px;margin:0;letter-spacing:.5px;font-weight:700}
  h1 .bench{color:var(--accent)}
  .sub{color:var(--muted);font-size:12px;font-family:var(--mono)}
  .spacer{flex:1}
  .legend{display:flex;gap:14px;flex-wrap:wrap;font-size:12px;color:var(--muted)}
  .legend b{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:5px;vertical-align:middle}
  .grid2{display:grid;grid-template-columns:minmax(0,560px) 1fr;gap:22px}
  @media(max-width:1040px){.grid2{grid-template-columns:1fr}}
  .card{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:14px}
  .card h2{font-size:13px;margin:0 0 10px;letter-spacing:.4px;text-transform:uppercase;color:var(--muted);font-weight:600}
  .toggle{display:inline-flex;border:1px solid var(--border);border-radius:7px;overflow:hidden;margin-left:10px}
  .toggle button{background:transparent;color:var(--muted);border:0;padding:4px 11px;font-size:12px;cursor:pointer;font-family:var(--mono)}
  .toggle button.on{background:var(--accent);color:#04121c;font-weight:700}
  svg{width:100%;height:auto;display:block}
  .qlabel{font-family:var(--mono);font-size:12px;font-weight:700;opacity:.85}
  .dot{cursor:pointer;transition:opacity .15s}
  .dot:hover{opacity:1}
  .tip{position:fixed;pointer-events:none;background:#05070c;border:1px solid var(--border);
       border-radius:7px;padding:7px 9px;font-size:12px;font-family:var(--mono);z-index:20;opacity:0;transition:opacity .1s;max-width:230px}
  .tip .q{font-weight:700}
  /* tile grid */
  .groups{display:flex;flex-direction:column;gap:14px}
  .group{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:10px 12px}
  .ghead{display:flex;align-items:center;gap:10px;margin-bottom:9px}
  .ghead .gname{font-weight:700;font-size:13px}
  .ghead .gq{font-family:var(--mono);font-size:11px;padding:1px 7px;border-radius:20px;font-weight:700}
  .ghead .gn{color:var(--muted);font-size:11px;font-family:var(--mono);margin-left:auto}
  .tiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(118px,1fr));gap:7px}
  .tile{border:1px solid var(--border);border-left-width:3px;border-radius:7px;padding:7px 8px;
        background:var(--panel2);position:relative;min-height:58px}
  .tile.gold{border-color:var(--gold);box-shadow:0 0 0 1px rgba(250,204,21,.25)}
  .tile .tk{font-family:var(--mono);font-weight:700;font-size:13px}
  .tile .nm{color:var(--muted);font-size:10.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .tile .rm{font-family:var(--mono);font-size:10.5px;color:var(--muted);margin-top:4px;
            font-variant-numeric:tabular-nums;display:flex;justify-content:space-between}
  .tile .rm b{color:var(--ink);font-weight:600}
  .filters{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px}
  .chip{border:1px solid var(--border);background:var(--panel);color:var(--muted);border-radius:20px;
        padding:3px 11px;font-size:11.5px;cursor:pointer;font-family:var(--mono)}
  .chip.on{border-color:var(--accent);color:var(--accent)}
  .foot{margin-top:26px;color:var(--muted);font-size:11px;line-height:1.6;font-family:var(--mono)}
</style>

<div class="wrap">
  <header>
    <h1>TECH RRG · 象限面板 <span class="bench" id="benchTag"></span></h1>
    <span class="sub" id="asof"></span>
    <div class="spacer"></div>
    <div class="legend">
      <span><b style="background:var(--lead)"></b>领先 Q1</span>
      <span><b style="background:var(--impr)"></b>改善 Q2</span>
      <span><b style="background:var(--weak)"></b>转弱 Q4</span>
      <span><b style="background:var(--lag)"></b>落后 Q3</span>
      <span><b style="background:var(--gold)"></b>金边=走强</span>
    </div>
  </header>

  <div class="grid2">
    <div class="card">
      <h2>相对旋转图 (RS-Ratio × RS-Momentum)
        <span class="toggle" id="modeTog">
          <button data-m="subs" class="on">子板块</button>
          <button data-m="stocks">个股</button>
        </span>
      </h2>
      <div id="plot"></div>
    </div>
    <div>
      <h2 style="font-size:13px;letter-spacing:.4px;text-transform:uppercase;color:var(--muted);margin:2px 0 10px">
        个股象限分布（按子板块）</h2>
      <div class="filters" id="filters"></div>
      <div class="groups" id="groups"></div>
    </div>
  </div>

  <div class="foot" id="foot"></div>
</div>
<div class="tip" id="tip"></div>

<script>
const DATA = __DATA__;
const QC = {Lead:'var(--lead)',Impr:'var(--impr)',Weak:'var(--weak)',Lag:'var(--lag)'};
const QHEX = {Lead:'#22c55e',Impr:'#3b82f6',Weak:'#f59e0b',Lag:'#ef4444'};
const QN = {Lead:'领先Q1',Impr:'改善Q2',Weak:'转弱Q4',Lag:'落后Q3'};

document.getElementById('benchTag').textContent = 'vs '+DATA.bench;
document.getElementById('asof').textContent = '截至 '+DATA.asof+' · 参数 Z'+DATA.params.zwin+'/S'+DATA.params.smooth+'/M'+DATA.params.mom_lag;

const tip = document.getElementById('tip');
function showTip(html,e){tip.innerHTML=html;tip.style.opacity=1;moveTip(e);}
function moveTip(e){tip.style.left=(e.clientX+14)+'px';tip.style.top=(e.clientY+14)+'px';}
function hideTip(){tip.style.opacity=0;}

// ---------- RRG scatter ----------
function drawPlot(mode){
  const pts = mode==='subs'
    ? DATA.subs.map(s=>({x:s.ratio,y:s.mom,st:s.state,g:s.strengthening,lab:s.sub,r:9,
                         tip:`<span class="q" style="color:${QHEX[s.state]}">${QN[s.state]}</span> · ${s.sub}<br>RS-Ratio ${s.ratio} · RS-Mom ${s.mom}<br>Δ5动能 ${s.dMom5} · 在象限 ${s.days}日`}))
    : DATA.stocks.map(s=>({x:s.ratio,y:s.mom,st:s.state,g:s.strengthening,lab:s.ticker,r:5,
                         tip:`<span class="q" style="color:${QHEX[s.state]}">${QN[s.state]}</span> · ${s.ticker} ${s.name}<br>RS-Ratio ${s.ratio} · RS-Mom ${s.mom}<br>20日 ${s.ret20}% · Δ5动能 ${s.dMom5}`}));
  const W=560,H=560,pad=34;
  const xs=pts.map(p=>p.x),ys=pts.map(p=>p.y);
  const xmin=Math.min(96,...xs)-.5,xmax=Math.max(104,...xs)+.5;
  const ymin=Math.min(96,...ys)-.5,ymax=Math.max(104,...ys)+.5;
  const sx=v=>pad+(v-xmin)/(xmax-xmin)*(W-2*pad);
  const sy=v=>H-pad-(v-ymin)/(ymax-ymin)*(H-2*pad);
  const x100=sx(100),y100=sy(100);
  let svg=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="RRG scatter">`;
  // quadrant fills
  svg+=`<rect x="${x100}" y="${pad}" width="${W-pad-x100}" height="${y100-pad}" fill="#22c55e" opacity=".06"/>`;
  svg+=`<rect x="${pad}" y="${pad}" width="${x100-pad}" height="${y100-pad}" fill="#3b82f6" opacity=".06"/>`;
  svg+=`<rect x="${pad}" y="${y100}" width="${x100-pad}" height="${H-pad-y100}" fill="#ef4444" opacity=".06"/>`;
  svg+=`<rect x="${x100}" y="${y100}" width="${W-pad-x100}" height="${H-pad-y100}" fill="#f59e0b" opacity=".07"/>`;
  svg+=`<line x1="${pad}" y1="${y100}" x2="${W-pad}" y2="${y100}" stroke="#3a4356" stroke-width="1"/>`;
  svg+=`<line x1="${x100}" y1="${pad}" x2="${x100}" y2="${H-pad}" stroke="#3a4356" stroke-width="1"/>`;
  svg+=`<text class="qlabel" x="${W-pad-4}" y="${pad+14}" text-anchor="end" fill="#22c55e">领先 Leading</text>`;
  svg+=`<text class="qlabel" x="${pad+4}" y="${pad+14}" fill="#3b82f6">改善 Improving</text>`;
  svg+=`<text class="qlabel" x="${pad+4}" y="${H-pad-6}" fill="#ef4444">落后 Lagging</text>`;
  svg+=`<text class="qlabel" x="${W-pad-4}" y="${H-pad-6}" text-anchor="end" fill="#f59e0b">转弱 Weakening</text>`;
  svg+=`<text x="${W/2}" y="${H-6}" text-anchor="middle" fill="#7d8798" font-size="11" font-family="var(--mono)">JdK RS-Ratio →</text>`;
  pts.forEach((p,i)=>{
    const cx=sx(p.x),cy=sy(p.y);
    const gold=p.g?`<circle cx="${cx}" cy="${cy}" r="${p.r+3}" fill="none" stroke="#facc15" stroke-width="2"/>`:'';
    svg+=gold+`<circle class="dot" data-i="${i}" cx="${cx}" cy="${cy}" r="${p.r}" fill="${QHEX[p.st]}" opacity=".9"/>`;
    if(mode==='subs') svg+=`<text x="${cx+p.r+3}" y="${cy+3}" font-size="10" fill="#c7cedb" font-family="var(--mono)">${p.lab}</text>`;
  });
  svg+=`</svg>`;
  const box=document.getElementById('plot');box.innerHTML=svg;
  box.querySelectorAll('.dot').forEach(d=>{
    const p=pts[+d.dataset.i];
    d.addEventListener('mousemove',e=>showTip(p.tip,e));
    d.addEventListener('mouseleave',hideTip);
  });
}

document.getElementById('modeTog').addEventListener('click',e=>{
  const b=e.target.closest('button'); if(!b)return;
  document.querySelectorAll('#modeTog button').forEach(x=>x.classList.remove('on'));
  b.classList.add('on'); drawPlot(b.dataset.m);
});

// ---------- tiles grouped by sub-sector ----------
let activeFilter=null;
const subMap={}; DATA.subs.forEach(s=>subMap[s.sub]=s);
function drawGroups(){
  const host=document.getElementById('groups');host.innerHTML='';
  DATA.groups.forEach(g=>{
    if(activeFilter && g!==activeFilter) return;
    const items=DATA.stocks.filter(s=>s.sub===g)
      .sort((a,b)=> (b.strengthening-a.strengthening)|| (b.mom-a.mom));
    if(!items.length) return;
    const gs=subMap[g];
    const div=document.createElement('div');div.className='group';
    let html=`<div class="ghead"><span class="gname">${g}</span>`;
    if(gs) html+=`<span class="gq" style="background:${QHEX[gs.state]}22;color:${QHEX[gs.state]}">${QN[gs.state]} · R${gs.ratio} M${gs.mom}</span>`;
    html+=`<span class="gn">${items.length}只</span></div><div class="tiles">`;
    items.forEach(s=>{
      html+=`<div class="tile ${s.strengthening?'gold':''}" style="border-left-color:${QHEX[s.state]}">
        <div class="tk">${s.ticker}</div><div class="nm">${s.name}</div>
        <div class="rm"><span>R <b>${s.ratio}</b></span><span>M <b>${s.mom}</b></span></div></div>`;
    });
    html+=`</div>`;div.innerHTML=html;host.appendChild(div);
  });
}
function drawFilters(){
  const f=document.getElementById('filters');
  f.innerHTML=`<span class="chip ${!activeFilter?'on':''}" data-g="">全部</span>`+
    DATA.groups.map(g=>`<span class="chip ${activeFilter===g?'on':''}" data-g="${g}">${g}</span>`).join('');
  f.querySelectorAll('.chip').forEach(c=>c.addEventListener('click',()=>{
    activeFilter=c.dataset.g||null;drawFilters();drawGroups();
  }));
}

const tally={};DATA.stocks.forEach(s=>tally[s.state]=(tally[s.state]||0)+1);
document.getElementById('foot').innerHTML =
 `个股象限分布：领先Q1 ${tally.Lead||0} · 改善Q2 ${tally.Impr||0} · 转弱Q4 ${tally.Weak||0} · 落后Q3 ${tally.Lag||0}　|　`+
 `走强(金边) ${DATA.stocks.filter(s=>s.strengthening).length} 只　|　基准 ${DATA.bench}　|　`+
 `RRG = 相对QQQ的强度趋势(横)与动能(纵)，坐标100为分界。仅供研究，非投资建议。`;

window.addEventListener('mousemove',e=>{if(tip.style.opacity==1)moveTip(e);});
drawPlot('subs');drawFilters();drawGroups();
</script>
"""

html = HTML.replace("__DATA__", DATA_JS)
path = os.path.join(OUT, "tech_panel.html")
with open(path, "w", encoding="utf-8") as f:
    f.write(html)
print("saved:", path, "size", round(len(html)/1024, 1), "KB")
