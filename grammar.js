
// grammar.js — iOS-like design + full support for "quiz" and "grammar_test"
(function(){
  const tg = window.Telegram && window.Telegram.WebApp;
  const root = () => document.getElementById('grammar-root');
  const pageEl = () => document.getElementById('grammar-page');
  let TREE = null;
  const path = [];

  // Inject CSS link once (no need to change index.html)
  function injectCSS(){
    if (document.getElementById('grammar-ios-css')) return;
    const link = document.createElement('link');
    link.id = 'grammar-ios-css';
    link.rel = 'stylesheet';
    link.href = 'grammar-ui.css?v=' + Date.now();
    document.head.appendChild(link);
  }

  function byPath(obj, arr){
    return arr.reduce((o,k)=> (o && o[k]) || null, obj);
  }
  function isLeaf(node){
    return node && typeof node === 'object' && (node.type === 'text' || node.type === 'quiz' || node.type === 'grammar_test');
  }
  function title(){
    return path.length ? path[path.length-1] : "📚 Grammar";
  }

  function escapeHTML(s){ return String(s || '').replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }

  // Render text content into nice cards with bullet list support
  function renderRich(text){
    const lines = (text || '').split(/\r?\n/);
    let html = '', inList = false;
    for (const ln of lines){
      const m = ln.match(/^\s*[-•]\s+(.*)$/);
      if (m){
        if (!inList){ html += '<ul class="tg-list">'; inList = true; }
        html += `<li>${escapeHTML(m[1])}</li>`;
      } else {
        if (inList){ html += '</ul>'; inList = false; }
        if (ln.trim() === '') { html += '<div style="height:8px"></div>'; }
        else { html += `<p class="tg-sub">${escapeHTML(ln)}</p>`; }
      }
    }
    if (inList) html += '</ul>';
    return `<div class="tg-card">${html}</div>`;
  }

  function setHeader(t){
    const h1 = pageEl() && pageEl().querySelector('.header h1');
    if (h1) h1.textContent = t;
  }

  function renderList(node){
    root().innerHTML = '';
    const container = root();
    container.classList.add('section-grid');
    Object.keys(node).forEach(k => {
      const card = document.createElement('div');
      card.className = 'section-card';
      card.innerHTML = `<h3>${k}</h3>`;
      card.onclick = () => { path.push(k); render(); };
      container.appendChild(card);
    });
    setHeader(title());
  }

  // Helpers for tests that store letters differently
  function getOptionLetter(optText){
    const m = String(optText).trim().match(/^([A-ZА-Я])[\.\)]/i);
    return m ? m[1].toUpperCase() : null;
  }
  function getCorrectLetter(q){
    const ca = q.correct_answer;
    if (!ca) return null;
    if (typeof ca === 'string'){
      // can be "B" or "B. went"
      const m = ca.trim().match(/^([A-ZА-Я])/i);
      return m ? m[1].toUpperCase() : null;
    }
    return String(ca).toUpperCase();
  }

  function renderTest(leaf){
    const container = root();
    container.classList.remove('section-grid');
    container.innerHTML = '';

    const back = document.createElement('button');
    back.className = 'back-btn';
    back.textContent = '← Назад';
    back.onclick = () => { path.pop(); render(); };
    container.appendChild(back);

    const h = document.createElement('div');
    h.className = 'tg-headline';
    h.textContent = title();
    container.appendChild(h);

    const info = document.createElement('div');
    info.className = 'tg-card';
    info.innerHTML = `<div class="tg-sub">${leaf.instructions || 'Выберите правильный вариант'}</div>`;
    container.appendChild(info);

    let idx = 0, score = 0;
    const answers = [];
    const qWrap = document.createElement('div');
    container.appendChild(qWrap);

    const ctaBar = document.createElement('div');
    ctaBar.className = 'tg-cta-bar';
    const nextBtn = document.createElement('button');
    nextBtn.className = 'tg-cta';
    nextBtn.textContent = 'Далее';
    ctaBar.appendChild(nextBtn);
    container.appendChild(ctaBar);

    function renderQuestion(){
      const q = leaf.questions[idx];
      qWrap.innerHTML = `<div class="tg-card" style="margin-top:10px;">
          <div class="tg-sub" style="font-weight:600;margin-bottom:8px;">Вопрос ${idx+1} из ${leaf.questions.length}</div>
          <div class="tg-sub">${escapeHTML(q.text)}</div>
        </div>`;

      (q.options || []).forEach(opt => {
        const div = document.createElement('div');
        div.className = 'section-card';
        div.style.marginTop = '10px';
        div.textContent = opt;
        div.onclick = () => {
          answers[idx] = getOptionLetter(opt) || opt[0];
          [...qWrap.querySelectorAll('.section-card')].forEach(el => el.style.opacity = '0.6');
          div.style.opacity = '1';
        };
        qWrap.appendChild(div);
      });

      nextBtn.textContent = idx === leaf.questions.length - 1 ? 'Завершить' : 'Далее';
    }

    nextBtn.onclick = () => {
      const q = leaf.questions[idx];
      const chosen = answers[idx];
      if (!chosen) { tg && tg.HapticFeedback && tg.HapticFeedback.notificationOccurred('warning'); return; }
      if ((getCorrectLetter(q) || '').toUpperCase() === String(chosen).toUpperCase()) score++;

      if (idx < leaf.questions.length - 1){
        idx++; renderQuestion();
      } else {
        qWrap.innerHTML = `<div class="tg-card">
            <div class="tg-headline" style="font-size:18px;">Результат: ${score} / ${leaf.questions.length}</div>
            <div class="tg-sub">Разбор вопросов ниже.</div>
          </div>`;
        leaf.questions.forEach((q, i) => {
          const row = document.createElement('div');
          row.className = 'tg-card';
          row.style.marginTop = '10px';
          const correct = getCorrectLetter(q) || '—';
          const your = answers[i] || '—';
          row.innerHTML = `<div class="tg-sub" style="font-weight:600;margin-bottom:6px;">${i+1}. ${escapeHTML(q.text)}</div>
            <div class="tg-sub">Ваш ответ: ${your} · Правильный: ${correct}</div>
            ${q.explanation ? `<div class="tg-sub" style="margin-top:6px;">${escapeHTML(q.explanation)}</div>` : ''}`;
          qWrap.appendChild(row);
        });
        ctaBar.remove();
      }
    };

    renderQuestion();
    tg && tg.MainButton && tg.MainButton.hide();
  }

  function renderLeaf(leaf){
    if (leaf.type === 'text'){
      const container = root();
      container.classList.remove('section-grid');
      container.innerHTML = '';

      const back = document.createElement('button');
      back.className = 'back-btn';
      back.textContent = '← Назад';
      back.onclick = () => { path.pop(); render(); };
      container.appendChild(back);

      const h = document.createElement('div');
      h.className = 'tg-headline';
      h.textContent = title();
      container.appendChild(h);

      container.insertAdjacentHTML('beforeend', renderRich(leaf.content || ''));
      tg && tg.MainButton && tg.MainButton.hide();
      return;
    }

    if (leaf.type === 'quiz' || leaf.type === 'grammar_test'){
      renderTest(leaf);
      return;
    }
  }

  function render(){
    injectCSS();
    const node = byPath(TREE, path);
    if (!node) return;
    if (isLeaf(node)) renderLeaf(node);
    else renderList(node);
    setHeader(title());
  }

  async function loadTree(){
    const res = await fetch('grammar_categories_tree.json');
    let text = await res.text();
    try { TREE = JSON.parse(text); }
    catch(e){ text = text.replace(/,\s*}/g, '}').replace(/,\s*]/g, ']'); TREE = JSON.parse(text); }
  }

  async function init(){
    await loadTree();
    const openSection = window.openSection;
    window.openSection = function(name){
      if (name === 'grammar'){ showPage('grammar'); path.length = 0; render(); return; }
      if (typeof openSection === 'function') return openSection(name);
    };
    const oldShow = window.showPage;
    window.showPage = function(id){
      oldShow(id);
      if (id === 'grammar'){ path.length = 0; render(); }
    };
  }

  document.addEventListener('DOMContentLoaded', init);
})();
