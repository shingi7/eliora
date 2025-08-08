/* Interactive neural network canvas animation
   - Supports multiple canvases via class "neural-canvas" (and legacy id "neural-canvas")
   - Responsive to pointer movement and clicks
   - Nodes "fire" with neon pulses
*/
(function () {
  const canvases = Array.from(document.querySelectorAll('.neural-canvas'));
  const legacy = document.getElementById('neural-canvas');
  if (legacy && !canvases.includes(legacy)) canvases.push(legacy);
  if (canvases.length === 0) return;

  const DPR = Math.min(2, window.devicePixelRatio || 1);

  canvases.forEach((canvas) => initCanvas(canvas));
  window.addEventListener('resize', () => canvases.forEach((c) => resize(c)));

  function resize(canvas) {
    const rect = canvas.getBoundingClientRect();
    canvas.width = Math.max(320, Math.floor(rect.width * DPR));
    canvas.height = Math.floor(rect.width * 0.55 * DPR);
  }

  function initCanvas(canvas) {
    const ctx = canvas.getContext('2d');
    resize(canvas);

    const config = {
      layers: 7,
      nodesPerLayer: [8, 12, 16, 20, 16, 12, 6],
      nodeRadius: 6 * DPR,
      linkAlpha: 0.15,
      baseHue: 195,
      pulseSpeed: 0.003,
      connectionDensity: 0.7,
    };

    const pointer = { x: 0, y: 0, active: false };
    canvas.addEventListener('mousemove', (e) => {
      const rect = canvas.getBoundingClientRect();
      pointer.x = (e.clientX - rect.left) * DPR;
      pointer.y = (e.clientY - rect.top) * DPR;
      pointer.active = true;
    });
    canvas.addEventListener('mouseleave', () => (pointer.active = false));
    canvas.addEventListener('click', (e) => exciteBurst(e, canvas, layers));

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
          layer.push({ 
            x, y, 
            v: Math.random() * 0.6, 
            t: Math.random() * 2000,
            baseV: 0.2 + Math.random() * 0.3,
            pulsePhase: Math.random() * Math.PI * 2
          });
        }
        layers.push(layer);
      }
    }
    init();
    window.addEventListener('resize', init);

    function exciteBurst(e, canvas, layers) {
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

      // Links with selective connections
      ctx.save();
      ctx.globalCompositeOperation = 'lighter';
      for (let li = 0; li < layers.length - 1; li++) {
        const A = layers[li], B = layers[li + 1];
        for (let i = 0; i < A.length; i++) {
          for (let j = 0; j < B.length; j++) {
            // Skip some connections for more realistic neural network
            if (Math.random() > config.connectionDensity) continue;
            
            const a = A[i], b = B[j];
            const midx = (a.x + b.x) / 2, midy = (a.y + b.y) / 2;
            const proximity = pointer.active ? Math.max(0.3, 1 - Math.hypot(midx - pointer.x, midy - pointer.y) / (w * 0.4)) : 0.6;
            
            // Dynamic connection strength based on node activity
            const connectionStrength = (a.v + b.v) * 0.5;
            const alpha = config.linkAlpha * proximity * (0.5 + connectionStrength);
            const hue = config.baseHue + Math.sin(dt * 0.001 + i + j) * 20;
            
            ctx.strokeStyle = `hsla(${hue}, 100%, ${50 + 25 * proximity}%, ${alpha})`;
            ctx.lineWidth = (1 + connectionStrength) * DPR;
            ctx.beginPath();
            ctx.moveTo(a.x, a.y);
            
            // Animated curve
            const waveOffset = Math.sin((a.t + b.t) * config.pulseSpeed) * 12 * DPR;
            ctx.quadraticCurveTo(midx, midy + waveOffset, b.x, b.y);
            ctx.stroke();
          }
        }
      }
      ctx.restore();

      // Nodes with enhanced visuals
      for (const layer of layers) {
        for (const n of layer) {
          n.t += dt;
          
          // Natural pulsing
          const pulse = Math.sin(n.t * config.pulseSpeed + n.pulsePhase) * 0.3;
          n.v = n.baseV + pulse + (Math.random() - 0.5) * 0.1;
          
          // Mouse interaction
          if (pointer.active) {
            const dx = n.x - pointer.x, dy = n.y - pointer.y;
            const d = Math.hypot(dx, dy);
            n.v += Math.max(0, 1.5 - d / (180 * DPR)) * 0.4;
          }
          
          n.v = Math.max(0.1, Math.min(1.5, n.v));
          const glow = n.v;

          // Outer glow
          const outerR = config.nodeRadius * (1.5 + glow * 1.2);
          const outerGrad = ctx.createRadialGradient(n.x, n.y, 0, n.x, n.y, outerR);
          outerGrad.addColorStop(0, `hsla(${config.baseHue + glow * 60}, 100%, ${70 + glow * 20}%, ${0.6 * glow})`);
          outerGrad.addColorStop(0.7, `hsla(${config.baseHue + glow * 40}, 100%, ${60 + glow * 15}%, ${0.2 * glow})`);
          outerGrad.addColorStop(1, 'rgba(0,0,0,0)');

          ctx.fillStyle = outerGrad;
          ctx.beginPath();
          ctx.arc(n.x, n.y, outerR, 0, Math.PI * 2);
          ctx.fill();

          // Main node
          const r = config.nodeRadius * (0.8 + glow * 0.4);
          const grad = ctx.createRadialGradient(n.x, n.y, 0, n.x, n.y, r);
          grad.addColorStop(0, `hsla(${config.baseHue + glow * 80}, 100%, ${80 + glow * 10}%, ${0.9})`);
          grad.addColorStop(0.8, `hsla(${config.baseHue + glow * 60}, 100%, ${60 + glow * 20}%, ${0.7})`);
          grad.addColorStop(1, 'rgba(0,0,0,0)');

          ctx.fillStyle = grad;
          ctx.beginPath();
          ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
          ctx.fill();

          // Core with enhanced glow
          ctx.fillStyle = `hsl(${config.baseHue + glow * 40}, 100%, ${70 + glow * 15}%)`;
          ctx.shadowBlur = 15 * glow * DPR;
          ctx.shadowColor = `hsl(${config.baseHue}, 100%, 70%)`;
          ctx.beginPath();
          ctx.arc(n.x, n.y, 2.5 * DPR * (0.8 + glow * 0.3), 0, Math.PI * 2);
          ctx.fill();
          ctx.shadowBlur = 0;
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
  }
})();


