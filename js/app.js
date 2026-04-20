// global-news-24h — Readhub 风格前端
(function() {
  'use strict';

  const CDN_BASE = 'https://cdn.jsdelivr.net/gh/fuweineng/global-news-24h@main/data/';
  const NEWS_FILE = CDN_BASE + 'news.json';
  const REFRESH_MS = 30 * 60 * 1000; // 30分钟刷新

  let articles = [];
  let currentTab = 'hot';
  let loading = false;

  // DOM refs
  const $newsList = document.getElementById('news-list');
  const $loading = document.getElementById('loading');
  const $empty = document.getElementById('empty');

  // ── Helpers ────────────────────────────────────────────
  function timeAgo(published) {
    try {
      const dt = new Date(published);
      const now = new Date();
      const diff = Math.floor((now - dt) / 1000);
      if (diff < 60) return diff + '秒前';
      if (diff < 3600) return Math.floor(diff / 60) + '分钟前';
      if (diff < 86400) return Math.floor(diff / 3600) + '小时前';
      return Math.floor(diff / 86400) + '天前';
    } catch { return ''; }
  }

  function categoryTag(cat) {
    const map = {
      world: '🌍', politics: '🏛️', business: '💹', technology: '🖥️',
      science: '🔬', health: '🏥', sports: '⚽', entertainment: '🎬',
      ai: '🤖', llm: '🤖', robot: '🤖', chip: '💾', tool: '🛠️'
    };
    return map[cat] || '📰';
  }

  // ── Render ────────────────────────────────────────────
  function renderFeed() {
    if (articles.length === 0) {
      $newsList.innerHTML = '';
      $empty.style.display = 'block';
      return;
    }
    $empty.style.display = 'none';

    const sorted = [...articles].reverse(); // newest first
    $newsList.innerHTML = sorted.map(art => `
      <div class="news-item" onclick="window.open('${art.link}', '_blank')">
        <div class="news-meta">
          <span class="news-tag">${categoryTag(art.category)}</span>
          <span class="news-time">${timeAgo(art.published)}</span>
        </div>
        <div class="news-title">${esc(art.title)}</div>
        <div class="news-source">${esc(art.source)}</div>
      </div>
    `).join('');
  }

  function esc(s) {
    return String(s || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // ── Load ──────────────────────────────────────────────
  async function loadNews() {
    if (loading) return;
    loading = true;
    $loading.style.display = 'block';
    try {
      const resp = await fetch(NEWS_FILE + '?t=' + Date.now());
      if (!resp.ok) throw new Error(resp.status);
      const data = await resp.json();
      articles = data.articles || [];
      renderFeed();
    } catch (e) {
      console.error('loadNews failed:', e);
      $newsList.innerHTML = '<div class="empty">加载失败，请稍后刷新</div>';
    } finally {
      loading = false;
      $loading.style.display = 'none';
    }
  }

  // ── Nav ──────────────────────────────────────────────
  document.getElementById('nav-inner').addEventListener('click', e => {
    const tab = e.target.closest('.nav-item');
    if (!tab) return;
    document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
    tab.classList.add('active');
    currentTab = tab.dataset.tab;
    // 实际按 tab 过滤（这里简化处理，全量展示）
    renderFeed();
  });

  // ── Scroll to top ────────────────────────────────────
  window.scrollToTop = function() {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  // ── FAB visibility ────────────────────────────────────
  window.addEventListener('scroll', () => {
    const fab = document.getElementById('fab');
    fab.style.opacity = window.scrollY > 300 ? '1' : '0';
  }, { passive: true });

  // ── Boot ─────────────────────────────────────────────
  loadNews();
  setInterval(loadNews, REFRESH_MS);
})();
