// global-news-24h — Readhub 风格前端
(function() {
  'use strict';

  const CDN_BASE = 'https://cdn.jsdelivr.net/gh/fuweineng/global-news-24h@main/data/';
  const NEWS_FILE = CDN_BASE + 'news.json';
  const PAGE_SIZE = 30;

  let allArticles = [];
  let visibleCount = PAGE_SIZE;
  let loading = false;

  // DOM refs
  const $newsList = document.getElementById('news-list');
  const $loading = document.getElementById('loading');
  const $empty = document.getElementById('empty');
  const $loadMore = document.getElementById('load-more');
  const $main = document.getElementById('main-feed');
  const $fab = document.getElementById('fab');

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

  function esc(s) {
    return String(s || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // ── Render ────────────────────────────────────────────
  function renderFeed() {
    const sorted = [...allArticles].reverse(); // newest first
    const visible = sorted.slice(0, visibleCount);

    if (visible.length === 0) {
      $newsList.innerHTML = '';
      $empty.style.display = 'block';
      $loadMore.style.display = 'none';
      return;
    }
    $empty.style.display = 'none';

    $newsList.innerHTML = visible.map(art => `
      <div class="news-item" onclick="window.open('${art.link}', '_blank')">
        <div class="news-meta">
          <span class="news-tag">${categoryTag(art.category)}</span>
          <span class="news-time">${timeAgo(art.published)}</span>
        </div>
        <div class="news-title">${esc(art.title)}</div>
        <div class="news-source">${esc(art.source)}</div>
      </div>
    `).join('');

    // Show load-more if there are more
    $loadMore.style.display = visibleCount < sorted.length ? 'block' : 'none';
  }

  // ── Load more ────────────────────────────────────────────
  window.loadMore = function() {
    visibleCount += PAGE_SIZE;
    renderFeed();
  };

  // ── Load ──────────────────────────────────────────────
  async function loadNews() {
    if (loading) return;
    loading = true;
    $loading.style.display = 'block';
    try {
      const resp = await fetch(NEWS_FILE + '?t=' + Date.now());
      if (!resp.ok) throw new Error(resp.status);
      const data = await resp.json();
      allArticles = data.articles || [];
      visibleCount = PAGE_SIZE;
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
  });

  // ── Scroll → FAB ────────────────────────────────────
  $main.addEventListener('scroll', () => {
    $fab.classList.toggle('show', $main.scrollTop > 200);
  }, { passive: true });

  // ── Scroll → auto load more ─────────────────────────
  $main.addEventListener('scroll', () => {
    if ($main.scrollTop + $main.clientHeight >= $main.scrollHeight - 100) {
      const sorted = [...allArticles].reverse();
      if (visibleCount < sorted.length) {
        visibleCount += PAGE_SIZE;
        renderFeed();
      }
    }
  }, { passive: true });

  // ── Scroll to top ────────────────────────────────────
  window.scrollToTop = function() {
    $main.scrollTo({ top: 0, behavior: 'smooth' });
  };

  // ── Boot ─────────────────────────────────────────────
  loadNews();
})();
