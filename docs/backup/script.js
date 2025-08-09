//
// Custom JavaScript for Eliora Tech Solutions website
//
// This script initialises the animated neural network background using
// Vanta.js and reveals sections on scroll via the Intersection Observer API.

document.addEventListener('DOMContentLoaded', () => {
  // Initialise Vanta NET effect on the full‑screen background container.
  if (typeof VANTA !== 'undefined' && VANTA.NET) {
    VANTA.NET({
      el: '#vanta-bg',
      mouseControls: true,
      touchControls: true,
      gyroControls: false,
      // Use a darker blue for the network lines to reduce visual interference
      color: 0x2a7bc9,
      backgroundColor: 0x0a0a0a,
      // Slightly reduce point density and spacing for a calmer effect
      points: 8.0,
      maxDistance: 20.0,
      spacing: 20.0
    });
  }

  // Reveal sections on scroll
  const observer = new IntersectionObserver((entries, obs) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
        obs.unobserve(entry.target);
      }
    });
  }, { threshold: 0.1 });

  document.querySelectorAll('.section').forEach(section => {
    observer.observe(section);
  });
});