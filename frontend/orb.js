// orb.js — der leuchtende Partikel-Orb. level() liefert 0..1 Lautstärke.
import * as THREE from "three";

export function startOrb(canvas, level) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 100);
  camera.position.z = 4;

  const N = 2000;
  const base = new Float32Array(N * 3);
  for (let i = 0; i < N; i++) {
    // gleichmäßig auf einer Kugel verteilt (Fibonacci-Spirale)
    const y = 1 - (i / (N - 1)) * 2;
    const r = Math.sqrt(1 - y * y);
    const t = i * Math.PI * (3 - Math.sqrt(5));
    base.set([Math.cos(t) * r, y, Math.sin(t) * r], i * 3);
  }
  const geo = new THREE.BufferGeometry();
  const pos = new Float32Array(base);
  geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  const mat = new THREE.PointsMaterial({
    color: 0x4fb3ff, size: 0.025, transparent: true, opacity: 0.85,
    blending: THREE.AdditiveBlending, depthWrite: false,
  });
  const points = new THREE.Points(geo, mat);
  scene.add(points);

  function resize() {
    const w = innerWidth, h = innerHeight;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }
  addEventListener("resize", resize);
  resize();

  let smooth = 0;
  renderer.setAnimationLoop((ms) => {
    const t = ms / 1000;
    smooth += (level() - smooth) * 0.15;
    const s = 1 + smooth * 0.35;
    for (let i = 0; i < N; i++) {
      const j = i * 3;
      const wob = 1 + 0.03 * Math.sin(t * 1.5 + i * 0.37) + smooth * 0.08 * Math.sin(t * 9 + i);
      pos[j] = base[j] * s * wob;
      pos[j + 1] = base[j + 1] * s * wob;
      pos[j + 2] = base[j + 2] * s * wob;
    }
    geo.attributes.position.needsUpdate = true;
    mat.opacity = 0.55 + smooth * 0.45;
    points.rotation.y = t * 0.12;
    points.rotation.x = Math.sin(t * 0.2) * 0.15;
    renderer.render(scene, camera);
  });
}
