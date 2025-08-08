/* Interactive neural network canvas animation
   - Responsive to pointer movement and clicks
   - Nodes "fire" with neon pulses
*/
(function () {
  const canvas = document.getElementById('neural-canvas');
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  const DPR = Math.min(2, window.devicePixelRatio || 1);

  function resize() {
    const rect = canvas.getBoundingClientRect();
    canvas.width = Math.floor(rect.width * DPR);
    canvas.height = Math.floor(rect.width * 0.55 * DPR);
  }
  resize();
  window.addEventListener('resize', resize);

  const config = {
    layers: 6,
    nodesPerLayer: [7, 10, 12, 10, 8, 5],
    nodeRadius: 5 * DPR,
    linkAlpha: 0.18,
    baseHue: 195,
    glow: 0.6,
  };

  let pointer = { x: 0, y: 0, active: false };
  canvas.addEventListener('mousemove', (e) => {
    const rect = canvas.getBoundingClientRect();
    pointer.x = (e.clientX - rect.left) * DPR;
    pointer.y = (e.clientY - rect.top) * DPR;
    pointer.active = true;
  });
  canvas.addEventListener('mouseleave', () => (pointer.active = false));
  canvas.addEventListener('click', exciteBurst);

  const layers = [];
  function init() {
    layers.length = 0;
    const w = canvas.width, h = canvas.height;
    for (let li = 0; li < config.layers; li++) {
      const x = ((li + 0.5) / config.layers) * w;
      const count = config.nodesPerLayer[li] || config.nodesPerLayer[config.nodesPerLayer.length - 1];
      const layer = [];
      for (let ni = 0; ni < count; ni++) {
        const y = ((ni + 0.5) / count) * (h * 0.82) + h * 0.09;
        layer.push({ x, y, v: Math.random() * 0.6, t: Math.random() * 2000 });
      }
      layers.push(layer);
    }
  }
  init();
  window.addEventListener('resize', init);

  function exciteBurst(e) {
    const rect = canvas.getBoundingClientRect();
    const x = (e.clientX - rect.left) * DPR;
    const y = (e.clientY - rect.top) * DPR;
    for (const layer of layers) {
      for (const n of layer) {
        const dx = n.x - x, dy = n.y - y;
        const d = Math.hypot(dx, dy);
        n.v += Math.max(0, 1.6 - d / (120 * DPR));
      }
    }
  }

  function step(dt) {
    const w = canvas.width, h = canvas.height;
    ctx.clearRect(0, 0, w, h);

    // Links
    ctx.save();
    ctx.globalCompositeOperation = 'lighter';
    for (let li = 0; li < layers.length - 1; li++) {
      const A = layers[li], B = layers[li + 1];
      for (let i = 0; i < A.length; i++) {
        for (let j = 0; j < B.length; j++) {
          const a = A[i], b = B[j];
          const dx = b.x - a.x, dy = b.y - a.y;
          const midx = (a.x + b.x) / 2, midy = (a.y + b.y) / 2;
          const proximity = pointer.active ? Math.max(0.25, 1 - Math.hypot(midx - pointer.x, midy - pointer.y) / (w * 0.5)) : 0.5;
          const alpha = config.linkAlpha * proximity;
          ctx.strokeStyle = `hsla(${config.baseHue + 40 * proximity}, 100%, ${45 + 20 * proximity}%, ${alpha})`;
          ctx.lineWidth = 1.2 * DPR;
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.quadraticCurveTo(midx, midy + Math.sin((a.t + j * 17) * 0.002) * 8 * DPR, b.x, b.y);
          ctx.stroke();
        }
      }
    }
    ctx.restore();

    // Nodes
    for (const layer of layers) {
      for (const n of layer) {
        n.t += dt;
        n.v += (Math.random() - 0.5) * 0.05;
        if (pointer.active) {
          const dx = n.x - pointer.x, dy = n.y - pointer.y;
          const d = Math.hypot(dx, dy);
          n.v += Math.max(0, 1.0 - d / (220 * DPR)) * 0.02;
        }
        n.v *= 0.98; // damping
        const glow = Math.max(0.2, Math.min(1.2, n.v));

        const r = config.nodeRadius * (0.9 + glow * 0.6);
        const grad = ctx.createRadialGradient(n.x, n.y, 0, n.x, n.y, r);
        grad.addColorStop(0, `hsla(${config.baseHue + glow * 80}, 100%, ${60 + glow * 20}%, ${0.85})`);
        grad.addColorStop(1, 'rgba(0,0,0,0)');

        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
        ctx.fill();

        // core
        ctx.fillStyle = `hsl(${config.baseHue + glow * 60}, 100%, ${50 + glow * 10}%)`;
        ctx.beginPath();
        ctx.arc(n.x, n.y, 2.2 * DPR, 0, Math.PI * 2);
        ctx.fill();
      }
    }
  }

  let last = performance.now();
  function loop(now) {
    const dt = Math.min(64, now - last);
    last = now;
    step(dt);
    requestAnimationFrame(loop);
  }
  requestAnimationFrame(loop);
})();


