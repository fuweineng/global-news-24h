// 全球 24h 新闻 — 中文优先信息流
(function() {
  'use strict';

  const CDN_BASE = 'https://cdn.jsdelivr.net/gh/fuweineng/global-news-24h@main/data/';
  const NEWS_FILE = CDN_BASE + 'news.json';
  const PAGE_SIZE = 30;

  let allArticles = [];
  let visibleCount = PAGE_SIZE;
  let activeCategory = null;
  let loading = false;

  const $newsList = document.getElementById('news-list');
  const $loading = document.getElementById('loading');
  const $empty = document.getElementById('empty');
  const $loadMore = document.getElementById('load-more');
  const $main = document.getElementById('main-feed');
  const $fab = document.getElementById('fab');
  const $updateTime = document.getElementById('last-updated');
  const $catBar = document.getElementById('category-bar');

  // ── Helpers ────────────────────────────────────
  function timeAgo(published) {
    try {
      const dt = new Date(published);
      const now = new Date();
      const diff = Math.floor((now - dt) / 1000);
      if (diff < 60) return diff + '秒前';
      if (diff < 3600) return Math.floor(diff / 60) + '分钟前';
      if (diff < 86400) return Math.floor(diff / 3600) + '小时前';
      const days = Math.floor(diff / 86400);
      return days + '天前';
    } catch { return ''; }
  }

  function tagClass(cat) {
    const map = {
      world: 'tag-world', politics: 'tag-politics',
      business: 'tag-business', finance: 'tag-finance',
      technology: 'tag-technology', science: 'tag-science',
      health: 'tag-health', sports: 'tag-sports',
      entertainment: 'tag-entertainment', asia: 'tag-asia'
    };
    return map[cat] || 'tag-default';
  }

  function tagLabel(cat) {
    const map = {
      world: '国际', politics: '政治', business: '商业',
      finance: '财经', technology: '科技', science: '科学',
      health: '健康', sports: '体育', entertainment: '娱乐',
      asia: '亚洲', china: '中国', europe: '欧洲',
      startups: '创业'
    };
    return map[cat] || cat;
  }

  function esc(s) {
    return String(s || '')
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function getFiltered() {
    let list = [...allArticles];
    if (activeCategory) {
      list = list.filter(a => a.category === activeCategory);
    }
    return list.reverse(); // newest first
  }

  // ── Render ────────────────────────────────────
  function renderFeed() {
    const sorted = getFiltered();
    const visible = sorted.slice(0, visibleCount);

    if (visible.length === 0) {
      $newsList.innerHTML = '';
      $empty.style.display = 'block';
      $loadMore.style.display = 'none';
      return;
    }
    $empty.style.display = 'none';

    $newsList.innerHTML = visible.map(art => {
      const title = art.zh_title || art.one_line || art.title;
      const orig = art.title !== title ? art.title : '';
      return `
        <a class="news-item" href="${esc(art.link)}" target="_blank" rel="noopener">
          <div class="news-meta">
            <span class="news-tag ${tagClass(art.category)}">${tagLabel(art.category)}</span>
            <span class="news-source">${esc(art.source)}</span>
            <span class="news-time">${timeAgo(art.published)}</span>
          </div>
          <div class="news-title">${esc(title)}</div>
        </a>
      `;
    }).join('');

    $loadMore.style.display = visibleCount < sorted.length ? 'block' : 'none';
  }

  window.loadMore = function() {
    visibleCount += PAGE_SIZE;
    renderFeed();
  };

  // ── Category filter ──────────────────────────
  function initCategories() {
    const cats = {};
    allArticles.forEach(a => {
      const c = a.category || 'world';
      cats[c] = (cats[c] || 0) + 1;
    });
    const entries = Object.entries(cats).sort((a, b) => b[1] - a[1]);

    // "全部" chip
    const allChip = document.createElement('button');
    allChip.className = 'cat-chip active';
    allChip.textContent = '全部';
    allChip.dataset.cat = '';
    allChip.addEventListener('click', () => {
      document.querySelectorAll('.cat-chip').forEach(el => el.classList.remove('active'));
      allChip.classList.add('active');
      activeCategory = null;
      visibleCount = PAGE_SIZE;
      renderFeed();
    });
    $catBar.appendChild(allChip);

    entries.forEach(([cat, count]) => {
      const chip = document.createElement('button');
      chip.className = 'cat-chip';
      chip.textContent = `${tagLabel(cat)}(${count})`;
      chip.dataset.cat = cat;
      chip.addEventListener('click', () => {
        document.querySelectorAll('.cat-chip').forEach(el => el.classList.remove('active'));
        chip.classList.add('active');
        activeCategory = cat;
        visibleCount = PAGE_SIZE;
        renderFeed();
      });
      $catBar.appendChild(chip);
    });
  }

  // ── Load ─────────────────────────────────────
  async function loadNews() {
    if (loading) return;
    loading = true;
    $loading.style.display = 'block';
    try {
      const resp = await fetch(NEWS_FILE + '?t=' + Date.now());
      if (!resp.ok) throw new Error('HTTP ' + resp.status);
      const data = await resp.json();
      allArticles = data.articles || [];
      visibleCount = PAGE_SIZE;

      // Update time
      if (data.updated && $updateTime) {
        try {
          const dt = new Date(data.updated);
          $updateTime.textContent = dt.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) + ' 更新';
        } catch { $updateTime.textContent = '--:-- 更新'; }
      }

      initCategories();
      renderFeed();
    } catch (e) {
      console.error('loadNews:', e);
      $newsList.innerHTML = '<div class="empty">加载失败，请刷新页面</div>';
    } finally {
      loading = false;
      $loading.style.display = 'none';
    }
  }

  // ── Scroll → FAB + auto load more ──────────
  $main.addEventListener('scroll', () => {
    $fab.classList.toggle('show', $main.scrollTop > 200);

    if ($main.scrollTop + $main.clientHeight >= $main.scrollHeight - 150) {
      const sorted = getFiltered();
      if (visibleCount < sorted.length) {
        visibleCount += PAGE_SIZE;
        renderFeed();
      }
    }
  }, { passive: true });

  window.scrollToTop = function() {
    $main.scrollTo({ top: 0, behavior: 'smooth' });
  };

  // ── Auto refresh every 5 min ───────────────
  setInterval(() => { loadNews(); }, 300000);

  // ── Boot ───────────────────────────────────
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', loadNews);
  } else {
    loadNews();
  }
})();
