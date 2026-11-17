/* SZL Public Frontier Atlas — original WebGL estate explorer, Apache-2.0.
 * Read-only public HF metadata + dated explicit topology. The field is
 * illustrative; none of the rendered light is execution or safety evidence.
 */
import * as THREE from './vendor/three.module.js';
import { OrbitControls } from './vendor/OrbitControls.js';

const SCHEMA = 'szl.public-hub-holographic-atlas/v1';
const COLORS = Object.freeze({
  vertical: 0x70a6ff, space: 0x50efdd, model: 0xb19aff, dataset: 0xffd58c
});
const $ = id => document.getElementById(id);
const stage = $('viewport');
const prefersReduced = matchMedia('(prefers-reduced-motion: reduce)');
const params = new URLSearchParams(location.search);
let snapshot = null;
let nodes = [];
let visible = [];
let selectedId = null;
let scene, camera, renderer, controls, mesh, linkLines, halo;
let rotator = false;
let animationRequested = true;
let timer = 0;
const positions = new Map();
const ray = new THREE.Raycaster();
const ndc = new THREE.Vector2();

const strictSha = v => typeof v === 'string' && /^[0-9a-f]{40}$/.test(v);
const validNode = n => n && typeof n.id === 'string'
  && ['vertical','space','model','dataset'].includes(n.kind)
  && typeof n.label === 'string' && n.label.length <= 128
  && n.execution_authorized === false
  && (n.kind === 'vertical' || (
    typeof n.hub_id === 'string' && n.hub_id.startsWith('SZLHOLDINGS/')
    && typeof n.url === 'string' && n.url.startsWith('https://huggingface.co/')
    && Array.isArray(n.verticals)
  ));

function validate(payload) {
  if (!payload || payload.schema !== SCHEMA
      || payload.state !== 'OBSERVED_PUBLIC_HUB_METADATA'
      || payload.scope !== 'ANONYMOUS_PUBLIC_HUB_ONLY'
      || payload.private_assets_excluded !== true
      || payload.production_qualified !== false
      || payload.execution_authorized !== false
      || payload.runtime_readiness !== 'NOT_EVALUATED'
      || !/^[0-9a-f]{64}$/.test(payload.observation_sha256 || '')
      || !Array.isArray(payload.nodes) || !Array.isArray(payload.links)
      || payload.nodes.length > 1050 || payload.links.length > 2000
      || !payload.nodes.every(validNode)
      || new Set(payload.nodes.map(n => n.id)).size !== payload.nodes.length) {
    throw new Error('Atlas evidence schema or privacy boundary invalid');
  }
  const ids = new Set(payload.nodes.map(n => n.id));
  if (!payload.links.every(l => ids.has(l.source) && ids.has(l.target)
      && l.kind === 'DECLARED_MEMBERSHIP_MATCHED_TO_PUBLIC_HUB')) {
    throw new Error('Unverified topology edge');
  }
  for (const kind of ['space','model','dataset']) {
    if (!Number.isInteger(payload.counts?.[kind])
        || payload.counts[kind] !== payload.nodes.filter(n => n.kind === kind).length) {
      throw new Error('Public asset cardinality does not match');
    }
  }
  return payload;
}

function make(tag, className, str) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (str !== undefined && str !== null) node.textContent = String(str);
  return node;
}
function FNV(id) {
  let h = 2166136261;
  for (let i = 0; i < id.length; i++) {
    h ^= id.charCodeAt(i); h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}
function evidenceText(node) {
  if (node.kind === 'vertical') return 'Historical source declaration';
  return 'Public Hub metadata · NOT a readiness claim';
}
function short(v) { return strictSha(v) ? v.slice(0,12) : 'NOT OBSERVED'; }
function labelForKind(kind) {
  return {vertical:'VERTICAL',space:'SPACE',model:'MODEL',dataset:'DATASET'}[kind] || 'UNKNOWN';
}

function emitData(data) {
  snapshot = validate(data);
  nodes = data.nodes;
  $('count-space').textContent = data.counts.space;
  $('count-model').textContent = data.counts.model;
  $('count-dataset').textContent = data.counts.dataset;
  $('count-vertical').textContent = data.declared_verticals;
  $('timestamp').textContent = 'OBSERVED ' + data.observed_at + ' / 300s cache';
  $('status').textContent = 'PUBLIC HUB / METADATA OBSERVED';
  $('view-message').textContent = 'ANONYMOUS PUBLIC HUB · TOPOLOGY DECLARED';
  $('export').disabled = false;
  const select = $('vertical');
  for (const item of nodes.filter(n => n.kind === 'vertical')) {
    const option = document.createElement('option');
    option.value = item.vertical_id;
    option.textContent = item.label;
    select.appendChild(option);
  }
  const deep = params.get('space') || params.get('model') || params.get('dataset') || '';
  const target = nodes.find(n => n.hub_id === deep) ||
    nodes.find(n => n.vertical_id && n.vertical_id === params.get('vertical'));
  if (target?.kind === 'vertical') select.value = target.vertical_id;
  filterAndRender();
  if (target) choose(target.id);
}

function passes(node) {
  const types = [...document.querySelectorAll('.switch input:checked')].map(x => x.value);
  if (!types.includes(node.kind)) return false;
  const choice = $('vertical').value;
  if (choice === 'unassigned' && (node.kind === 'vertical' || node.verticals.length !== 0)) return false;
  if (choice !== 'all' && choice !== 'unassigned'
      && (node.kind === 'vertical' ? node.vertical_id !== choice
        : !node.verticals.includes(choice))) return false;
  const query = $('search').value.trim().toLowerCase();
  if (!query) return true;
  const fields = [node.label, node.kind, node.domain || '', node.hub_id || '',
    ...(Array.isArray(node.tags) ? node.tags : [])].join(' ').toLowerCase();
  return fields.includes(query);
}

function updateTable() {
  const tbody = $('asset-rows');
  tbody.replaceChildren();
  const current = nodes.filter((_n,i) => visible[i]).sort((a,b) => {
    const aKind = a.kind === 'vertical' ? -1 : ['space','model','dataset'].indexOf(a.kind);
    const bKind = b.kind === 'vertical' ? -1 : ['space','model','dataset'].indexOf(b.kind);
    return aKind-bKind || a.label.localeCompare(b.label);
  });
  $('directory-result').textContent = current.length + ' matching public or dated-declared nodes. Assets with no declared vertical are not silently assigned.';
  const fragment = document.createDocumentFragment();
  for (const item of current) {
    const tr = document.createElement('tr');
    const title = document.createElement('td');
    const a = document.createElement('a');
    if (item.kind === 'vertical') {
      a.href = '?vertical=' + encodeURIComponent(item.vertical_id);
    } else {
      a.href = item.url;
      a.target = '_blank';
      a.rel = 'noopener noreferrer';
    }
    a.textContent = item.label;
    title.appendChild(a);
    const category = make('td','',labelForKind(item.kind));
    const vertical = make('td','',
      item.kind === 'vertical' ? 'Legacy declared group' :
      item.verticals.length ? item.verticals.join(', ') : 'Unassigned in dated topology');
    const provenance = make('td','',evidenceText(item));
    tr.append(title,category,vertical,provenance);
    fragment.appendChild(tr);
  }
  if (!current.length) {
    const tr=make('tr');
    const td=make('td','','No matching public entities.');
    td.colSpan=4; tr.appendChild(td); fragment.appendChild(tr);
  }
  tbody.appendChild(fragment);
}

function filterAndRender() {
  if (!snapshot) return;
  visible = nodes.map(passes);
  const count = visible.filter(Boolean).length;
  $('visible-count').textContent = count + ' visible / ' + nodes.length;
  updateTable();
  if (mesh) {
    const dummy = new THREE.Object3D();
    for (let i=0;i<nodes.length;i++) {
      const n=nodes[i];
      dummy.position.copy(positions.get(n.id));
      const scale = visible[i] ? (n.kind === 'vertical' ? 2.25 : n.kind === 'space' ? 1.45 : n.kind === 'model' ? .94 : .88) : 0.00001;
      dummy.scale.setScalar(scale);
      dummy.updateMatrix();
      mesh.setMatrixAt(i,dummy.matrix);
    }
    mesh.instanceMatrix.needsUpdate = true;
    buildEdges();
    if (selectedId && !visible[nodes.findIndex(n=>n.id===selectedId)]) choose(null);
  }
}

function showSelected(node) {
  const kind = $('selected-kind'), name = $('selected-name'), sub = $('selected-sub');
  const dl = $('metadata');
  dl.replaceChildren();
  if (!node) {
    kind.textContent='NO ENTITY SELECTED';name.textContent='Select any point of light.';
    sub.textContent='Click a node or select from the directory; private resources are not in the public graph.';
    $('open-asset').href='https://huggingface.co/SZLHOLDINGS';
    return;
  }
  kind.textContent = labelForKind(node.kind) + ' / ' + node.evidence_state;
  name.textContent = node.label;
  sub.textContent = evidenceText(node);
  const items = [
    ['Identity', node.hub_id || node.vertical_id],
    ['Declared vertical', node.kind === 'vertical' ? node.domain || '—' :
      node.verticals.length ? node.verticals.join(' · ') : 'Unassigned'],
    ['Revision', short(node.source_revision)],
    ['Modified (Hub)', node.last_modified || 'UNAVAILABLE'],
    ['SDK', node.sdk || 'NOT APPLICABLE'],
    ['Tags', (node.tags || []).slice(0,5).join(' · ') || '—'],
    ['Readiness', 'NOT EVALUATED'],
    ['Action authority', 'DENIED / NOT GRANTED'],
  ];
  for (const [k,v] of items) {
    const row=make('div');
    row.append(make('dt','',k),make('dd','',v));
    dl.appendChild(row);
  }
  $('open-asset').href = node.url || ('?vertical='+encodeURIComponent(node.vertical_id));
  $('open-asset').textContent = node.kind === 'vertical'
    ? 'Explore this vertical lens ↗' : 'Open official Hugging Face asset ↗';
}

function choose(id) {
  selectedId=id;
  const node = nodes.find(n=>n.id===id);
  showSelected(node);
  if (halo) {
    halo.visible=!!node;
    if(node) {halo.position.copy(positions.get(node.id));halo.material.color.setHex(COLORS[node.kind]);}
  }
  if(node) {
    const next = new URL(location.href);
    next.search = '';
    if(node.kind === 'vertical') next.searchParams.set('vertical',node.vertical_id);
    else next.searchParams.set(node.kind,node.hub_id);
    history.replaceState(null,'',next);
  }
}

function stablePositions() {
  const center = new Map();
  const verticals = nodes.filter(n=>n.kind === 'vertical');
  verticals.forEach((node,i) => {
    const angle=i*Math.PI*2/Math.max(1,verticals.length);
    center.set(node.vertical_id,new THREE.Vector3(Math.cos(angle)*23,(i%3-1)*8,Math.sin(angle)*23));
  });
  const grouped = new Map();
  for(const n of nodes.filter(x=>x.kind !== 'vertical')) {
    const key=n.verticals?.[0] || 'unassigned';
    if(!grouped.has(key))grouped.set(key,[]);
    grouped.get(key).push(n);
  }
  for(const n of verticals)positions.set(n.id,center.get(n.vertical_id));
  for(const [key,items] of grouped) {
    items.sort((a,b)=>a.id.localeCompare(b.id));
    items.forEach((n,i)=>{
      const seed=FNV(n.id);
      const phi=(i*2.399963229728653 + (seed%100)/100) % (Math.PI*2);
      const row=Math.sqrt(i+1);
      const base=key==='unassigned' ? new THREE.Vector3(0,0,0) : center.get(key);
      const radius=key==='unassigned' ? 45+row*1.7 : 5.5+row*2.2;
      const y=key==='unassigned'
        ? ((seed%3300)/100 - 16.5)*1.65
        : ((i%11)-5)*2.3;
      positions.set(n.id,new THREE.Vector3(
        base.x+Math.cos(phi)*radius,
        base.y+y,
        base.z+Math.sin(phi)*radius
      ));
    });
  }
}

function buildEdges() {
  if (!scene) return;
  if(linkLines) {
    scene.remove(linkLines);
    linkLines.geometry.dispose();
    linkLines.material.dispose();
  }
  const idIndex=new Map(nodes.map((n,i)=>[n.id,i]));
  const coords=[];
  for(const edge of snapshot.links) {
    const ai=idIndex.get(edge.source),bi=idIndex.get(edge.target);
    if(ai===undefined||bi===undefined||!visible[ai]||!visible[bi])continue;
    const a=positions.get(edge.source),b=positions.get(edge.target);
    coords.push(a.x,a.y,a.z,b.x,b.y,b.z);
  }
  const geo=new THREE.BufferGeometry();
  geo.setAttribute('position',new THREE.Float32BufferAttribute(coords,3));
  linkLines=new THREE.LineSegments(geo,
    new THREE.LineBasicMaterial({color:0x66c7d8,transparent:true,opacity:.35,depthWrite:false}));
  scene.add(linkLines);
}

function install3D() {
  if(!snapshot)throw new Error('PUBLIC_METADATA_NOT_LOADED');
  const w=Math.max(400,stage.clientWidth),h=Math.max(350,stage.clientHeight);
  renderer=new THREE.WebGLRenderer({antialias:true,alpha:true,powerPreference:'low-power'});
  renderer.setPixelRatio(Math.min(devicePixelRatio||1,1.6));
  renderer.setSize(w,h);
  renderer.setClearColor(0x050a13,0);
  renderer.domElement.setAttribute('aria-label','Interactive 3D graph of public Hub metadata');
  renderer.domElement.setAttribute('tabindex','0');
  stage.prepend(renderer.domElement);
  scene=new THREE.Scene();
  scene.fog=new THREE.FogExp2(0x040914,.0042);
  camera=new THREE.PerspectiveCamera(58,w/h,.1,500);
  camera.position.set(0,39,106);
  controls=new OrbitControls(camera,renderer.domElement);
  controls.enableDamping=true;controls.dampingFactor=.065;
  controls.minDistance=12;controls.maxDistance=230;
  controls.autoRotate=!prefersReduced.matches;
  controls.autoRotateSpeed=.36;
  rotator=controls.autoRotate;
  const core=new THREE.Mesh(new THREE.IcosahedronGeometry(5,1),
    new THREE.MeshBasicMaterial({color:0x155a69,transparent:true,opacity:.23,wireframe:true}));
  scene.add(core);
  const ring=new THREE.Mesh(new THREE.TorusGeometry(12,.055,7,120),
    new THREE.MeshBasicMaterial({color:0x3acfc1,transparent:true,opacity:.25}));
  ring.rotation.set(1.13,.2,.5);scene.add(ring);
  stablePositions();
  const geom=new THREE.IcosahedronGeometry(.7,1);
  const mat=new THREE.MeshBasicMaterial({color:0xffffff,transparent:true,opacity:.92});
  mesh=new THREE.InstancedMesh(geom,mat,nodes.length);
  mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
  for(let i=0;i<nodes.length;i++)mesh.setColorAt(i,new THREE.Color(COLORS[nodes[i].kind]));
  mesh.instanceColor.needsUpdate=true;
  scene.add(mesh);
  halo=new THREE.Mesh(new THREE.TorusGeometry(1.5,.095,9,80),
    new THREE.MeshBasicMaterial({color:0x50efdd,transparent:true,opacity:.9,side:THREE.DoubleSide}));
  halo.visible=false;scene.add(halo);
  const stars=[];
  let seed=977;
  const rand=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296;};
  for(let i=0;i<850;i++){
    const u=rand()*Math.PI*2,v=(rand()-.5)*Math.PI,r=145+rand()*140;
    stars.push(Math.cos(u)*Math.cos(v)*r,Math.sin(v)*r,Math.sin(u)*Math.cos(v)*r);
  }
  const starGeo=new THREE.BufferGeometry();
  starGeo.setAttribute('position',new THREE.Float32BufferAttribute(stars,3));
  scene.add(new THREE.Points(starGeo,
    new THREE.PointsMaterial({color:0x6c9ab9,size:.6,sizeAttenuation:true,transparent:true,opacity:.67})));
  filterAndRender();

  const rectAndPoint = (event)=>{
    const rect=renderer.domElement.getBoundingClientRect();
    ndc.set((event.clientX-rect.left)/rect.width*2-1,
      -(event.clientY-rect.top)/rect.height*2+1);
    ray.setFromCamera(ndc,camera);
    const hit=ray.intersectObject(mesh,false)[0];
    if(!hit || hit.instanceId===undefined || !visible[hit.instanceId])return null;
    return nodes[hit.instanceId];
  };
  renderer.domElement.addEventListener('pointermove',ev=>{
    const n=rectAndPoint(ev);
    const tip=$('tooltip');
    tip.hidden=!n;
    if(n) {
      tip.textContent=n.label+' • '+labelForKind(n.kind)+' • PUBLIC METADATA';
      tip.style.left=Math.min(ev.offsetX+14,stage.clientWidth-230)+'px';
      tip.style.top=Math.max(48,ev.offsetY-26)+'px';
    }
  });
  renderer.domElement.addEventListener('pointerleave',()=>{$('tooltip').hidden=true;});
  renderer.domElement.addEventListener('click',ev=>{
    const n=rectAndPoint(ev);if(n)choose(n.id);
  });
  renderer.domElement.addEventListener('keydown',ev=>{
    if(ev.key==='Escape'){choose(null);ev.preventDefault();}
    if(ev.key==='Enter'){
      const n=nodes.find((node,i)=>visible[i]);
      if(n)choose(n.id);
      ev.preventDefault();
    }
  });
  const onResize=()=>{
    const nw=Math.max(300,stage.clientWidth),nh=Math.max(300,stage.clientHeight);
    camera.aspect=nw/nh;camera.updateProjectionMatrix();renderer.setSize(nw,nh);
  };
  if(typeof ResizeObserver!=='undefined')new ResizeObserver(onResize).observe(stage);
  else window.addEventListener('resize',onResize);
  let last=0;
  const paint=now=>{
    requestAnimationFrame(paint);
    if(document.hidden || now-last<27)return;
    last=now;
    controls.autoRotate=animationRequested&&!prefersReduced.matches;
    if(!animationRequested)controls.autoRotate=false;
    controls.update();
    if(halo.visible) {
      halo.quaternion.copy(camera.quaternion);
      halo.scale.setScalar(1+.16*Math.sin(now*.002));
    }
    renderer.render(scene,camera);
  };
  requestAnimationFrame(paint);
}

function handleError(error) {
  $('status').textContent='ATLAS / PUBLIC OBSERVATION UNAVAILABLE';
  $('view-message').textContent='NO LIVE PUBLIC GRAPH CLAIMED';
  $('directory-result').textContent='Public Hub inventory could not be admitted: '+error.name+'. No stale snapshot substituted.';
  $('asset-rows').replaceChildren();
  const tr=make('tr'),td=make('td','','Live public directory unavailable; retry later.');
  td.colSpan=4;tr.appendChild(td);$('asset-rows').append(tr);
  $('fallback').hidden=false;
  $('visible-count').textContent='0 visible';
  $('export').disabled=true;
}

for(const input of document.querySelectorAll('.switch input'))input.addEventListener('change',filterAndRender);
$('search').addEventListener('input',filterAndRender);
$('vertical').addEventListener('change',()=>{
  filterAndRender();choose(null);
});
$('reset').addEventListener('click',()=>{
  if(!controls)return;
  camera.position.set(0,39,106);controls.target.set(0,0,0);controls.update();
});
$('frame').addEventListener('click',()=>{
  const node=nodes.find(n=>n.id===selectedId);
  if(!node||!controls)return;
  const p=positions.get(node.id);
  controls.target.copy(p);
  camera.position.copy(p).add(new THREE.Vector3(0,6,17));
  controls.update();
});
$('motion').addEventListener('click',()=>{
  animationRequested=!animationRequested;
  controls&&(controls.autoRotate=animationRequested&&!prefersReduced.matches);
  $('motion').setAttribute('aria-pressed',String(!animationRequested));
  $('motion').firstChild.textContent=animationRequested?'Pause orbit ':'Resume orbit ';
});
$('share-selection').addEventListener('click',async()=>{
  try{
    await navigator.clipboard.writeText(location.href);
    $('share-selection').textContent='Copied ✓';
  }catch{$('share-selection').textContent='Copy from address bar';}
});
$('export').addEventListener('click',()=>{
  if(!snapshot)return;
  const blob=new Blob([JSON.stringify(snapshot,null,2)+'\n'],{type:'application/json'});
  const url=URL.createObjectURL(blob);
  const a=document.createElement('a');
  a.href=url;a.download='szl-public-hub-observation.json';a.click();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
});
(async()=>{
  try{
    const ctl=new AbortController();
    const timeout=setTimeout(()=>ctl.abort(),30000);
    let response;
    try{
      response=await fetch('/api/atlas/public',{
        credentials:'omit',cache:'no-store',
        headers:{Accept:'application/json'},signal:ctl.signal});
    }finally{clearTimeout(timeout);}
    if(!response.ok)throw new Error('HUB_HTTP_'+response.status);
    const data=validate(await response.json());
    emitData(data);
    try{install3D();}
    catch(err){
      $('fallback').hidden=false;
      $('view-message').textContent='WEBGL UNAVAILABLE / DIRECTORY REMAINS READY';
    }
  }catch(err){handleError(err);}
})();
