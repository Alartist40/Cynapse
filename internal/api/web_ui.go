package api

// webUI is the single-file graph visualisation app served at GET /.
// It is embedded in the binary — no separate web/ directory needed.
const webUI = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CYNAPSE — DENDRITE</title>
<script src="/d3.min.js"></script>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Space+Mono:ital,wght@0,400;0,700;1,400&family=Syne:wght@400;600;800&display=swap');

  :root {
    --bg:#080b10;--surface:#0d1117;--surface2:#161b24;--border:#1e2733;
    --purple:#9b59b6;--purple-dim:#6c3483;--orange:#e67e22;--orange-dim:#a04000;
    --cyan:#00d4ff;--green:#2ecc71;--red:#e74c3c;--text:#c9d1d9;
    --text-dim:#4a5568;--text-bright:#f0f6fc;
    --mono:'Space Mono',monospace;--sans:'Syne',sans-serif;
  }
  *{box-sizing:border-box;margin:0;padding:0}
  html,body{width:100%;height:100%;background:var(--bg);color:var(--text);font-family:var(--mono);overflow:hidden}
  #app{display:flex;width:100vw;height:100vh}

  /* Sidebar */
  #sidebar{width:320px;min-width:280px;background:var(--surface);border-right:1px solid var(--border);display:flex;flex-direction:column;z-index:10}
  #header{padding:20px 20px 16px;border-bottom:1px solid var(--border)}
  #logo{font-family:var(--sans);font-weight:800;font-size:18px;color:var(--purple);letter-spacing:.12em;text-transform:uppercase}
  #logo span{color:var(--orange)}
  #subtitle{font-size:10px;color:var(--text-dim);letter-spacing:.08em;margin-top:4px}
  #search-wrap{padding:12px 16px;border-bottom:1px solid var(--border)}
  #search{width:100%;background:var(--surface2);border:1px solid var(--border);border-radius:4px;color:var(--text);font-family:var(--mono);font-size:12px;padding:8px 10px;outline:none;transition:border-color .2s}
  #search:focus{border-color:var(--purple)}
  :focus-visible{outline:2px solid var(--purple);outline-offset:2px}
  #search::placeholder{color:var(--text-dim)}
  #stats{display:flex;border-bottom:1px solid var(--border)}
  .stat{flex:1;text-align:center;padding:10px 0;border-right:1px solid var(--border)}
  .stat:last-child{border-right:none}
  .stat-val{font-family:var(--sans);font-size:20px;font-weight:800;color:var(--purple)}
  .stat-lbl{font-size:9px;color:var(--text-dim);letter-spacing:.1em;text-transform:uppercase}
  #node-list{flex:1;overflow-y:auto}
  #node-list::-webkit-scrollbar{width:4px}
  #node-list::-webkit-scrollbar-thumb{background:var(--border);border-radius:2px}
  .node-item{padding:10px 16px;border-bottom:1px solid var(--border);cursor:pointer;transition:background .15s;display:flex;align-items:flex-start;gap:10px}
  .node-item:hover{background:var(--surface2)}
  .node-item.active{background:rgba(155,89,182,.12);border-left:2px solid var(--purple)}
  .node-type-dot{width:8px;height:8px;border-radius:50%;margin-top:5px;flex-shrink:0}
  .node-item-content{flex:1;min-width:0}
  .node-item-title{font-family:var(--sans);font-size:13px;font-weight:600;color:var(--text-bright);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .node-item-meta{font-size:10px;color:var(--text-dim);margin-top:2px}

  /* Graph area */
  #dendrite-area{flex:1;position:relative;overflow:hidden}
  #canvas{width:100%;height:100%}
  #toolbar{position:absolute;top:16px;left:16px;display:flex;gap:8px;z-index:5}
  .tool-btn{background:var(--surface);border:1px solid var(--border);border-radius:4px;color:var(--text-dim);font-family:var(--mono);font-size:11px;padding:6px 12px;cursor:pointer;transition:all .15s}
  .tool-btn:hover{border-color:var(--purple);color:var(--purple)}
  #add-btn{position:absolute;bottom:20px;left:50%;transform:translateX(-50%);background:var(--purple);border:none;border-radius:4px;color:#fff;font-family:var(--mono);font-size:12px;padding:10px 24px;cursor:pointer;letter-spacing:.08em;transition:background .15s,transform .15s;z-index:5}
  #add-btn:hover{background:var(--purple-dim);transform:translateX(-50%) translateY(-1px)}
  #legend{position:absolute;bottom:20px;right:20px;background:var(--surface);border:1px solid var(--border);border-radius:6px;padding:12px 14px;z-index:5}
  .legend-title{font-size:9px;color:var(--text-dim);letter-spacing:.1em;text-transform:uppercase;margin-bottom:8px}
  .legend-item{display:flex;align-items:center;gap:8px;margin-bottom:5px;font-size:11px;color:var(--text-dim)}
  .legend-dot{width:10px;height:10px;border-radius:50%}

  /* Detail panel */
  #detail{position:absolute;right:0;top:0;bottom:0;width:380px;background:var(--surface);border-left:1px solid var(--border);display:flex;flex-direction:column;transform:translateX(100%);transition:transform .25s ease;z-index:20}
  #detail.open{transform:translateX(0)}
  #detail-header{padding:16px 20px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:12px}
  #detail-close{background:none;border:none;color:var(--text-dim);cursor:pointer;font-size:18px;line-height:1;margin-left:auto;transition:color .15s}
  #detail-close:hover{color:var(--text-bright)}
  #detail-title{font-family:var(--sans);font-size:16px;font-weight:800;color:var(--text-bright)}
  #detail-body{flex:1;overflow-y:auto;padding:16px 20px;display:flex;flex-direction:column;gap:16px}
  #detail-body::-webkit-scrollbar{width:3px}
  #detail-body::-webkit-scrollbar-thumb{background:var(--border)}
  .detail-label{font-size:10px;color:var(--text-dim);letter-spacing:.1em;text-transform:uppercase;margin-bottom:6px}
  #detail-content{background:var(--surface2);border:1px solid var(--border);border-radius:4px;padding:10px;font-size:12px;line-height:1.7;color:var(--text);white-space:pre-wrap;word-break:break-word;max-height:200px;overflow-y:auto}
  .tag-list{display:flex;flex-wrap:wrap;gap:6px}
  .tag{background:rgba(155,89,182,.18);border:1px solid var(--purple-dim);color:var(--purple);font-size:10px;padding:2px 8px;border-radius:99px}
  .link-list{display:flex;flex-direction:column;gap:4px}
  .link-item{background:var(--surface2);border:1px solid var(--border);border-radius:4px;padding:6px 10px;font-size:11px;color:var(--text);cursor:pointer;display:flex;align-items:center;gap:8px;transition:border-color .15s}
  .link-item:hover{border-color:var(--purple);color:var(--text-bright)}
  .link-arrow{color:var(--text-dim);font-size:10px}

  /* Edit form */
  #edit-form{display:none;flex-direction:column;gap:10px;padding:16px 20px;overflow-y:auto}
  #edit-form.active{display:flex}
  .form-label{font-size:10px;color:var(--text-dim);letter-spacing:.1em;text-transform:uppercase;margin-bottom:4px}
  .form-input,.form-textarea,.form-select{width:100%;background:var(--surface2);border:1px solid var(--border);border-radius:4px;color:var(--text);font-family:var(--mono);font-size:12px;padding:8px 10px;outline:none;transition:border-color .2s}
  .form-input:focus,.form-textarea:focus,.form-select:focus{border-color:var(--purple)}
  .form-textarea{resize:vertical;min-height:140px;line-height:1.6}
  .form-hint{font-size:10px;color:var(--text-dim);margin-top:4px}
  .btn{font-family:var(--mono);font-size:11px;padding:7px 14px;border-radius:4px;border:1px solid;cursor:pointer;letter-spacing:.05em;transition:all .15s}
  .btn-primary{background:var(--purple);border-color:var(--purple);color:#fff}
  .btn-primary:hover{background:var(--purple-dim)}
  .btn-ghost{background:transparent;border-color:var(--border);color:var(--text-dim)}
  .btn-ghost:hover{border-color:var(--text-dim);color:var(--text)}
  .btn-danger{background:transparent;border-color:var(--red);color:var(--red)}
  .btn-danger:hover{background:var(--red);color:#fff}
  .btn-row{display:flex;gap:8px}

  /* Graph elements */
  .g-link{stroke:var(--border);stroke-width:1.5;stroke-opacity:.7}
  .g-link.highlighted{stroke:var(--purple);stroke-opacity:1;stroke-width:2}
  .g-node circle{stroke-width:2;cursor:pointer}
  .g-node circle:hover{filter:brightness(1.3)}
  .g-node.selected circle{stroke:var(--text-bright);stroke-width:3}
  .g-label{font-family:var(--sans);font-size:11px;font-weight:600;fill:var(--text);pointer-events:none;text-anchor:middle}
  .g-count{font-family:var(--mono);font-size:9px;fill:var(--text-dim);pointer-events:none;text-anchor:middle}

  /* Toast */
  #toast{position:fixed;bottom:60px;left:50%;transform:translateX(-50%) translateY(20px);background:var(--surface2);border:1px solid var(--border);border-radius:4px;padding:10px 20px;font-size:12px;color:var(--text);opacity:0;transition:opacity .2s,transform .2s;pointer-events:none;z-index:100;white-space:nowrap}
  #toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
</style>
</head>
<body>
<div id="app">
  <aside id="sidebar">
    <div id="header">
      <div id="logo">CYNAPSE <span>◆</span> DENDRITE</div>
      <div id="subtitle">NEURONS, BRANCHES, CONNECTIONS</div>
    </div>
    <div id="search-wrap">
      <input id="search" type="text" placeholder="Search nodes..." aria-label="Search nodes" autocomplete="off">
    </div>
    <div id="stats">
      <div class="stat"><div class="stat-val" id="stat-nodes">0</div><div class="stat-lbl">Nodes</div></div>
      <div class="stat"><div class="stat-val" id="stat-links">0</div><div class="stat-lbl">Links</div></div>
      <div class="stat"><div class="stat-val" id="stat-tags">0</div><div class="stat-lbl">Tags</div></div>
    </div>
    <div id="node-list"></div>
  </aside>

  <div id="dendrite-area">
    <div id="toolbar">
      <button class="tool-btn" onclick="resetZoom()">⟳ Reset</button>
      <button class="tool-btn" id="pause-btn" onclick="toggleForce()">⏸ Pause</button>
    </div>
    <svg id="canvas"></svg>
    <button id="add-btn" onclick="openNewNodeForm()">+ New Node</button>
    <div id="legend">
      <div class="legend-title">Node Types</div>
      <div class="legend-item"><div class="legend-dot" style="background:#9b59b6"></div>Identity</div>
      <div class="legend-item"><div class="legend-dot" style="background:#e67e22"></div>Person</div>
      <div class="legend-item"><div class="legend-dot" style="background:#00d4ff"></div>Project</div>
      <div class="legend-item"><div class="legend-dot" style="background:#2ecc71"></div>Concept</div>
      <div class="legend-item"><div class="legend-dot" style="background:#e74c3c"></div>Memory</div>
      <div class="legend-item"><div class="legend-dot" style="background:#f39c12"></div>Event</div>
      <div class="legend-item"><div class="legend-dot" style="background:#4a5568"></div>Custom</div>
    </div>
  </div>

  <div id="detail">
    <div id="detail-header">
      <div class="node-type-dot" id="detail-type-dot"></div>
      <div id="detail-title">Node</div>
      <button id="detail-close" aria-label="Close details" onclick="closeDetail()">✕</button>
    </div>
    <div id="detail-body">
      <div><div class="detail-label">Content</div><div id="detail-content"></div></div>
      <div id="detail-tags-section"><div class="detail-label">Tags</div><div class="tag-list" id="detail-tags"></div></div>
      <div id="detail-links-section"><div class="detail-label">Links To</div><div class="link-list" id="detail-links"></div></div>
      <div id="detail-backlinks-section"><div class="detail-label">Linked From</div><div class="link-list" id="detail-backlinks"></div></div>
      <div class="btn-row">
        <button class="btn btn-primary" onclick="openEditForm()">Edit</button>
        <button class="btn btn-danger" onclick="deleteNode()">Delete</button>
      </div>
    </div>
    <div id="edit-form">
      <div><div class="form-label">Title</div><input class="form-input" id="edit-title" type="text" placeholder="Node title"></div>
      <div>
        <div class="form-label">Type</div>
        <select class="form-select" id="edit-type">
          <option value="identity">Identity</option><option value="person">Person</option>
          <option value="project">Project</option><option value="concept">Concept</option>
          <option value="memory">Memory</option><option value="event">Event</option>
          <option value="custom">Custom</option>
        </select>
      </div>
      <div>
        <div class="form-label">Content</div>
        <textarea class="form-textarea" id="edit-content" placeholder="Markdown content. Use [[node-id]] to link. Use #tag for tags."></textarea>
        <div class="form-hint">[[node-id]] creates links · #tag adds tags</div>
      </div>
      <div class="btn-row">
        <button class="btn btn-primary" onclick="saveNode()">Save</button>
        <button class="btn btn-ghost" onclick="cancelEdit()">Cancel</button>
      </div>
    </div>
  </div>
</div>
<div id="toast"></div>

<script>
const TYPE_COLORS={identity:'#9b59b6',person:'#e67e22',project:'#00d4ff',concept:'#2ecc71',memory:'#e74c3c',event:'#f39c12',custom:'#4a5568'};
function typeColor(t){return TYPE_COLORS[t]||TYPE_COLORS.custom}

let dendriteData={nodes:[],links:[]},allNodes=[],selected=null,simulation=null,svg,g,linkSel,nodeSel,forcePaused=false,zoom,isNewNode=false;

window.addEventListener('DOMContentLoaded',async()=>{initGraph();await loadData();setInterval(loadData,10000)});

async function loadData(){
  try{
    const[gr,nr]=await Promise.all([fetch('/api/dendrite'),fetch('/api/nodes')]);
    dendriteData=await gr.json();allNodes=await nr.json();
    updateStats();renderNodeList(allNodes);updateGraph();
  }catch(e){toast('⚠ Cannot reach API')}
}

function updateStats(){
  document.getElementById('stat-nodes').textContent=dendriteData.nodes.length;
  document.getElementById('stat-links').textContent=dendriteData.links.length;
  const ts=new Set();allNodes.forEach(n=>(n.tags||[]).forEach(t=>ts.add(t)));
  document.getElementById('stat-tags').textContent=ts.size;
}

function renderNodeList(nodes){
  const list=document.getElementById('node-list');list.innerHTML='';
  (nodes||[]).forEach(n=>{
    const item=document.createElement('div');item.className='node-item'+(selected&&selected.id===n.id?' active':'');item.dataset.id=n.id;item.onclick=()=>selectNode(n.id);
    const dot=document.createElement('div');dot.className='node-type-dot';dot.style.background=typeColor(n.type);
    const content=document.createElement('div');content.className='node-item-content';
    const title=document.createElement('div');title.className='node-item-title';title.textContent=n.title||n.id;
    const meta=document.createElement('div');meta.className='node-item-meta';
    const lc=(n.links||[]).length+(n.backlinks||[]).length;
    meta.textContent=n.type+(lc?'  ·  '+lc+' connections':'');
    content.appendChild(title);content.appendChild(meta);item.appendChild(dot);item.appendChild(content);list.appendChild(item);
  });
}

function initGraph(){
  const area=document.getElementById('dendrite-area');
  const w=area.clientWidth,h=area.clientHeight;
  svg=d3.select('#canvas').attr('width',w).attr('height',h);
  const defs=svg.append('defs');
  const rg=defs.append('radialGradient').attr('id','bg-g').attr('cx','50%').attr('cy','50%').attr('r','70%');
  rg.append('stop').attr('offset','0%').attr('stop-color','#0d1117');
  rg.append('stop').attr('offset','100%').attr('stop-color','#080b10');
  svg.append('rect').attr('width',w).attr('height',h).attr('fill','url(#bg-g)');
  zoom=d3.zoom().scaleExtent([0.1,5]).on('zoom',e=>g.attr('transform',e.transform));
  svg.call(zoom);g=svg.append('g');
  g.append('g').attr('class','links-layer');g.append('g').attr('class','nodes-layer');
  simulation=d3.forceSimulation()
    .force('link',d3.forceLink().id(d=>d.id).distance(130))
    .force('charge',d3.forceManyBody().strength(-400))
    .force('center',d3.forceCenter(w/2,h/2))
    .force('collision',d3.forceCollide(42));
  window.addEventListener('resize',()=>{
    const nw=area.clientWidth,nh=area.clientHeight;
    svg.attr('width',nw).attr('height',nh);
    simulation.force('center',d3.forceCenter(nw/2,nh/2)).alpha(0.1).restart();
  });
}

function updateGraph(){
  const nodes=(dendriteData.nodes||[]).map(d=>({...d}));
  const links=(dendriteData.links||[]).map(d=>({...d}));
  const pos={};
  if(simulation.nodes){simulation.nodes().forEach(n=>{pos[n.id]={x:n.x,y:n.y}})}
  nodes.forEach(n=>{if(pos[n.id]){n.x=pos[n.id].x;n.y=pos[n.id].y}});

  const defs=svg.select('defs');
  if(defs.select('#arrow').empty()){
    defs.append('marker').attr('id','arrow').attr('viewBox','0 -4 8 8').attr('refX',22).attr('refY',0).attr('markerWidth',6).attr('markerHeight',6).attr('orient','auto')
      .append('path').attr('d','M0,-4L8,0L0,4').attr('fill','#1e2733');
  }

  linkSel=g.select('.links-layer').selectAll('.g-link').data(links,d=>d.source+'-'+d.target);
  linkSel.exit().remove();
  linkSel=linkSel.enter().append('line').attr('class','g-link').attr('marker-end','url(#arrow)').merge(linkSel);

  const ng=g.select('.nodes-layer').selectAll('.g-node').data(nodes,d=>d.id);
  ng.exit().remove();
  const entered=ng.enter().append('g').attr('class','g-node')
    .call(d3.drag().on('start',dragStart).on('drag',dragging).on('end',dragEnd))
    .on('click',(e,d)=>{e.stopPropagation();selectNode(d.id)});
  entered.append('circle');
  entered.append('text').attr('class','g-label').attr('dy',28);
  entered.append('text').attr('class','g-count').attr('dy',40);
  nodeSel=entered.merge(ng);
  nodeSel.select('circle').attr('r',d=>14+Math.min((d.link_count||0)*1.5,14)).attr('fill',d=>typeColor(d.type)).attr('fill-opacity',.85).attr('stroke',d=>typeColor(d.type));
  nodeSel.select('.g-label').text(d=>(d.title||d.id).length>14?(d.title||d.id).slice(0,14)+'…':d.title||d.id);
  nodeSel.select('.g-count').text(d=>(d.link_count||0)>0?d.link_count+' links':'');
  svg.on('click',()=>{if(selected){selected=null;updateSel()}});
  simulation.nodes(nodes).on('tick',ticked);
  simulation.force('link').links(links);
  simulation.alpha(0.3).restart();
}

function ticked(){
  linkSel.attr('x1',d=>d.source.x).attr('y1',d=>d.source.y).attr('x2',d=>d.target.x).attr('y2',d=>d.target.y);
  nodeSel.attr('transform',d=>'translate('+d.x+','+d.y+')');
}
function dragStart(e,d){if(!e.active)simulation.alphaTarget(0.3).restart();d.fx=d.x;d.fy=d.y}
function dragging(e,d){d.fx=e.x;d.fy=e.y}
function dragEnd(e,d){if(!e.active)simulation.alphaTarget(0);d.fx=null;d.fy=null}
function resetZoom(){svg.transition().duration(500).call(zoom.transform,d3.zoomIdentity)}
function toggleForce(){
  forcePaused=!forcePaused;
  const btn=document.getElementById('pause-btn');
  if(forcePaused){simulation.stop();btn.textContent='▶ Resume'}
  else{simulation.alphaTarget(0.1).restart();btn.textContent='⏸ Pause'}
}
function updateSel(){nodeSel&&nodeSel.classed('selected',d=>selected&&d.id===selected.id)}

async function selectNode(id){
  try{
    const r=await fetch('/api/nodes/'+id);if(!r.ok)return;
    selected=await r.json();openDetail(selected);updateSel();
    linkSel&&linkSel.classed('highlighted',d=>{
      const s=typeof d.source==='object'?d.source.id:d.source;
      const t=typeof d.target==='object'?d.target.id:d.target;
      return s===id||t===id;
    });
    document.querySelectorAll('.node-item').forEach(el=>el.classList.toggle('active',el.dataset.id===id));
  }catch(e){console.error(e)}
}

function openDetail(node){
  const panel=document.getElementById('detail');
  document.getElementById('edit-form').classList.remove('active');
  document.getElementById('detail-body').style.display='flex';
  document.getElementById('detail-title').textContent=node.title;
  document.getElementById('detail-type-dot').style.background=typeColor(node.type);
  document.getElementById('detail-content').textContent=node.content||'(empty)';
  const tagsEl=document.getElementById('detail-tags');tagsEl.innerHTML='';
  (node.tags||[]).forEach(t=>{const el=document.createElement('span');el.className='tag';el.textContent='#'+t;tagsEl.appendChild(el)});
  document.getElementById('detail-tags-section').style.display=(node.tags||[]).length?'block':'none';
  renderLinkList('detail-links',node.links||[],'→');
  document.getElementById('detail-links-section').style.display=(node.links||[]).length?'block':'none';
  renderLinkList('detail-backlinks',node.backlinks||[],'←');
  document.getElementById('detail-backlinks-section').style.display=(node.backlinks||[]).length?'block':'none';
  panel.classList.add('open');
}

function renderLinkList(cid,ids,arrow){
  const el=document.getElementById(cid);el.innerHTML='';
  ids.forEach(id=>{
    const node=allNodes.find(n=>n.id===id);
    const item=document.createElement('div');item.className='link-item';item.onclick=()=>selectNode(id);
    const dot=document.createElement('div');dot.className='node-type-dot';dot.style.background=typeColor(node?node.type:'custom');
    const ar=document.createElement('span');ar.className='link-arrow';ar.textContent=arrow;
    const label=document.createElement('span');label.textContent=node?node.title:id;
    item.appendChild(dot);item.appendChild(ar);item.appendChild(label);el.appendChild(item);
  });
}

function closeDetail(){
  document.getElementById('detail').classList.remove('open');
  selected=null;updateSel();
  linkSel&&linkSel.classed('highlighted',false);
  document.querySelectorAll('.node-item').forEach(el=>el.classList.remove('active'));
}

function openEditForm(){
  if(!selected)return;isNewNode=false;
  document.getElementById('edit-title').value=selected.title;
  document.getElementById('edit-type').value=selected.type||'custom';
  document.getElementById('edit-content').value=selected.content;
  document.getElementById('detail-body').style.display='none';
  document.getElementById('edit-form').classList.add('active');
}

function openNewNodeForm(){
  isNewNode=true;selected=null;closeDetail();
  document.getElementById('edit-title').value='';
  document.getElementById('edit-type').value='custom';
  document.getElementById('edit-content').value='';
  document.getElementById('detail-body').style.display='none';
  document.getElementById('edit-form').classList.add('active');
  document.getElementById('detail').classList.add('open');
  document.getElementById('detail-title').textContent='New Node';
}

function cancelEdit(){
  document.getElementById('edit-form').classList.remove('active');
  if(selected){document.getElementById('detail-body').style.display='flex'}
  else{document.getElementById('detail').classList.remove('open')}
}

async function saveNode(){
  const title=document.getElementById('edit-title').value.trim();
  const type=document.getElementById('edit-type').value;
  const content=document.getElementById('edit-content').value;
  if(!title){toast('Title is required');return}
  try{
    if(isNewNode){
      const id=title.toLowerCase().replace(/\s+/g,'_').replace(/[^a-z0-9_-]/g,'');
      const r=await fetch('/api/nodes',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,title,type,content})});
      if(!r.ok)throw new Error(await r.text());
      toast('✓ Node created');
    }else{
      const r=await fetch('/api/nodes/'+selected.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({title,type,content})});
      if(!r.ok)throw new Error(await r.text());
      toast('✓ Saved');
    }
    document.getElementById('edit-form').classList.remove('active');
    await loadData();
    if(!isNewNode&&selected)selectNode(selected.id);else closeDetail();
  }catch(e){toast('Error: '+e.message)}
}

async function deleteNode(){
  if(!selected)return;
  if(!confirm('Delete "'+selected.title+'"?'))return;
  try{
    const r=await fetch('/api/nodes/'+selected.id,{method:'DELETE'});
    if(!r.ok)throw new Error(await r.text());
    toast('✓ Deleted');closeDetail();await loadData();
  }catch(e){toast('Error: '+e.message)}
}

document.getElementById('search').addEventListener('input',async e=>{
  const q=e.target.value.trim();
  if(!q){renderNodeList(allNodes);nodeSel&&nodeSel.select('circle').attr('fill-opacity',.85);return}
  try{
    const r=await fetch('/api/search?q='+encodeURIComponent(q));
    const results=await r.json()||[];
    renderNodeList(results);
    nodeSel&&nodeSel.select('circle').attr('fill-opacity',d=>results.some(r=>r.id===d.id)?0.9:0.12);
  }catch(e){console.error(e)}
});

function toast(msg){
  const el=document.getElementById('toast');el.textContent=msg;el.classList.add('show');
  setTimeout(()=>el.classList.remove('show'),2500);
}
</script>
</body>
</html>`
