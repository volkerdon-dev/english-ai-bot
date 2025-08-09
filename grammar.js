
(function(){
  const tg = window.Telegram && window.Telegram.WebApp;
  const root = () => document.getElementById('grammar-root');
  const pageEl = () => document.getElementById('grammar-page');

  let TREE = null;
  const path = [];

  function byPath(obj, arr){
    return arr.reduce((o,k)=> (o && o[k]) || null, obj);
  }

  function titleFromPath(){
    if (path.length === 0) return "📚 Grammar";
    return path[path.length-1];
  }

  function isLeaf(node){
    return node && typeof node === 'object' && (node.type === 'text' || node.type === 'quiz');
  }

  function renderList(node){
    const keys = Object.keys(node);
    root().innerHTML = '';
    const container = root();
    container.classList.add('section-grid');
    keys.forEach(k=>{
      const card = document.createElement('div');
      card.className = 'section-card';
      card.innerHTML = `<h3>${k}</h3>`;
      card.addEventListener('click', ()=>{
        path.push(k);
        render();
      });
      container.appendChild(card);
    });
    setHeader(titleFromPath());
  }

  function renderLeaf(leaf){
    const container = root();
    container.classList.remove('section-grid');
    container.innerHTML = '';
    const back = document.createElement('button');
    back.className = 'back-btn';
    back.textContent = '← Назад';
    back.addEventListener('click', ()=>{ path.pop(); render(); });
    container.appendChild(back);

    const h2 = document.createElement('h2');
    h2.textContent = titleFromPath();
    container.appendChild(h2);

    if (leaf.type === 'text') {
      const box = document.createElement('div');
      box.className = 'detail-box';
      box.style.whiteSpace = 'pre-wrap';
      box.innerText = leaf.content || '';
      container.appendChild(box);
      tg && tg.MainButton.hide();
      return;
    }

    if (leaf.type === 'quiz') {
      const title = document.createElement('div');
      title.className = 'muted';
      title.style.margin = '6px 0 14px';
      title.innerText = leaf.instructions || 'Выберите правильный вариант';
      container.appendChild(title);

      let idx = 0;
      let score = 0;
      const answers = [];

      const qWrap = document.createElement('div');
      container.appendChild(qWrap);

      const nextBtn = document.createElement('button');
      nextBtn.className = 'btn';
      nextBtn.style.marginTop = '14px';
      nextBtn.textContent = 'Далее';
      container.appendChild(nextBtn);

      function renderQuestion() {
        const q = leaf.questions[idx];
        qWrap.innerHTML = '';
        const qBox = document.createElement('div');
        qBox.className = 'detail-box';
        qBox.style.padding = '16px';
        qBox.innerHTML = `<div style="font-weight:600;margin-bottom:8px;">Вопрос ${idx+1} из ${leaf.questions.length}</div><div>${q.text}</div>`;
        qWrap.appendChild(qBox);

        q.options.forEach((opt, i) => {
          const card = document.createElement('div');
          card.className = 'section-card';
          card.style.cursor = 'pointer';
          card.textContent = opt;
          card.addEventListener('click', () => {
            answers[idx] = opt[0];
            [...qWrap.querySelectorAll('.section-card')].forEach(el=> el.style.opacity='0.6');
            card.style.opacity = '1';
          });
          qWrap.appendChild(card);
        });

        nextBtn.textContent = idx === leaf.questions.length - 1 ? 'Завершить' : 'Далее';
      }

      nextBtn.addEventListener('click', () => {
        const q = leaf.questions[idx];
        const chosen = answers[idx];
        if (!chosen) { tg && tg.HapticFeedback && tg.HapticFeedback.notificationOccurred('warning'); return; }
        if (chosen === q.correct_answer) score++;

        if (idx < leaf.questions.length - 1) {
          idx++;
          renderQuestion();
        } else {
          qWrap.innerHTML = '';
          const res = document.createElement('div');
          res.className = 'detail-box';
          res.style.padding = '16px';
          res.innerHTML = `<div style="font-weight:700;font-size:18px;margin-bottom:8px;">Результат: ${score} / ${leaf.questions.length}</div>`;
          qWrap.appendChild(res);

          leaf.questions.forEach((q, i) => {
            const row = document.createElement('div');
            row.className = 'section-card';
            const your = answers[i] || '—';
            row.innerHTML = `<div style="font-weight:600;margin-bottom:6px;">${i+1}. ${q.text}</div>
              <div>Ваш ответ: ${your} · Правильный: ${q.correct_answer}</div>
              ${q.explanation ? `<div class="muted" style="margin-top:6px;">${q.explanation}</div>` : ''}`;
            qWrap.appendChild(row);
          });

          nextBtn.remove();
        }
      });

      renderQuestion();
      tg && tg.MainButton.hide();
      return;
    }
  }

  function setHeader(title){
    const h1 = pageEl().querySelector('.header h1');
    if (h1) h1.textContent = title;
  }

  function render(){
    const node = byPath(TREE, path);
    if (!node) return;

    if (isLeaf(node)){
      renderLeaf(node);
    } else {
      renderList(node);
    }
  }

  async function loadTree(){
    const res = await fetch('grammar_categories_tree.json');
    let text = await res.text();
    try {
      TREE = JSON.parse(text);
    } catch (e) {
      text = text.replace(/,\\s*}/g, '}').replace(/,\\s*]/g, ']');
      TREE = JSON.parse(text);
    }
  }

  async function init(){
    await loadTree();
    path.length = 0;

    const openSection = window.openSection;
    window.openSection = function(name){
      if (name === 'grammar'){
        showPage('grammar');
        path.length = 0;
        render();
        return;
      }
      if (typeof openSection === 'function') return openSection(name);
    }

    const oldShow = window.showPage;
    window.showPage = function(id){
      oldShow(id);
      if (id === 'grammar'){
        path.length = 0;
        render();
      }
    }
  }

  document.addEventListener('DOMContentLoaded', init);
})();
