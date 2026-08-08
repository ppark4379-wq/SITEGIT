const header=document.querySelector('[data-header]');
const menu=document.querySelector('[data-menu]');
const nav=document.querySelector('#primary-nav');

function syncHeader(){header.classList.toggle('scrolled',window.scrollY>24)}
syncHeader();
window.addEventListener('scroll',syncHeader,{passive:true});

menu.addEventListener('click',()=>{
  const open=menu.getAttribute('aria-expanded')!=='true';
  menu.setAttribute('aria-expanded',String(open));
  nav.classList.toggle('open',open);
});
nav.addEventListener('click',event=>{
  if(event.target.closest('a')){nav.classList.remove('open');menu.setAttribute('aria-expanded','false')}
});

const reduced=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const reveals=document.querySelectorAll('.reveal');
if(reduced||!('IntersectionObserver' in window)) reveals.forEach(item=>item.classList.add('visible'));
else{
  const observer=new IntersectionObserver(entries=>entries.forEach(entry=>{
    if(entry.isIntersecting){entry.target.classList.add('visible');observer.unobserve(entry.target)}
  }),{threshold:.14,rootMargin:'0px 0px -6%'});
  reveals.forEach(item=>observer.observe(item));
}

const stage=document.querySelector('[data-parallax]');
if(stage&&!reduced&&window.matchMedia('(min-width: 900px)').matches){
  window.addEventListener('pointermove',event=>{
    const x=(event.clientX/window.innerWidth-.5)*10;
    const y=(event.clientY/window.innerHeight-.5)*8;
    stage.style.transform=`translate3d(${x}px,${y}px,0)`;
  },{passive:true});
}

const previewImage=document.querySelector('[data-preview-image]');
const previewLabel=document.querySelector('[data-preview-label]');
document.querySelectorAll('[data-preview]').forEach(button=>button.addEventListener('click',()=>{
  if(button.getAttribute('aria-selected')==='true')return;
  document.querySelectorAll('[data-preview]').forEach(item=>item.setAttribute('aria-selected','false'));
  button.setAttribute('aria-selected','true');
  previewImage.classList.add('switching');
  window.setTimeout(()=>{
    previewImage.src=`assets/screenshots/${button.dataset.preview}`;
    previewImage.alt=`SiteGit ${button.dataset.label} 제품 화면`;
    previewLabel.textContent=button.dataset.label;
    previewImage.classList.remove('switching');
  },160);
}));
