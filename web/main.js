import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/addons/loaders/DRACOLoader.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

// ---------------------------------------------------------------------------
// Scroll timeline of the sticky stage (0 → 1). PRÉSENT = 0 → 0.62, FUTUR = 0.62 → 1.
// ---------------------------------------------------------------------------
const T = {
  explode: [0.17, 0.27],        // chair opens (the red thread stays on the upholstery)
  labels: [0.21, 0.31],         // black part labels
  filOut: [0.30, 0.40],         // the red thread lifts off on its own
  filLabel: [0.39, 0.57],       // red arrow + label
  solo: [0.42, 0.46, 0.53, 0.57], // everything but the thread fades while the camera is on it
  collapse: [0.51, 0.575],      // parts come back…
  filBack: [0.565, 0.62],       // …and the thread returns last
  dark: [0.62, 0.68],           // lights out
  rays: [0.64, 0.76],           // Shiota threads converge on the seam
  glow: [0.64, 0.74],           // the seam lights up
  reveal: [0.78, 0.9],          // light reveals the whole chair
  threadOut: [0.93, 1.0],       // thread leaves the chair toward the rest of the page
};
const LABELLED = ['AppuiTete', 'CoussinLombaire', 'Assise', 'Garnissage', 'CoqueInterieure', 'CoqueBois', 'Liaison', 'Pietement'];
const FIL = 'Passepoil';

const clamp01 = (x) => Math.min(1, Math.max(0, x));
const lerp = (a, b, t) => a + (b - a) * t;
const smooth = (a, b, x) => { const t = clamp01((x - a) / (b - a)); return t * t * (3 - 2 * t); };
const range = (r, x) => smooth(r[0], r[1], x);
const easeInOut = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// ===========================================================================
// 1. The document thread — one smooth path through every [data-thread] knot
// ===========================================================================
const scrolly = document.getElementById('scrolly');
const threadSvg = document.getElementById('thread');
const threadPath = document.getElementById('thread-path');
const threadTip = document.getElementById('thread-tip');
let threadLen = 0, threadKnots = [];     // [y, cumulative length] at every knot
let threadDrawn = 0, threadTarget = 0;   // drawn length eases toward the scroll target every frame
let builtFor = '';                        // layout signature the path was built for

function knotPoint(el) {
  const spec = el.dataset.thread;
  if (spec && spec.includes(',')) {         // "fx,fy": fraction of page width / of the parent section
    const [fx, fy] = spec.split(',').map(Number);
    const sec = el.closest('section, footer');
    const top = sec.getBoundingClientRect().top + window.scrollY;
    return [fx * document.documentElement.clientWidth, top + fy * sec.offsetHeight];
  }
  const r = el.getBoundingClientRect();
  return [r.left + r.width / 2, r.top + window.scrollY + r.height / 2];
}

function buildThread(force = false) {
  const W = document.documentElement.clientWidth, H = document.documentElement.scrollHeight;
  // mobile browsers fire resize when the address bar slides: only rebuild if the layout really changed
  const sig = `${W}x${H}`;
  if (!force && sig === builtFor) return;
  builtFor = sig;
  threadSvg.setAttribute('viewBox', `0 0 ${W} ${H}`);
  threadSvg.style.height = `${H}px`;
  const pts = [...document.querySelectorAll('[data-thread]')].map(knotPoint);
  // Smooth curve through every knot. Tangent length is capped by the two segments touching the
  // knot, so a long straight run (behind the 3D stage) can't make the curve loop back upward.
  const dist = (a, b) => Math.hypot(b[0] - a[0], b[1] - a[1]);
  const tan = pts.map((p, i) => {
    const a = pts[i - 1] || p, b = pts[i + 1] || p;
    const len = dist(a, b) || 1;
    const reach = 0.4 * Math.min(i ? dist(a, p) : Infinity, i < pts.length - 1 ? dist(p, b) : Infinity);
    return [((b[0] - a[0]) / len) * reach, ((b[1] - a[1]) / len) * reach];
  });
  // control points stay between their two knots vertically → every segment only goes down
  const within = (y, a, b) => Math.min(Math.max(y, Math.min(a, b)), Math.max(a, b));
  let d = `M${pts[0][0]},${pts[0][1]}`;
  const segs = [];
  for (let i = 0; i < pts.length - 1; i++) {
    const p1 = pts[i], p2 = pts[i + 1], t1 = tan[i], t2 = tan[i + 1];
    const seg = `C${p1[0] + t1[0]},${within(p1[1] + t1[1], p1[1], p2[1])} ${p2[0] - t2[0]},${within(p2[1] - t2[1], p1[1], p2[1])} ${p2[0]},${p2[1]}`;
    d += ` ${seg}`;
    segs.push(`M${p1[0]},${p1[1]} ${seg}`);
  }
  // cumulative length at each knot: the line advances along each segment at a steady rate
  const probe = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  threadSvg.appendChild(probe);
  threadKnots = [[pts[0][1], 0]];
  for (let i = 0; i < segs.length; i++) {
    probe.setAttribute('d', segs[i]);
    threadKnots.push([pts[i + 1][1], threadKnots[i][1] + probe.getTotalLength()]);
  }
  probe.remove();
  threadPath.setAttribute('d', d);
  threadLen = threadPath.getTotalLength();
  threadPath.style.strokeDasharray = `${threadLen} ${threadLen}`;
  aimThread();
  threadDrawn = threadTarget;   // after a rebuild, snap instead of re-animating the whole line
  paintThread();
}

// Where the line should end: the reader's eye line (62 % of the viewport). Right after the 3D
// stage the stage's own thread leaves through its bottom edge, so the page line starts from that
// edge and eases back up to the eye line — no gap, no jump.
function aimThread() {
  if (!threadKnots.length) return;
  const h = window.innerHeight, y = window.scrollY;
  let eye = y + h * 0.62;
  const stageEnd = scrolly.getBoundingClientRect().bottom + y;
  const past = y + h - stageEnd;
  if (past >= 0) eye = y + lerp(h, h * 0.62, clamp01(past / (h * 0.8)));
  let len = threadLen;
  for (let i = 0; i < threadKnots.length - 1; i++) {
    const [y1, l1] = threadKnots[i], [y2, l2] = threadKnots[i + 1];
    if (eye < y2) { len = eye <= y1 ? l1 : l1 + (l2 - l1) * ((eye - y1) / Math.max(y2 - y1, 1)); break; }
  }
  threadTarget = reduced ? threadLen : Math.min(len, threadLen);
}

function paintThread() {
  threadPath.style.strokeDashoffset = threadLen - threadDrawn;
  const q = threadPath.getPointAtLength(threadDrawn);
  threadTip.setAttribute('cx', q.x); threadTip.setAttribute('cy', q.y);
  threadTip.style.opacity = threadDrawn > 2 && threadDrawn < threadLen - 2 ? 1 : 0;
}

function tickThread(dt) {
  if (!threadKnots.length) return;
  const gap = threadTarget - threadDrawn;
  if (Math.abs(gap) < 0.5) { if (gap) { threadDrawn = threadTarget; paintThread(); } return; }
  threadDrawn += gap * (1 - Math.exp(-dt * 9));
  paintThread();
}

// ===========================================================================
// 2. The 3D stage
// ===========================================================================
const stage = document.getElementById('stage');
const canvas = document.getElementById('scene');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 0.95;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;

const scene = new THREE.Scene();
const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;

const camera = new THREE.PerspectiveCamera(30, 1, 0.02, 60);

const key = new THREE.DirectionalLight(0xffffff, 2.0);
key.position.set(-2.4, 5.2, 3.2);
key.castShadow = true;
key.shadow.mapSize.set(2048, 2048);
Object.assign(key.shadow.camera, { left: -2.2, right: 2.2, top: 3.4, bottom: -1.0, near: 0.5, far: 14 });
key.shadow.bias = -0.0004;
key.shadow.normalBias = 0.025;
key.shadow.radius = 4;
key.target.position.set(0, 0.9, 0);
scene.add(key, key.target);
const hemi = new THREE.HemisphereLight(0xf5f5f5, 0x8f8f8f, 0.35);
scene.add(hemi);

// the FUTUR spotlight: first a narrow beam on the seam, then wide open on the chair
const spot = new THREE.SpotLight(0xfff4ea, 0, 12, 0.12, 0.6, 1.2);
spot.position.set(-1.2, 4.6, 2.4);
spot.castShadow = true;
spot.shadow.mapSize.set(1024, 1024);
scene.add(spot, spot.target);

const groundMat = new THREE.ShadowMaterial({ opacity: 0.12 });
const ground = new THREE.Mesh(new THREE.PlaneGeometry(30, 30), groundMat);
ground.rotation.x = -Math.PI / 2;
ground.receiveShadow = true;
scene.add(ground);

const parts = [];
let fil = null;              // the red thread part
const filLocal = new THREE.Vector3();   // anchor on the seam (mesh local)
const filCenter = new THREE.Vector3();  // bbox centre of the seam (mesh local)
const filSide = new THREE.Vector3();    // outermost point of the seam, where the red arrow lands
const chair = new THREE.Group();
scene.add(chair);

const draco = new DRACOLoader().setDecoderPath('https://cdn.jsdelivr.net/npm/three@0.170.0/examples/jsm/libs/draco/gltf/');
const loader = new GLTFLoader().setDRACOLoader(draco);
const loaderEl = document.getElementById('loader');
const pctEl = document.getElementById('loader-pct');
const materials = [];

loader.load('models/fauteuil.glb?v=11', (gltf) => {
  const maxAniso = renderer.capabilities.getMaxAnisotropy();
  gltf.scene.traverse((o) => {
    if (!o.isMesh) return;
    o.castShadow = true;
    o.receiveShadow = true;
    const m = o.material;
    for (const t of [m.map, m.normalMap, m.roughnessMap]) if (t) t.anisotropy = maxAniso;
    if (!materials.includes(m)) materials.push(m);
    // three.js renders the exported sheen much stronger than Blender: tone it down
    if (m.name === 'Tissu') {
      m.sheen = 0.2; m.sheenRoughness = 0.7; m.sheenColor.setRGB(0.5, 0.52, 0.45);
    }
    if (m.name === 'Passepoil') {
      m.sheen = 0.25; m.sheenRoughness = 0.6; m.sheenColor.setRGB(0.55, 0.1, 0.1);
      m.emissive = new THREE.Color(0xd4202a);
      m.emissiveMap = m.map;          // glow keeps the Material-265 weave
      m.emissiveIntensity = 0;
    }
  });
  gltf.scene.traverse((o) => {
    const u = o.userData;
    if (!u || !u.explode) return;
    const geo = o.geometry;
    geo.computeBoundingBox();
    const bb = geo.boundingBox;
    const part = {
      name: o.name, obj: o, order: u.order ?? 0,
      base: o.position.clone(),
      offset: new THREE.Vector3().fromArray(u.explode),
      anchor: new THREE.Vector3(bb.max.x, (bb.min.y + bb.max.y) / 2, (bb.min.z + bb.max.z) / 2),
      label: u.label, desc: u.desc, t: 0,
    };
    parts.push(part);
    if (o.name === FIL) {
      fil = part;
      bb.getCenter(filCenter);
      // anchor = the highest point of the seam, on the rim of the back
      const pos = geo.attributes.position;
      let best = -Infinity, side = -Infinity;
      for (let i = 0; i < pos.count; i++) {
        const y = pos.getY(i), s = pos.getX(i) + pos.getZ(i) * 0.5;
        if (y > best) { best = y; filLocal.fromBufferAttribute(pos, i); }
        if (s > side) { side = s; filSide.fromBufferAttribute(pos, i); }
      }
      o.castShadow = false; // a floating thread's hairline shadow reads as a glitch
    }
  });
  const others = parts.filter((p) => p !== fil);
  const maxOrder = Math.max(...others.map((p) => p.order));
  for (const p of others) p.maxOrder = maxOrder;
  chair.add(gltf.scene);
  window.__chair = gltf.scene; // handy for tweaking materials from the console
  buildLabels();
  loaderEl.classList.add('done');
}, (e) => {
  if (e.total) pctEl.textContent = `${Math.round((e.loaded / e.total) * 100)} %`;
}, (err) => {
  pctEl.textContent = 'Erreur de chargement du modèle';
  console.error(err);
});

// ---------------------------------------------------------------------------
// Overlays: black part labels, red thread label + arrow, stage threads, rays
// ---------------------------------------------------------------------------
const NS = 'http://www.w3.org/2000/svg';
const svg = document.getElementById('leaders');
const labelsEl = document.getElementById('labels');
const partLeaders = document.getElementById('part-leaders');
const filLabel = document.getElementById('fil-label');
const filLeader = document.getElementById('fil-leader');
const inPath = document.getElementById('stage-thread-in');
const outPath = document.getElementById('stage-thread-out');
const raysG = document.getElementById('rays');
const labelItems = [];

// converging threads of the FUTUR installation: start points on the frame (fractions of w/h)
const RAYS = [[0, 0.08], [0.22, 0], [0.48, 0], [1, 0.12], [1, 0.46], [1, 0.9], [0.8, 1], [0.34, 1], [0, 0.72], [0, 0.4]]
  .map(([x, y], i) => {
    const el = document.createElementNS(NS, 'path');
    el.setAttribute('class', 'ray');
    raysG.appendChild(el);
    return { x, y, el, delay: (i % 5) * 0.12 + (i > 4 ? 0.06 : 0) };
  });

function buildLabels() {
  for (const name of LABELLED) {
    const p = parts.find((q) => q.name === name);
    if (!p) continue;
    const el = document.createElement('div');
    el.className = 'label';
    el.innerHTML = `<b>${p.label}</b><span>${p.desc}</span>`;
    labelsEl.appendChild(el);
    const path = document.createElementNS(NS, 'path');
    const dot = document.createElementNS(NS, 'circle');
    dot.setAttribute('r', '2.2');
    partLeaders.append(path, dot);
    labelItems.push({ part: p, el, path, dot });
  }
}

const v = new THREE.Vector3();
function toScreen(localPoint, obj, w, h) {
  v.copy(localPoint).add(obj.position);
  obj.parent.localToWorld(v);
  v.project(camera);
  return { x: (v.x * 0.5 + 0.5) * w, y: (-v.y * 0.5 + 0.5) * h, behind: v.z > 1 };
}

// Draws `frac` of a path (0 → hidden, 1 → complete) — works for paths that change every frame
function drawPartial(el, d, frac) {
  el.setAttribute('d', d);
  const L = el.getTotalLength() || 1;
  el.style.strokeDasharray = `${L} ${L}`;
  el.style.strokeDashoffset = L * (1 - clamp01(frac));
}

function layoutLabels(alpha, w, h, mobile) {
  if (!labelItems.length) return;
  const pts = labelItems.map((it) => ({ it, ...toScreen(it.part.anchor, it.part.obj, w, h) }));
  const colX = Math.min(Math.max(...pts.map((p) => p.x)) + (mobile ? 24 : 64), w - (mobile ? 140 : 240));
  const gap = mobile ? 28 : 48;
  pts.sort((a, b) => a.y - b.y);
  let prev = -Infinity;
  for (const p of pts) { p.ly = Math.max(p.y, prev + gap); prev = p.ly; }
  const overflow = prev - (h - 90);
  if (overflow > 0) for (const p of pts) p.ly -= overflow;
  for (const p of pts) {
    const { it } = p;
    const a = alpha * smooth(0.55, 1, it.part.t);
    it.el.style.opacity = a;
    it.el.style.transform = `translate(${colX}px, ${p.ly - 12}px)`;
    const elbow = colX - 18;
    it.path.setAttribute('d', `M${p.x},${p.y} L${elbow - Math.abs(p.ly - p.y) * 0.35},${p.y} L${elbow},${p.ly} L${colX - 6},${p.ly}`);
    it.path.style.opacity = a * 0.55;
    it.dot.setAttribute('cx', p.x); it.dot.setAttribute('cy', p.y);
    it.dot.style.opacity = a;
  }
}

let inFrac = 0, frameDt = 0, stageTop = 1;
function layoutThread(p, w, h, mobile, threadX) {
  if (!fil) return;
  const a = toScreen(filLocal, fil.obj, w, h);          // seam anchor
  const c = toScreen(filCenter, fil.obj, w, h);          // seam centre

  // page thread enters from the top edge and ties onto the seam; leaves through the bottom edge
  const sag = Math.min(h * 0.18, 140);
  // while the stage slides up into view the line grows with the page line (same eye line);
  // once the stage is pinned it is simply tied to the seam
  const eyeInStage = h * 0.62 - Math.max(0, stageTop);
  const inAim = stageTop > 0 ? clamp01(eyeInStage / Math.max(a.y, 1)) : 1;
  inFrac += (inAim - inFrac) * (1 - Math.exp(-frameDt * 9));
  inPath.style.visibility = outPath.style.visibility = a.behind ? 'hidden' : 'visible';
  drawPartial(inPath, `M${threadX},0 C${threadX},${sag} ${a.x},${a.y - sag} ${a.x},${a.y}`, reduced ? 1 : inFrac);
  drawPartial(outPath, `M${a.x},${a.y} C${a.x + w * 0.32},${a.y + 10} ${threadX + w * 0.28},${h * 0.72} ${threadX},${h}`, reduced ? (p > T.threadOut[0] ? 1 : 0) : range(T.threadOut, p));

  // red label with its own arrow, pointing at the thread
  const la = range(T.filLabel, p) * (1 - smooth(T.filLabel[1] - 0.02, T.filLabel[1] + 0.01, p));
  const s = toScreen(filSide, fil.obj, w, h);
  const lx = Math.max(16, Math.min(s.x + (mobile ? 24 : 70), w - (mobile ? 176 : 260)));
  const ly = Math.max(mobile ? 70 : 90, s.y - (mobile ? 110 : 150));
  filLabel.style.opacity = la;
  filLabel.style.transform = `translate(${lx}px, ${ly}px)`;
  // arrow: from under the label, swinging down onto the seam
  const sx = lx + 14, sy = ly + (mobile ? 34 : 58);
  drawPartial(filLeader, `M${sx},${sy} C${sx},${sy + 40} ${s.x + 30},${s.y - 30} ${s.x + 5},${s.y - 4}`, la);
  filLeader.style.opacity = la > 0.01 ? 1 : 0;

  // converging threads
  const rp = range(T.rays, p);
  const rayFade = 1 - range([0.84, 0.94], p);
  for (const r of RAYS) {
    const sx = r.x * w, sy = r.y * h;
    const mx = lerp(sx, a.x, 0.5) + (sy - a.y) * 0.08, my = lerp(sy, a.y, 0.5) - (sx - a.x) * 0.08;
    drawPartial(r.el, `M${sx},${sy} Q${mx},${my} ${a.x},${a.y}`, clamp01((rp - r.delay) / (1 - 0.5)));
    r.el.style.opacity = rp > 0 ? rayFade : 0;
  }
}

// ---------------------------------------------------------------------------
// Camera keyframes. fil = how much the camera looks at the thread instead of the chair.
// ---------------------------------------------------------------------------
const K = [
  { p: 0.00, az: -24, el: 8, dist: 0.55, ty: 1.02, fil: 1, seam: 1 },  // fragment: the seam only
  { p: 0.06, az: -28, el: 10, dist: 0.8, ty: 1.0, fil: 1, seam: 1 },
  { p: 0.15, az: -38, el: 11, dist: 3.1, ty: 0.52, fil: 0 },  // the whole chair
  { p: 0.27, az: -30, el: 15, dist: 5.9, ty: 1.36, fil: 0 },  // exploded
  { p: 0.33, az: -26, el: 15, dist: 5.9, ty: 1.36, fil: 0 },
  { p: 0.42, az: -22, el: 13, dist: 4.6, ty: 1.2, fil: 0.45 }, // thread lifts off
  { p: 0.47, az: -6, el: 12, dist: 2.5, ty: 0, fil: 1 },       // close on the weave
  { p: 0.53, az: 4, el: 10, dist: 2.6, ty: 0, fil: 1 },
  { p: 0.61, az: -32, el: 11, dist: 3.2, ty: 0.55, fil: 0 },   // reassembled
  { p: 0.68, az: -20, el: 9, dist: 3.4, ty: 0.55, fil: 0.3 },  // dark room
  { p: 0.78, az: -12, el: 9, dist: 3.0, ty: 0.6, fil: 0.3 },
  { p: 0.9, az: -26, el: 10, dist: 3.3, ty: 0.52, fil: 0 },    // revealed
  { p: 1.0, az: -34, el: 12, dist: 3.5, ty: 0.52, fil: 0 },
];
function cameraAt(p) {
  let i = 0;
  while (i < K.length - 2 && p > K[i + 1].p) i++;
  const a = K[i], b = K[i + 1];
  const t = smooth(a.p, b.p, p);
  const o = {};
  for (const k of ['az', 'el', 'dist', 'ty', 'fil', 'seam']) o[k] = lerp(a[k] ?? 0, b[k] ?? 0, t);
  return o;
}

// ---------------------------------------------------------------------------
// Scroll + pointer
// ---------------------------------------------------------------------------
const beats = [...document.querySelectorAll('.beat')];
const acts = [...document.querySelectorAll('#acts a')];
const passe = document.getElementById('passe');
const progressBar = document.getElementById('progress-bar');
let target = 0, progress = 0;
const pointer = { x: 0, y: 0, sx: 0, sy: 0 };

function readScroll() {
  const r = scrolly.getBoundingClientRect();
  const total = scrolly.offsetHeight - window.innerHeight;
  target = total > 0 ? clamp01(-r.top / total) : 0;
  stageTop = r.top;
  aimThread();
  // header: which act are we in, and are we on a dark page?
  const mid = window.innerHeight * 0.5;
  const pr = passe.getBoundingClientRect();
  let act = null;
  if (pr.top < mid && pr.bottom > mid) act = 'passe';
  else if (r.top < mid && r.bottom > mid) act = target < 0.62 ? 'present' : 'futur';
  acts.forEach((a) => a.classList.toggle('on', a.dataset.act === act));
  // header over a dark area? (lit stage in FUTUR, or the dark rendez-vous / footer sections)
  const darkStage = r.top <= 30 && r.bottom > 30 && target >= 0.64;
  document.body.classList.toggle('header-dark', darkStage || document.getElementById('event').getBoundingClientRect().top <= 30);
}
window.addEventListener('scroll', readScroll, { passive: true });
window.addEventListener('pointermove', (e) => {
  pointer.x = (e.clientX / window.innerWidth) * 2 - 1;
  pointer.y = (e.clientY / window.innerHeight) * 2 - 1;
});

function resize() {
  const w = stage.clientWidth, h = stage.clientHeight;
  if (!w || !h) return;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  svg.setAttribute('viewBox', `0 0 ${w} ${h}`);
  document.getElementById('stage-threads').setAttribute('viewBox', `0 0 ${w} ${h}`);
  buildThread();
}
window.addEventListener('resize', () => { resize(); readScroll(); });
window.addEventListener('load', () => { resize(); readScroll(); });
document.fonts?.ready.then(() => { buildThread(true); readScroll(); });
// any late layout change (fonts, images) rebuilds the path so knots stay on their elements
new ResizeObserver(() => { buildThread(); readScroll(); }).observe(document.body);
resize();
readScroll();

// ---------------------------------------------------------------------------
// Frame loop
// ---------------------------------------------------------------------------
const camTarget = new THREE.Vector3();
const filWorld = new THREE.Vector3();
const white = new THREE.Color(0xfafaf8), black = new THREE.Color(0x0a0a0a), bg = new THREE.Color();
const clock = new THREE.Clock();

function frame() {
  const dt = Math.min(clock.getDelta(), 0.05);
  frameDt = dt;
  tickThread(dt);
  const time = clock.elapsedTime;
  progress += (target - progress) * (1 - Math.exp(-dt * 7));
  pointer.sx += (pointer.x - pointer.sx) * 0.05;
  pointer.sy += (pointer.y - pointer.sy) * 0.05;
  const p = progress;
  const w = stage.clientWidth, h = stage.clientHeight;
  const mobile = w <= 820;

  // --- parts: the chair opens with the thread still sewn in, then the thread leaves alone
  const e = range(T.explode, p) * (1 - range(T.collapse, p));
  const span = 0.55;
  for (const part of parts) {
    if (part === fil) continue;
    const k = part.order / (part.maxOrder || 1);
    part.t = easeInOut(clamp01((e - k * (1 - span)) / span));
    part.obj.position.copy(part.base).addScaledVector(part.offset, part.t);
  }
  if (fil) {
    const garn = parts.find((q) => q.name === 'Garnissage');
    const own = easeInOut(range(T.filOut, p) * (1 - range(T.filBack, p)));
    fil.t = own;
    // rides with the upholstery until it lifts off; floats gently while it is on its own
    fil.obj.position.copy(fil.base)
      .addScaledVector(garn.offset, garn.t * (1 - own))
      .addScaledVector(fil.offset, own);
    fil.obj.position.y += Math.sin(time * 0.9) * 0.012 * own;
    fil.obj.rotation.y = Math.sin(time * 0.35) * 0.06 * own;
  }

  // --- solo: the chair steps back so the thread is alone on screen
  const solo = range(T.solo.slice(0, 2), p) * (1 - range(T.solo.slice(2), p));
  for (const m of materials) {
    if (m.name === 'Passepoil') continue;
    m.opacity = 1 - 0.92 * solo;
    const t = solo > 0.001;
    if (m.transparent !== t) { m.transparent = t; m.depthWrite = !t; m.needsUpdate = true; }
  }

  // --- light: PRÉSENT is a bright atelier, FUTUR a dark room where the seam glows first
  const dark = range(T.dark, p);
  const reveal = range(T.reveal, p);
  const glow = range(T.glow, p);
  const room = lerp(1, 0.04, dark) + reveal * 0.5;
  key.intensity = 2.0 * room;
  hemi.intensity = 0.35 * room;
  scene.environmentIntensity = 0.7 * lerp(1, 0.05, dark) + reveal * 0.3;
  groundMat.opacity = lerp(0.12, 0.5, dark);
  spot.intensity = dark * lerp(22, 90, reveal);
  spot.angle = lerp(0.07, 0.42, reveal);
  spot.penumbra = lerp(0.4, 0.8, reveal);
  if (fil) {
    fil.obj.getWorldPosition(filWorld);
    const m = fil.obj.material;
    m.emissiveIntensity = glow * lerp(1.6, 0.55, reveal);
    // beam follows the seam, then opens onto the chair
    spot.target.position.lerpVectors(filWorld.clone().add(v.copy(filLocal)), new THREE.Vector3(0, 0.55, 0), reveal);
  }
  bg.copy(white).lerp(black, dark);
  stage.style.setProperty('--stage-bg', `#${bg.getHexString()}`);
  stage.classList.toggle('is-dark', dark > 0.5);

  // --- camera
  const c = cameraAt(p);
  const narrow = w / h < 0.9 ? 1.5 : 1;
  if (w && h) camera.aspect = w / h;
  const bigShot = c.dist > 2.5 ? 1 : 0;
  if (mobile) camera.setViewOffset(w, h, 0, h * 0.16, w, h);
  else camera.setViewOffset(w, h, -w * 0.16 * (1 - Math.max(0, (p - 0.86) / 0.14) * bigShot), 0, w, h);
  camTarget.set(0, c.ty, 0);
  if (fil) {
    v.copy(filCenter).lerp(filLocal, c.seam).add(fil.obj.position);
    fil.obj.parent.localToWorld(v);
    camTarget.lerp(v, c.fil);
  }
  const az = THREE.MathUtils.degToRad(c.az + Math.sin(time * 0.25) * 1.2 + pointer.sx * 3);
  const el = THREE.MathUtils.degToRad(c.el - pointer.sy * 2);
  const dist = c.dist * (c.dist > 2 ? narrow : 1);
  camera.position.set(
    camTarget.x + Math.sin(az) * Math.cos(el) * dist,
    camTarget.y + Math.sin(el) * dist,
    camTarget.z + Math.cos(az) * Math.cos(el) * dist,
  );
  camera.lookAt(camTarget);
  camera.updateMatrixWorld();

  // --- overlays
  for (const b of beats) b.classList.toggle('on', p >= +b.dataset.from && p < +b.dataset.to);
  progressBar.style.transform = `scaleY(${p})`;

  renderer.render(scene, camera);
  const labelAlpha = range(T.labels, p) * (1 - smooth(T.labels[1], T.labels[1] + 0.03, p));
  layoutLabels(mobile ? 0 : labelAlpha, w, h, mobile);
  layoutThread(p, w, h, mobile, 0.62 * w);
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);
