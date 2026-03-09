const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

function show(screen) {
  $$('.screen').forEach((el) => el.classList.toggle('hidden', el.dataset.screen !== screen));
  $$('.navbtn').forEach((b) => b.classList.toggle('active', b.dataset.go === screen));
}

function wireNav() {
  $$('.navbtn').forEach((b) => b.addEventListener('click', () => show(b.dataset.go)));
  $$('[data-go]').forEach((el) => {
    el.addEventListener('click', () => {
      const to = el.dataset.go;
      if (to) show(to);
    });
  });
}

function seedThreads() {
  return [
    { id: 't1', title: '新对话', meta: '03/01 19:20', preview: '我懂。先把信息架构收敛，再做细节。' },
    { id: 't2', title: '产品定位', meta: '03/01 18:02', preview: '可以。你先说目标用户与场景。' },
    { id: 't3', title: 'UI 风格', meta: '02/28 22:11', preview: '我建议走建筑事务所式：黑白灰、留白、细线。' },
  ];
}

function renderThreads() {
  const host = $('#threadList');
  if (!host) return;
  const threads = seedThreads();
  host.innerHTML = '';
  threads.forEach((t) => {
    const el = document.createElement('div');
    el.className = 'thread';
    el.innerHTML = `
      <div class="grow">
        <div class="row between">
          <div class="title">${t.title}</div>
          <div class="meta">${t.meta}</div>
        </div>
        <div class="preview">${t.preview}</div>
      </div>
      <div class="actions">
        <button class="btn" data-open="${t.id}">进入</button>
        <button class="btn" data-del="${t.id}">删除</button>
      </div>
    `;
    host.appendChild(el);
  });

  $$('[data-open]').forEach((b) => b.addEventListener('click', () => show('chat')));
  $$('[data-del]').forEach((b) =>
    b.addEventListener('click', () => {
      const node = b.closest('.thread');
      if (!node) return;
      node.remove();
    })
  );
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch (_) {
    return false;
  }
}

function wireCopy() {
  $$('[data-copy]').forEach((btn) => {
    btn.addEventListener('click', async (e) => {
      e.preventDefault();
      e.stopPropagation();
      const bubble = btn.closest('.bubble');
      if (!bubble) return;
      const text = bubble.childNodes[0].textContent.trim();
      const ok = await copyText(text);
      btn.textContent = ok ? '已复制' : '复制失败';
      setTimeout(() => (btn.textContent = '复制'), 900);
    });
  });
}

wireNav();
renderThreads();
wireCopy();
show('login');

