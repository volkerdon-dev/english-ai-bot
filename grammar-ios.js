
(function(){
  const tg = window.Telegram && window.Telegram.WebApp;
  const root = () => document.getElementById('grammar-root');
  const pageEl = () => document.getElementById('grammar-page');
  let TREE = null; const path = [];

  function injectCSS(){
    if (document.getElementById('grammar-ios-css')) return;
    const link = document.createElement('link');
    link.id = 'grammar-ios-css'; link.rel = 'stylesheet';
    link.href = 'grammar-ui.css?v=' + Date.now();
    document.head.appendChild(link);
  }
  function byPath(obj, arr){ return arr.reduce((o,k)=> (o && o[k]) || null, obj); }
  function isLeaf(node){ return node && typeof node === 'object' && (node.type === 'text' || node.type === 'quiz'); }
  function title(){ return path.length ? path[path.length-1] : "📚 Grammar"; }

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
  function escapeHTML(s){ return s.replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }
  function setHeader(t){ const h1 = pageEl() && pageEl().querySelector('.header h1'); if (h1) h1.textContent = t; }

  function renderList(node){
    root().innerHTML = ''; const c = root(); c.classList.add('section-grid');
    Object.keys(node).forEach(k => { const card = document.createElement('div');
      card.className = 'section-card'; card.innerHTML = `<h3>${k}</h3>`; card.onclick = () => { path.push(k); render(); }; c.appendChild(card); });
    setHeader(title());
  }

  function renderLeaf(leaf){
    const c = root(); c.classList.remove('section-grid'); c.innerHTML = '';
    const back = document.createElement('button'); back.className = 'back-btn'; back.textContent = '← Назад'; back.onclick = () => { path.pop(); render(); }; c.appendChild(back);
    const h = document.createElement('div'); h.className = 'tg-headline'; h.textContent = title(); c.appendChild(h);

    if (leaf.type === 'text'){ c.insertAdjacentHTML('beforeend', renderRich(leaf.content || '')); return; }

    if (leaf.type === 'quiz'){
      const info = document.createElement('div'); info.className = 'tg-card';
      info.innerHTML = `<div class="tg-sub">${leaf.instructions || 'Выберите правильный вариант'}</div>`; c.appendChild(info);
      let idx = 0, score = 0; const answers = []; const qWrap = document.createElement('div'); c.appendChild(qWrap);
      const ctaBar = document.createElement('div'); ctaBar.className = 'tg-cta-bar';
      const nextBtn = document.createElement('button'); nextBtn.className = 'tg-cta'; nextBtn.textContent = 'Далее';
      ctaBar.appendChild(nextBtn); c.appendChild(ctaBar);

      function renderQuestion(){
        const q = leaf.questions[idx]; qWrap.innerHTML = `<div class="tg-card" style="margin-top:10px;">
            <div class="tg-sub" style="font-weight:600;margin-bottom:8px;">Вопрос ${idx+1} из ${leaf.questions.length}</div>
            <div class="tg-sub">${escapeHTML(q.text)}</div></div>`;
        q.options.forEach(opt => { const div = document.createElement('div'); div.className = 'section-card'; div.style.marginTop = '10px'; div.textContent = opt;
          div.onclick = () => { answers[idx] = opt[0]; [...qWrap.querySelectorAll('.section-card')].forEach(el => el.style.opacity = '0.6'); div.style.opacity = '1'; };
          qWrap.appendChild(div); });
        nextBtn.textContent = idx === leaf.questions.length - 1 ? 'Завершить' : 'Далее';
      }

      nextBtn.onclick = () => { const q = leaf.questions[idx]; const chosen = answers[idx]; if (!chosen) { tg && tg.HapticFeedback && tg.HapticFeedback.notificationOccurred('warning'); return; }
        if (chosen === q.correct_answer) score++;
        if (idx < leaf.questions.length - 1){ idx++; renderQuestion();
        } else { qWrap.innerHTML = `<div class="tg-card"><div class="tg-headline" style="font-size:18px;">Результат: ${score} / ${leaf.questions.length}</div><div class="tg-sub">Разбор вопросов ниже.</div></div>`;
          leaf.questions.forEach((q,i)=>{ const row = document.createElement('div'); row.className = 'tg-card'; row.style.marginTop = '10px';
            row.innerHTML = `<div class="tg-sub" style="font-weight:600;margin-bottom:6px;">${i+1}. ${escapeHTML(q.text)}</div>
            <div class="tg-sub">Ваш ответ: ${answers[i] || '—'} · Правильный: ${q.correct_answer}</div>
            ${q.explanation ? `<div class="tg-sub" style="margin-top:6px;">${escapeHTML(q.explanation)}</div>` : ''}`; qWrap.appendChild(row); });
          ctaBar.remove(); } };

      renderQuestion(); tg && tg.MainButton && tg.MainButton.hide(); return;
    }
  }

  function render(){ injectCSS(); const node = byPath(TREE, path); if (!node) return; if (isLeaf(node)) renderLeaf(node); else renderList(node); setHeader(title()); }
  async function loadTree(){ const r = await fetch('grammar_categories_tree.json'); let t = await r.text(); try{ TREE = JSON.parse(t);}catch(e){t=t.replace(/,\s*}/g,'}').replace(/,\s*]/g,']'); TREE=JSON.parse(t);} }
  async function init(){ await loadTree();
    const o = window.openSection; window.openSection = function(n){ if (n==='grammar'){ showPage('grammar'); path.length=0; render(); return; } if (typeof o==='function') return o(n); };
    const s = window.showPage; window.showPage = function(id){ s(id); if (id==='grammar'){ path.length=0; render(); } };
  }
  document.addEventListener('DOMContentLoaded', init);
})();
