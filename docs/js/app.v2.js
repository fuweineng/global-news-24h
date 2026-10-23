// 全球 24h 新闻 — 中英双语信息流
(function() {
  'use strict';

  const CDN_BASE = '/data/';
  const NEWS_FILE = CDN_BASE + 'news.json';
  const PAGE_SIZE = 30;
  const LANG_KEY = 'news.lang';

  let allArticles = [];
  let visibleCount = PAGE_SIZE;
  let activeCategory = null;
  let loading = false;
  let lang = 'zh';

  const $newsList = document.getElementById('news-list');
  const $loading = document.getElementById('loading');
  const $empty = document.getElementById('empty');
  const $loadMore = document.getElementById('load-more');
  const $main = document.getElementById('main-feed');
  const $fab = document.getElementById('fab');
  const $updateTime = document.getElementById('last-updated');
  const $catBar = document.getElementById('category-bar');
  const $langSwitch = document.getElementById('lang-switch');
  const $footerSources = document.getElementById('footer-sources');

  // ── Helpers ────────────────────────────────────
  function timeAgo(published) {
    if (!published) return '--';
    const dt = new Date(published);
    if (isNaN(dt.getTime())) return '--';
    const diff = Math.floor((Date.now() - dt.getTime()) / 1000);
    if (diff < 0) return '刚刚';
    if (diff < 60) return diff + '秒前';
    if (diff < 3600) return Math.floor(diff / 60) + '分钟前';
    if (diff < 86400) return Math.floor(diff / 3600) + '小时前';
    return Math.floor(diff / 86400) + '天前';
  }

  // 含 2 个以上汉字即视为已有中文标题
  // （中英混排标题里英文品牌名很长，按占比判定会把正常译文误判为未翻译）
  function isChinese(s) {
    if (!s || typeof s !== 'string') return false;
    let cjk = 0;
    for (let i = 0; i < s.length; i++) {
      const code = s.charCodeAt(i);
      if (code >= 0x4e00 && code <= 0x9fff && ++cjk >= 2) return true;
    }
    return false;
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
      const origTitle = art.title || art.zh_title || '';
      let titleHtml;
      let summaryHtml = '';

      if (lang === 'en') {
        titleHtml = esc(origTitle || '--');
      } else if (isChinese(art.zh_title)) {
        titleHtml = esc(art.zh_title);
      } else {
        // 无可用中文标题：如实展示原文，并标注 ·EN
        titleHtml = esc(origTitle || '--') +
          '<span class="lang-fallback" title="该条暂无中文译文">·EN</span>';
      }

      if (lang === 'zh' && isChinese(art.zh_summary)) {
        summaryHtml = `<div class="news-summary">${esc(art.zh_summary)}</div>`;
      }

      return `
        <a class="news-item" href="${esc(art.link)}" target="_blank" rel="noopener">
          <div class="news-meta">
            <span class="news-tag ${tagClass(art.category)}">${tagLabel(art.category)}</span>
            <span class="news-source">${esc(art.source)}</span>
            <span class="news-time">${timeAgo(art.published)}</span>
          </div>
          <div class="news-title">${titleHtml}</div>
          ${summaryHtml}
        </a>
      `;
    }).join('');

    $loadMore.style.display = visibleCount < sorted.length ? 'block' : 'none';
  }

  // ── Language switch ──────────────────────────
  function readLang() {
    try {
      const saved = localStorage.getItem(LANG_KEY);
      if (saved === 'zh' || saved === 'en') return saved;
    } catch (e) { /* 隐私模式等场景忽略 */ }
    return 'zh';
  }

  function saveLang(value) {
    try { localStorage.setItem(LANG_KEY, value); } catch (e) { /* 忽略 */ }
  }

  function updateLangButtons() {
    if (!$langSwitch) return;
    $langSwitch.querySelectorAll('.lang-btn').forEach(btn => {
      const active = btn.dataset.lang === lang;
      btn.classList.toggle('active', active);
      btn.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
  }

  function setLang(value) {
    if (value !== 'zh' && value !== 'en') return;
    lang = value;
    saveLang(value);
    updateLangButtons();
    renderFeed(); // 复用当前分类与 visibleCount，不重新请求
  }

  function initLangSwitch() {
    if (!$langSwitch) return;
    $langSwitch.querySelectorAll('.lang-btn').forEach(btn => {
      btn.addEventListener('click', () => setLang(btn.dataset.lang));
    });
    updateLangButtons();
  }

  // ── Footer sources ───────────────────────────
  function updateFooterSources() {
    if (!$footerSources) return;
    const counts = {};
    allArticles.forEach(art => {
      const name = (art.source || '').trim();
      if (name) counts[name] = (counts[name] || 0) + 1;
    });
    const names = Object.keys(counts).sort((a, b) => counts[b] - counts[a]);
    if (!allArticles.length || names.length === 0) {
      $footerSources.textContent = '数据来源: --';
      return;
    }
    $footerSources.textContent = '数据来源: ' +
      names.slice(0, 8).join(' · ') + ' 等 ' + names.length + ' 家';
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

    // 刷新数据后重建，避免重复追加；保留当前筛选
    $catBar.innerHTML = '';
    if (activeCategory && !cats[activeCategory]) activeCategory = null;

    // "全部" chip
    const allChip = document.createElement('button');
    allChip.className = 'cat-chip' + (activeCategory ? '' : ' active');
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
      chip.className = 'cat-chip' + (activeCategory === cat ? ' active' : '');
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
      updateFooterSources();
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
  lang = readLang();
  initLangSwitch();

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', loadNews);
  } else {
    loadNews();
  }
})();
