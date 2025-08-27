async function loadTree(group){
  const r = await fetch(`/catalog/tree?group=${encodeURIComponent(group)}`);
  if (!r.ok) throw new Error('failed_tree');
  return r.json();
}

function el(tag, className, html){
  const n = document.createElement(tag);
  if (className) n.className = className;
  if (html != null) n.innerHTML = html;
  return n;
}

function renderTree(rootEl, group, tree){
  rootEl.innerHTML = '';
  const sections = tree.sections || [];
  sections.forEach(section => {
    const secCard = el('section', 'card');
    const secHeader = el('div', 'row');
    secHeader.appendChild(el('h2', '', section.title));
    const toggleBtn = el('a', 'chip', 'Показать');
    toggleBtn.href = 'javascript:void(0)';
    secHeader.appendChild(toggleBtn);
    secCard.appendChild(secHeader);

    const subsWrap = el('div', 'grid');
    subsWrap.style.display = 'none';
    section.subsections.forEach(sub => {
      const subCard = el('section', 'card');
      const subHeader = el('div', 'row');
      subHeader.appendChild(el('div', '', `<b>${sub.title}</b>`));
      const subToggle = el('a', 'chip secondary', 'Открыть');
      subToggle.href = 'javascript:void(0)';
      subHeader.appendChild(subToggle);
      subCard.appendChild(subHeader);

      const unitsWrap = el('div', 'grid');
      unitsWrap.style.display = 'none';
      sub.units.forEach(u => {
        const unitCard = el('section', 'card');
        unitCard.appendChild(el('div', '', `<b>${u.title}</b>`));
        const row = el('div', 'row');
        if (u.hasPractice) {
          const btn = el('a', 'btn', 'Start practice');
          btn.href = 'javascript:void(0)';
          btn.onclick = () => onSelectUnit(u);
          row.appendChild(btn);
        } else {
          row.appendChild(el('span', 'badge', 'Practice coming soon'));
        }
        unitCard.appendChild(row);
        unitsWrap.appendChild(unitCard);
      });
      subCard.appendChild(unitsWrap);
      subToggle.onclick = () => {
        unitsWrap.style.display = (unitsWrap.style.display === 'none') ? 'grid' : 'none';
      };
      subsWrap.appendChild(subCard);
    });
    secCard.appendChild(subsWrap);
    toggleBtn.onclick = () => {
      subsWrap.style.display = (subsWrap.style.display === 'none') ? 'grid' : 'none';
    };
    rootEl.appendChild(secCard);
  });
}

async function onSelectUnit(unit){
  try {
    const lessonId = (unit.lessonIds && unit.lessonIds[0]) || null;
    if (!lessonId) {
      alert('Нет уроков для этого юнита');
      return;
    }
    // Navigate to SPA and let it open the lesson by id
    const group = (window.__GROUP__ || 'grammar');
    window.location.href = `/static/index.html?group=${encodeURIComponent(group)}&lesson_id=${lessonId}`;
  } catch (e) {
    console.error(e);
    alert('Ошибка открытия практики');
  }
}

async function bootClassic(group){
  try {
    const data = await loadTree(group);
    const root = document.getElementById('classic-root');
    renderTree(root, group, data);
  } catch (e) {
    const root = document.getElementById('classic-root');
    root.innerHTML = '<div class="muted">Не удалось загрузить каталог</div>';
  }
}
