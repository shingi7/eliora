// Initialize Vanta.NET if hero-bg present and Three.js available
(function () {
  if (!window.VANTA || !document.getElementById('hero-bg')) return;
  VANTA.NET({
    el: "#hero-bg",
    mouseControls: true,
    touchControls: true,
    gyroControls: false,
    color: 0x00d4ff,           // cyan network lines
    backgroundColor: 0x060912, // match dark background
    points: 10.0,
    maxDistance: 18.0,
    spacing: 15.0
  });
})();

