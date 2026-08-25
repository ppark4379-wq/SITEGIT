const header = document.querySelector('[data-header]');
const menu = document.querySelector('[data-menu]');
const nav = document.querySelector('#primary-nav');

function syncHeader() {
  if (header) header.classList.toggle('scrolled', window.scrollY > 24);
}

syncHeader();
window.addEventListener('scroll', syncHeader, { passive: true });

if (menu && nav) {
  menu.addEventListener('click', () => {
    const open = menu.getAttribute('aria-expanded') !== 'true';
    menu.setAttribute('aria-expanded', String(open));
    nav.classList.toggle('open', open);
  });

  nav.addEventListener('click', (event) => {
    if (event.target.closest('a')) {
      nav.classList.remove('open');
      menu.setAttribute('aria-expanded', 'false');
    }
  });
}

const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const reveals = document.querySelectorAll('.reveal');

if (reducedMotion || !('IntersectionObserver' in window)) {
  reveals.forEach((item) => item.classList.add('visible'));
} else {
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.12, rootMargin: '0px 0px -5%' });

  reveals.forEach((item) => observer.observe(item));
}

const productStage = document.querySelector('[data-parallax]');
if (productStage && !reducedMotion && window.matchMedia('(min-width: 900px)').matches) {
  window.addEventListener('pointermove', (event) => {
    const x = (event.clientX / window.innerWidth - 0.5) * 8;
    const y = (event.clientY / window.innerHeight - 0.5) * 6;
    productStage.style.transform = `translate3d(${x}px, ${y}px, 0)`;
  }, { passive: true });
}

const previewImage = document.querySelector('[data-preview-image]');
const previewLabel = document.querySelector('[data-preview-label]');
const previewButtons = document.querySelectorAll('[data-preview]');

previewButtons.forEach((button) => {
  button.addEventListener('click', () => {
    if (!previewImage || !previewLabel || button.getAttribute('aria-selected') === 'true') return;

    previewButtons.forEach((item) => item.setAttribute('aria-selected', 'false'));
    button.setAttribute('aria-selected', 'true');
    previewImage.classList.add('switching');

    window.setTimeout(() => {
      previewImage.src = `assets/screenshots/${button.dataset.preview}`;
      previewImage.alt = `SiteGit ${button.dataset.label} 제품 화면`;
      previewLabel.textContent = button.dataset.label;
      previewImage.classList.remove('switching');
    }, 160);
  });
});
