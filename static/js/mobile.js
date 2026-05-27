/* ============================================================
   HELP DESK — JS RESPONSIVO MOBILE
   Apenas a lógica do menu hambúrguer. Sem dependências externas.
   ============================================================ */

(function () {
  'use strict';

  // Pega elementos relevantes (várias possibilidades de class/id pra
  // funcionar em todos os 11 templates sem padronizar HTML)
  function getMenu() {
    return (
      document.getElementById('mainMenu') ||
      document.querySelector('header nav') ||
      document.querySelector('header .menu') ||
      document.querySelector('.nav-menu')
    );
  }

  function getToggleBtn() {
    return document.querySelector('.menu-toggle');
  }

  function getBackdrop() {
    return document.querySelector('.menu-backdrop');
  }

  // Cria backdrop se não existir
  function ensureBackdrop() {
    var existing = getBackdrop();
    if (existing) return existing;
    var bd = document.createElement('div');
    bd.className = 'menu-backdrop';
    bd.setAttribute('aria-hidden', 'true');
    document.body.appendChild(bd);
    bd.addEventListener('click', closeMenu);
    return bd;
  }

  function openMenu() {
    var menu = getMenu();
    var btn = getToggleBtn();
    var bd = ensureBackdrop();
    if (!menu) return;
    menu.classList.add('active');
    bd.classList.add('active');
    if (btn) {
      btn.innerHTML = '✕';
      btn.setAttribute('aria-expanded', 'true');
    }
    document.body.style.overflow = 'hidden';
  }

  function closeMenu() {
    var menu = getMenu();
    var btn = getToggleBtn();
    var bd = getBackdrop();
    if (!menu) return;
    menu.classList.remove('active');
    if (bd) bd.classList.remove('active');
    if (btn) {
      btn.innerHTML = '☰';
      btn.setAttribute('aria-expanded', 'false');
    }
    document.body.style.overflow = '';
  }

  function toggleMenu() {
    var menu = getMenu();
    if (!menu) return;
    if (menu.classList.contains('active')) {
      closeMenu();
    } else {
      openMenu();
    }
  }

  // Expõe globalmente pra suportar onclick inline nos templates antigos
  window.toggleMenu = toggleMenu;
  window.closeMenu = closeMenu;

  // Setup quando DOM estiver pronto
  function init() {
    var btn = getToggleBtn();
    if (btn) {
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        toggleMenu();
      });
      btn.setAttribute('aria-label', 'Abrir menu');
      btn.setAttribute('aria-expanded', 'false');
    }

    // Fecha menu quando clicar num link interno
    var menu = getMenu();
    if (menu) {
      var links = menu.querySelectorAll('a');
      for (var i = 0; i < links.length; i++) {
        links[i].addEventListener('click', function () {
          // pequeno delay pra animação ficar suave
          setTimeout(closeMenu, 50);
        });
      }
    }

    // Fecha menu se redimensionar pra desktop
    var resizeTimer;
    window.addEventListener('resize', function () {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(function () {
        if (window.innerWidth > 768) {
          closeMenu();
        }
      }, 150);
    });

    // ESC fecha o menu
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') closeMenu();
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
