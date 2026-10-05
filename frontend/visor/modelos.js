import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { descargar } from './common.js';

/** Una malla por sesión; dispose libera WebGL, listeners y el parser. */
export async function abrirModelo(element, item, ctx) {
  const buffer = await descargar(item.url, { signal: ctx.signal, maxBytes: ctx.limits.meshBytes, progress: p => ctx.status('Descargando modelo…', p) });
  ctx.status('Preparando modelo…');
  ctx.signal.throwIfAborted();
  const data = await new Promise((resolve, reject) => {
    const worker = new Worker(new URL('./mesh.worker.js', import.meta.url), { type: 'module' });
    const finish = () => { worker.terminate(); ctx.signal.removeEventListener('abort', abort); clearTimeout(timer); };
    const abort = () => { finish(); reject(new DOMException('Cancelado', 'AbortError')); };
    const timer = setTimeout(() => { finish(); reject(new Error('formato')); }, 30000);
    ctx.signal.addEventListener('abort', abort, { once: true });
    worker.onmessage = ({ data }) => { finish(); data.error ? reject(new Error(data.error)) : resolve(data); };
    worker.onerror = () => { finish(); reject(new Error('formato')); };
    worker.postMessage({ buffer, formato: item.formato, limits: ctx.limits }, [buffer]);
  });
  ctx.signal.throwIfAborted();
  const geometry = new THREE.BufferGeometry();
  for (const [name, a] of Object.entries(data.attributes)) geometry.setAttribute(name, new THREE.BufferAttribute(a.array, a.itemSize, a.normalized));
  if (data.index) geometry.setIndex(new THREE.BufferAttribute(data.index, 1));
  if (data.faces && !geometry.hasAttribute('normal')) geometry.computeVertexNormals();
  geometry.computeBoundingSphere();
  const center = geometry.boundingSphere.center.clone();
  const radius = geometry.boundingSphere.radius;
  if (!Number.isFinite(radius) || radius <= 0) { geometry.dispose(); throw new Error('formato'); }
  geometry.translate(-center.x, -center.y, -center.z);
  const material = data.faces
    ? new THREE.MeshStandardMaterial({ color: geometry.hasAttribute('color') ? 0xffffff : 0xd6e6e5, vertexColors: geometry.hasAttribute('color'), roughness: .72, side: THREE.DoubleSide })
    : new THREE.PointsMaterial({ color: geometry.hasAttribute('color') ? 0xffffff : 0xc9e9e5, vertexColors: geometry.hasAttribute('color'), size: radius / 180 });
  const scene = new THREE.Scene();
  scene.background = new THREE.Color('#152c37');
  scene.add(data.faces ? new THREE.Mesh(geometry, material) : new THREE.Points(geometry, material));
  scene.add(new THREE.HemisphereLight(0xffffff, 0x405367, 2.5));
  const light = new THREE.DirectionalLight(0xffffff, 3); light.position.set(2, 3, 4); scene.add(light);
  const camera = new THREE.PerspectiveCamera(40, 1, radius / 100, radius * 100);
  camera.position.set(radius * 1.5, radius, radius * 3.5);
  let renderer;
  try { renderer = new THREE.WebGLRenderer({ antialias: true }); }
  catch { geometry.dispose(); material.dispose(); throw new Error('webgl'); }
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  element.append(renderer.domElement);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.minDistance = radius / 50; controls.maxDistance = radius * 50;
  controls.enableDamping = false; controls.saveState();
  let disposed = false;
  const render = () => renderer.render(scene, camera);
  const resize = () => { const w = element.clientWidth, h = element.clientHeight; renderer.setSize(w, h); camera.aspect = w / Math.max(1, h); camera.updateProjectionMatrix(); render(); };
  const observer = new ResizeObserver(resize); observer.observe(element);
  controls.addEventListener('change', render);
  resize(); ctx.status(data.faces ? 'Modelo listo' : 'Nube de puntos lista', 100);
  return {
    reset() { controls.reset(); render(); },
    zoom(factor) { camera.position.sub(controls.target).multiplyScalar(factor).add(controls.target); controls.update(); render(); },
    rotate() { camera.position.sub(controls.target).applyAxisAngle(camera.up, Math.PI / 9).add(controls.target); controls.update(); render(); },
    dispose() {
      if (disposed) return;
      disposed = true;
      observer.disconnect(); controls.dispose(); geometry.dispose(); material.dispose(); renderer.dispose();
      renderer.forceContextLoss(); renderer.domElement.remove(); scene.clear();
    },
  };
}
