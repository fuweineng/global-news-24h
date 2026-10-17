// 南海政务 — 佛山南海政务新闻 + 租金标签
(function () {
  'use strict';

  const DATA_FILE = '/data/nanhai.json';
  const PAGE_SIZE = 30;

  const state = {
    all: [],
    updated: null,
    category: null,   // 分类筛选；'__rent' 表示仅看租金相关
    tag: null,        // 标签筛选
    query: '',
    visible: PAGE_SIZE,
    loading: false
  };

  const $newsList = document.getElementById('news-list');
  const $loading = document.getElementById('loading');
  const $empty = document.getElementById('empty');
  const $loadMore = document.getElementById('load-more');
  const $main = document.getElementById('main-feed');
  const $fab = document.getElementById('fab');
  const $updateTime = document.getElementById('last-updated');
  const $catBar = document.getElementById('category-bar');
  const $tagBar = document.getElementById('tag-bar');
  const $query = document.getElementById('nh-query');

  // ── Helpers ────────────────────────────────────
  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function shortDate(published) {
    if (!published) return '日期未知';
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(published);
    if (!m) return published;
    const now = new Date();
    const sameYear = String(now.getFullYear()) === m[1];
    return sameYear ? `${Number(m[2])}月${Number(m[3])}日` : `${m[1]}-${m[2]}-${m[3]}`;
  }

  function catClass(category) {
    if (category === '政策公告') return 'tag-policy';
    return 'tag-gov';
  }

  function tagClass(tag) {
    if (tag === '租金') return 'tag-rent';
    if (tag === '公租房' || tag === '住房') return 'tag-housing';
    return 'tag-default';
  }

  function matches(article) {
    if (state.category === '__rent' && !article.is_rent) return false;
    if (state.category && state.category !== '__rent' && article.category !== state.category) return false;
    if (state.tag && !(article.tags || []).includes(state.tag)) return false;
    if (state.query) {
      const haystack = [
        article.title, article.summary, (article.tags || []).join(' '),
        article.category, (article.sources || [article.source]).join(' ')
      ].join(' ').toLowerCase();
      if (!haystack.includes(state.query)) return false;
    }
    return true;
  }

  function filtered() {
    return state.all.filter(matches);
  }

  // ── Render ────────────────────────────────────
  function renderFeed() {
    const list = filtered();
    const visible = list.slice(0, state.visible);

    if (!visible.length) {
      $newsList.innerHTML = '';
      $empty.style.display = 'block';
      $empty.textContent = state.all.length ? '没有符合条件的条目' : '暂无数据';
      $loadMore.style.display = 'none';
      return;
    }
    $empty.style.display = 'none';

    $newsList.innerHTML = visible.map(a => {
      const tags = (a.tags || []).slice(0, 4)
        .map(t => `<span class="news-tag ${tagClass(t)}">${esc(t)}</span>`).join('');
      const summary = a.summary ? `<div class="nh-summary">${esc(a.summary)}</div>` : '';
      const snippets = (a.rent_snippets || []);
      const rentBox = snippets.length ? `
        <div class="nh-rent">
          <div class="nh-rent-label">💰 租金要点</div>
          <ul>${snippets.map(s => `<li>${esc(s)}</li>`).join('')}</ul>
        </div>` : '';
      const atts = (a.attachments || []);
      const attBox = atts.length ? `
        <div class="nh-atts">
          <span class="nh-atts-label">📎 附件</span>
          ${atts.map(f => `<a href="${esc(f.url)}" target="_blank" rel="noopener">${esc(f.name)}</a>`).join('')}
        </div>` : '';
      return `
        <div class="news-item${a.is_rent ? ' is-rent' : ''}">
          <div class="news-meta">
            <span class="news-tag ${catClass(a.category)}">${esc(a.category)}</span>
            ${tags}
            <span class="news-time">${esc(shortDate(a.published))}</span>
          </div>
          <a class="news-title" href="${esc(a.link)}" target="_blank" rel="noopener">${esc(a.title)}</a>
          ${summary}
          ${rentBox}
          ${attBox}
        </div>`;
    }).join('');

    $loadMore.style.display = state.visible < list.length ? 'block' : 'none';
  }

  window.loadMore = function () {
    state.visible += PAGE_SIZE;
    renderFeed();
  };

  // ── Chips ─────────────────────────────────────
  function chip(label, active, onClick) {
    const btn = document.createElement('button');
    btn.className = 'cat-chip' + (active ? ' active' : '');
    btn.textContent = label;
    btn.addEventListener('click', onClick);
    return btn;
  }

  function buildChips() {
    $catBar.innerHTML = '';
    $tagBar.innerHTML = '';
    state.visible = PAGE_SIZE;

    const categories = {};
    state.all.forEach(a => {
      categories[a.category] = (categories[a.category] || 0) + 1;
    });

    $catBar.appendChild(chip('全部', state.category === null, () => {
      state.category = null; buildChips(); renderFeed();
    }));
    $catBar.appendChild(chip(`租金(${state.all.filter(a => a.is_rent).length})`, state.category === '__rent', () => {
      state.category = '__rent'; buildChips(); renderFeed();
    }));
    Object.entries(categories).sort((a, b) => b[1] - a[1]).forEach(([cat, count]) => {
      $catBar.appendChild(chip(`${cat}(${count})`, state.category === cat, () => {
        state.category = cat; buildChips(); renderFeed();
      }));
    });

    const tags = {};
    state.all.forEach(a => (a.tags || []).forEach(t => {
      if (t === '租金') return;   // 已在分类栏中
      tags[t] = (tags[t] || 0) + 1;
    }));

    $tagBar.appendChild(chip('全部标签', state.tag === null, () => {
      state.tag = null; buildChips(); renderFeed();
    }));
    Object.entries(tags).sort((a, b) => b[1] - a[1]).slice(0, 12).forEach(([tag, count]) => {
      $tagBar.appendChild(chip(`${tag}(${count})`, state.tag === tag, () => {
        state.tag = tag; buildChips(); renderFeed();
      }));
    });
  }

  function renderStats(data) {
    document.getElementById('stat-total').textContent = data.total || state.all.length;
    document.getElementById('stat-rent').textContent = data.rent_total || 0;
    const latest = state.all[0];
    document.getElementById('stat-latest').textContent = latest ? shortDate(latest.published) : '--';
  }

  // ── Load ─────────────────────────────────────
  async function loadNews() {
    if (state.loading) return;
    state.loading = true;
    $loading.style.display = 'block';
    try {
      const resp = await fetch(DATA_FILE + '?t=' + Date.now());
      if (!resp.ok) throw new Error('HTTP ' + resp.status);
      const data = await resp.json();
      state.all = data.articles || [];
      state.updated = data.updated;

      if (data.updated && $updateTime) {
        const dt = new Date(data.updated);
        $updateTime.textContent = dt.toLocaleString('zh-CN', {
          month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit'
        }) + ' 更新';
      }

      renderStats(data);
      buildChips();
      renderFeed();
    } catch (e) {
      console.error('load nanhai:', e);
      $newsList.innerHTML = '<div class="empty">加载失败，请刷新页面</div>';
    } finally {
      state.loading = false;
      $loading.style.display = 'none';
    }
  }

  // ── Events ───────────────────────────────────
  let queryTimer = null;
  $query.addEventListener('input', () => {
    clearTimeout(queryTimer);
    queryTimer = setTimeout(() => {
      state.query = $query.value.trim().toLowerCase();
      state.visible = PAGE_SIZE;
      renderFeed();
    }, 150);
  });

  $main.addEventListener('scroll', () => {
    $fab.classList.toggle('show', $main.scrollTop > 200);
    if ($main.scrollTop + $main.clientHeight >= $main.scrollHeight - 150) {
      const list = filtered();
      if (state.visible < list.length) {
        state.visible += PAGE_SIZE;
        renderFeed();
      }
    }
  }, { passive: true });

  window.scrollToTop = function () {
    $main.scrollTo({ top: 0, behavior: 'smooth' });
  };

  setInterval(loadNews, 600000);   // 10 分钟自动刷新

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', loadNews);
  } else {
    loadNews();
  }
})();
