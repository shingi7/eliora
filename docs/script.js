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

// ---- Contact form (Formspree) ----
(function () {
  const form = document.getElementById('contact-form');
  if (!form) return;

  const status = document.getElementById('form-status');

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    status.textContent = 'Sending…';
    status.className = 'form-status';

    try {
      const r = await fetch(form.action, {
        method: 'POST',
        body: new FormData(form),
        headers: { 'Accept': 'application/json' }
      });

      if (r.ok) {
        form.reset();
        status.textContent = 'Thanks! We’ll reach out within 1 business day.';
        status.classList.add('success');
      } else {
        const data = await r.json().catch(() => ({}));
        status.textContent = (data.errors && data.errors.length)
          ? data.errors.map(e => e.message).join(', ')
          : 'Oops! There was a problem submitting your form.';
        status.classList.add('error');
      }
    } catch {
      status.textContent = 'Network error. Please try again.';
      status.classList.add('error');
    }
  });
})();
