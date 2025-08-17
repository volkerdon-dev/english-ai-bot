// grammar.js — robust leaf detection + iOS-like UI (with universal quiz support)
(function(){
  const tg = window.Telegram && window.Telegram.WebApp;
  const root = () => document.getElementById('grammar-root');
  const pageEl = () => document.getElementById('grammar-page');
  let TREE = null;
  const path = [];

  // Inject CSS once (keeps index.html unchanged)
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

  function hasQuestions(node){
    // accept arrays or objects for questions
    return node && typeof node === 'object' && ('questions' in node);
  }
  function hasContent(node){
    return node && typeof node === 'object' && typeof node.content === 'string';
  }
  function normalizeType(t){
    return (t || '').toString().trim().toLowerCase();
  }
  function isLeaf(node){
    if (!node || typeof node !== 'object') return false;
    const t = normalizeType(node.type);
    if (t === 'text' || t === 'quiz' || t === 'grammar_test' || t === 'content_from_file') return true;
    // Fallbacks: treat any object with questions as test, or with content as text
    if (hasQuestions(node)) return true;
    if (hasContent(node)) return true;
    return false;
  }

  function title(){
    return path.length ? path[path.length-1] : "📚 Grammar";
  }

  function escapeHTML(s){ return String(s || '').replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }

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

  // replaced: renderList with grouping Theory/Practice
  function renderList(node){
    root().innerHTML = '';
    const container = root();
    container.classList.add('section-grid');

    const keys = Object.keys(node);
    const practiceFor = new Set();
    keys.forEach(k => {
      const m = String(k).match(/^\s*Practice:\s*(.+)$/i);
      if (m && m[1]) practiceFor.add(m[1].trim());
    });

    keys.forEach(k => {
      const isPractice = /^\s*Practice:\s*/i.test(String(k));
      // Если есть пара «Теория + Практика», скрываем дубликат Practice в списке
      if (isPractice){
        const base = String(k).replace(/^\s*Practice:\s*/i, '').trim();
        if (keys.includes(base)) return;
      }

      const card = document.createElement('div');
      card.className = 'section-card';
      card.innerHTML = `<h3>${k}</h3>`;

      if (!isPractice && practiceFor.has(String(k).trim())){
        card.onclick = () => { path.push(k); renderChooserForTopic(k); };
      } else {
        card.onclick = () => { path.push(k); render(); };
      }

      container.appendChild(card);
    });
    setHeader(title());
  }

  // Меню выбора для темы: Теория / Практика
  function renderChooserForTopic(baseKey){
    const container = root();
    container.classList.add('section-grid');
    container.innerHTML = '';
    setHeader(title());

    const theory = document.createElement('div');
    theory.className = 'section-card';
    theory.innerHTML = '<h3>📖 Теория</h3><p>Правила и примеры</p>';
    theory.onclick = () => { /* остаёмся на базовой теме */ render(); };

    const practice = document.createElement('div');
    practice.className = 'section-card';
    practice.innerHTML = '<h3>✍️ Практика</h3><p>Тест по теме</p>';
    practice.onclick = () => { path[path.length - 1] = `Practice: ${baseKey}`; render(); };

    container.appendChild(theory);
    container.appendChild(practice);
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
      const m = ca.trim().match(/^([A-ZА-Я])/i);
      return m ? m[1].toUpperCase() : null;
    }
    return String(ca).toUpperCase();
  }
  function displayOptionText(opt){
    const s = String(opt || '').trim();
    const m = s.match(/^([A-ZА-Я])[\.\)]\s*(.*)$/i);
    return m ? m[2] : s;
  }

  function toArrayQuestions(questions){
    if (Array.isArray(questions)) return questions;
    if (questions && typeof questions === 'object') return Object.values(questions);
    return [];
  }

  function renderTest(leaf){
    const container = root();
    container.classList.remove('section-grid');
    container.innerHTML = '';

    // Header already shows title and Back/Home. Avoid duplicating controls here.
    setHeader(leaf.title || title());

    const info = document.createElement('div');
    info.className = 'tg-card';
    info.innerHTML = `<div class="tg-sub">${leaf.instructions || 'Выберите правильный вариант'}</div>`;
    container.appendChild(info);

    const questions = toArrayQuestions(leaf.questions);
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
      const q = questions[idx] || {};
      const qText = q.text || q.question || '';
      qWrap.innerHTML = `<div class="tg-card" style="margin-top:10px;">
          <div class="tg-sub" style="font-weight:600;margin-bottom:8px;">Вопрос ${idx+1} из ${questions.length}</div>
          <div class="tg-sub">${escapeHTML(qText)}</div>
        </div>`;

      (q.options || []).forEach(opt => {
        const div = document.createElement('div');
        div.className = 'section-card';
        div.style.marginTop = '10px';
        div.textContent = opt;
        div.onclick = () => {
          answers[idx] = opt;
          [...qWrap.querySelectorAll('.section-card')].forEach(el => el.style.opacity = '0.6');
          div.style.opacity = '1';
        };
        qWrap.appendChild(div);
      });

      nextBtn.textContent = idx === questions.length - 1 ? 'Завершить' : 'Далее';
    }

    nextBtn.onclick = () => {
      const q = questions[idx] || {};
      const chosen = answers[idx];
      if (!chosen) { tg && tg.HapticFeedback && tg.HapticFeedback.notificationOccurred('warning'); return; }
      if ((getCorrectLetter(q) || '').toUpperCase() === (getOptionLetter(chosen) || '').toUpperCase()) score++;

      if (idx < questions.length - 1){
        idx++; renderQuestion();
      } else {
        qWrap.innerHTML = `<div class="tg-card">
            <div class="tg-headline" style="font-size:18px;">Результат: ${score} / ${questions.length}</div>
            <div class="tg-sub">Разбор вопросов ниже.</div>
          </div>`;
        questions.forEach((q, i) => {
          const row = document.createElement('div');
          row.className = 'tg-card';
          row.style.marginTop = '10px';
          const correctLetter = getCorrectLetter(q) || '—';
          const chosenOpt = answers[i];
          const chosenLetter = getOptionLetter(chosenOpt) || '';
          const isCorrect = String(chosenLetter).toUpperCase() === String(correctLetter).toUpperCase();
          const correctText = (q.options || []).find(o => (getOptionLetter(o) || '').toUpperCase() === String(correctLetter).toUpperCase()) || q.correct_answer || '—';
          const qText = (q && (q.text || q.question)) || '';
          row.innerHTML = `<div class="tg-sub" style="font-weight:600;margin-bottom:6px;">${i+1}. ${escapeHTML(qText)}</div>
            <div class="tg-sub" style="${isCorrect ? 'color:#34c759;' : 'color:#ef4444;'}">Ваш ответ: ${escapeHTML(chosenOpt || '—')}</div>
            <div class="tg-sub">Правильный: ${escapeHTML(correctText)}</div>
            ${q && q.explanation ? `<div class="tg-sub" style="margin-top:6px;">${escapeHTML(q.explanation)}</div>` : ''}`;
          qWrap.appendChild(row);
        });
        ctaBar.remove();
      }
    };

    renderQuestion();
    tg && tg.MainButton && tg.MainButton.hide();
  }

  async function renderFromFile(leaf){
    const container = root();
    container.classList.remove('section-grid');
    container.innerHTML = '';

    // Use header for title
    setHeader(leaf.title || title());

    const filePath = leaf.file || '';
    try {
      const res = await fetch(filePath);
      const data = await res.json();

      // Heuristics: if array of verbs with base/past/participle
      const isIrregularVerbs = Array.isArray(data) && data.length && typeof data[0] === 'object' && ('base' in data[0]) && ('past' in data[0]) && ('participle' in data[0]);
      if (isIrregularVerbs){
        renderIrregularVerbsTable(container, data);
      } else {
        const card = document.createElement('div');
        card.className = 'tg-card';
        card.innerHTML = '<div class="tg-sub">Не удалось распознать формат файла для отображения.</div>';
        container.appendChild(card);
      }
    } catch(e){
      const card = document.createElement('div');
      card.className = 'tg-card';
      card.innerHTML = `<div class="tg-sub">Ошибка загрузки файла: ${escapeHTML(String(e))}</div>`;
      container.appendChild(card);
    }

    tg && tg.MainButton && tg.MainButton.hide();
  }

  function renderIrregularVerbsTable(container, verbs){
    // Search box
    const searchWrap = document.createElement('div');
    searchWrap.className = 'tg-card';
    searchWrap.innerHTML = `
      <input class="tg-input" type="text" placeholder="Поиск: base / V2 / V3 / перевод" aria-label="Поиск по таблице" />
      <div class="tg-sub" style="margin-top:8px;"><span class="iv-count"></span></div>
    `;
    container.appendChild(searchWrap);
    const input = searchWrap.querySelector('input');
    const countEl = searchWrap.querySelector('.iv-count');

    // Table wrapper
    const wrap = document.createElement('div');
    wrap.className = 'tg-table-wrap tg-card';
    container.appendChild(wrap);

    const table = document.createElement('table');
    table.className = 'tg-table verbs-table';
    table.innerHTML = `
      <thead>
        <tr>
          <th>Base (V1)</th>
          <th>Past (V2)</th>
          <th>Participle (V3)</th>
          <th>Перевод</th>
        </tr>
      </thead>
      <tbody></tbody>
    `;
    wrap.appendChild(table);
    const tbody = table.querySelector('tbody');

    const data = [...verbs].sort((a,b)=> String(a.base).localeCompare(String(b.base)));

    function renderRows(list){
      tbody.innerHTML = '';
      list.forEach(v => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td>${escapeHTML(v.base)}</td>
          <td>${escapeHTML(v.past)}</td>
          <td>${escapeHTML(v.participle)}</td>
          <td>${escapeHTML(v.translation || '')}</td>
        `;
        tbody.appendChild(tr);
      });
      countEl.textContent = `Показано: ${list.length} из ${data.length}`;
    }

    function normalize(s){ return String(s || '').toLowerCase(); }

    input.addEventListener('input', () => {
      const q = normalize(input.value);
      if (!q){ renderRows(data); return; }
      const filtered = data.filter(v =>
        normalize(v.base).includes(q) ||
        normalize(v.past).includes(q) ||
        normalize(v.participle).includes(q) ||
        normalize(v.translation).includes(q)
      );
      renderRows(filtered);
    });

    renderRows(data);
  }

  function renderLeaf(leaf){
    const t = normalizeType(leaf.type);
    if (t === 'text' || hasContent(leaf)){
      const container = root();
      container.classList.remove('section-grid');
      container.innerHTML = '';

      // Only use header title, avoid duplicate h inside content
      setHeader(leaf.title || title());

      container.insertAdjacentHTML('beforeend', renderRich(leaf.content || ''));

      // Показать кнопку «Перейти к практике», если у темы есть соответствующий раздел Practice
      try {
        const currentKey = path[path.length - 1];
        const parentNode = byPath(TREE, path.slice(0, -1));
        const practiceKey = `Practice: ${currentKey}`;
        if (parentNode && parentNode[practiceKey] && isLeaf(parentNode[practiceKey])){
          const ctaBar = document.createElement('div');
          ctaBar.className = 'tg-cta-bar';
          const btn = document.createElement('button');
          btn.className = 'tg-cta';
          btn.textContent = 'Перейти к практике';
          btn.onclick = () => { path[path.length - 1] = practiceKey; render(); };
          ctaBar.appendChild(btn);
          container.appendChild(ctaBar);
        }
      } catch(_){}

      tg && tg.MainButton && tg.MainButton.hide();
      return;
    }

    if (t === 'quiz' || t === 'grammar_test' || hasQuestions(leaf)){
      renderTest(leaf);
      return;
    }

    if (t === 'content_from_file'){
      renderFromFile(leaf);
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

    // Expose Grammar back handler for global Back button
    window.grammarBack = function(){
      const page = pageEl();
      if (!page || !page.classList.contains('active')) return false;
      if (path.length > 0){ path.pop(); render(); return true; }
      return false;
    };
  }

  document.addEventListener('DOMContentLoaded', init);
})();