
// Dynamically render grammar categories from grammar_categories_tree.json
(function(){
  const tg = window.Telegram && window.Telegram.WebApp;
  const root = () => document.getElementById('grammar-root');
  const pageEl = () => document.getElementById('grammar-page');

  let TREE = null;
  const path = []; // stack of keys

  function byPath(obj, arr){
    return arr.reduce((o,k)=> (o && o[k]) || null, obj);
  }

  function titleFromPath(){
    if (path.length === 0) return "📚 Grammar";
    return path[path.length-1];
  }

  function isLeaf(node){
    return node && typeof node === 'object' && node.type === 'text';
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

    const box = document.createElement('div');
    box.className = 'detail-box';
    box.style.whiteSpace = 'pre-wrap';
    box.style.lineHeight = '1.5';
    box.style.fontSize = '15px';
    box.innerText = leaf.content || '';
    container.appendChild(box);

    // Show a button to go back to list one level up
    tg && tg.MainButton.hide();
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
    // load JSON; try to recover from trailing commas if any
    const res = await fetch('grammar_categories_tree.json');
    let text = await res.text();
    try {
      TREE = JSON.parse(text);
    } catch (e) {
      // remove trailing commas and BOM if present
      text = text.replace(/,\s*}/g, '}').replace(/,\s*]/g, ']');
      TREE = JSON.parse(text);
    }
  }

  async function init(){
    await loadTree();
    path.length = 0;
    // When entering the 'Grammar' page, render top-level
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

    // Also intercept showPage('grammar')
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
