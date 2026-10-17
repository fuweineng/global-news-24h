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

// ════════════════════════════════════════════════════
// 分析视图：情绪 / 事实类型 / 价格 / 关键词（纯 SVG 手绘）
// ════════════════════════════════════════════════════
(function () {
  'use strict';

  const DATA_FILE = '/data/analysis.json';
  const COL = { 正: '#34c759', 中: '#aeaeb2', 负: '#ff3b30', fact: '#0066cc', word: '#7b1fa2', price: '#f97316' };

  const state = { data: null, loading: false, loaded: false, ym: 'all' };

  const $app = document.getElementById('app');
  const $analysis = document.getElementById('nh-analysis');
  const $ym = document.getElementById('nh-ym');
  const $updated = document.getElementById('nh-ana-updated');
  const $loading = document.getElementById('nh-ana-loading');
  const $empty = document.getElementById('nh-ana-empty');
  const $body = document.getElementById('nh-ana-body');
  const $drill = document.getElementById('nh-drill');
  const $drillTitle = document.getElementById('nh-drill-title');
  const $drillBody = document.getElementById('nh-drill-body');
  const $priceCard = document.getElementById('nh-card-price');

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function widthOf(el) { return Math.max(el.clientWidth || 0, 280); }

  // ── 数据加载 ─────────────────────────────────
  async function loadAnalysis() {
    if (state.loading || state.loaded) return;
    state.loading = true;
    $loading.style.display = 'block';
    try {
      const resp = await fetch(DATA_FILE + '?t=' + Date.now());
      if (!resp.ok) throw new Error('HTTP ' + resp.status);
      state.data = await resp.json();
      state.loaded = true;
      $loading.style.display = 'none';
      $empty.style.display = 'none';
      $body.style.display = 'block';
      if (state.data.updated) {
        const dt = new Date(state.data.updated);
        const txt = isNaN(dt) ? state.data.updated : dt.toLocaleString('zh-CN', {
          year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit'
        });
        $updated.textContent = '数据更新 ' + txt;
      }
      buildYmSelect();
      renderAll();
    } catch (e) {
      console.error('load analysis:', e);
      $loading.style.display = 'none';
      $empty.style.display = 'block';
      $body.style.display = 'none';
    } finally {
      state.loading = false;
    }
  }

  function buildYmSelect() {
    const byYm = state.data.by_ym || {};
    const years = [...new Set(Object.keys(byYm).map(k => k.slice(0, 4)))].sort();
    let html = '<option value="all">全部时间</option>';
    years.forEach(y => {
      const months = Object.keys(byYm).filter(k => k.slice(0, 4) === y && k.length > 4).sort();
      html += `<optgroup label="${esc(y)}年">`;
      if (byYm[y] != null) html += `<option value="${esc(y)}">${esc(y)}年（未标注月）</option>`;
      months.forEach(k => {
        html += `<option value="${esc(k)}">${esc(y)}年${Number(k.slice(5))}月</option>`;
      });
      html += '</optgroup>';
    });
    $ym.innerHTML = html;
    $ym.value = state.ym;
  }

  // ── 过滤 ─────────────────────────────────────
  function ymOf(a) {
    if (!a.year) return null;
    return a.month ? `${a.year}-${String(a.month).padStart(2, '0')}` : String(a.year);
  }

  function filtered() {
    const arts = (state.data.articles || []);
    if (state.ym === 'all') return arts;
    return arts.filter(a => {
      if (state.ym.length === 4) return String(a.year) === state.ym;
      return ymOf(a) === state.ym;
    });
  }

  // ── 图表工具 ─────────────────────────────────
  function factCounts(arts) {
    const m = {};
    arts.forEach(a => { m[a.fact_type] = (m[a.fact_type] || 0) + 1; });
    return Object.entries(m).sort((x, y) => y[1] - x[1]);
  }

  function sentimentByYm(arts) {
    const m = {};
    arts.forEach(a => {
      const k = ymOf(a);
      if (!k) return;
      const b = m[k] || (m[k] = { 正: 0, 中: 0, 负: 0 });
      b[a.sentiment] = (b[a.sentiment] || 0) + 1;
    });
    return m;
  }

  const STOP = new Set('的了和在与及等是为将对以其并或可要不到上下这那有个我你他她它们一二三四五六七八九十百千万亿年月日时分秒第批次号区街镇村组关于工作项目中国广东佛山南海进行以及有关相关目前已经通过进一步'.split(''));

  function keywords(arts, limit) {
    const grams = {};
    arts.forEach(a => {
      const text = (a.title || '') + ' ' + (a.title || '') + ' ' + (a.summary || '');
      (text.match(/[\u4e00-\u9fff]{2,}/g) || []).forEach(run => {
        for (let n = 2; n <= 4 && n <= run.length; n++) {
          for (let i = 0; i + n <= run.length; i++) {
            const g = run.slice(i, i + n);
            let bad = false;
            for (const c of g) { if (STOP.has(c)) { bad = true; break; } }
            if (!bad) grams[g] = (grams[g] || 0) + 1;
          }
        }
      });
    });
    const keys = Object.keys(grams);
    const maxSup = {};
    keys.forEach(g => {
      const c = grams[g], n = g.length;
      for (let i = 0; i < n; i++) {
        for (let j = i + 2; j <= n; j++) {
          if (i === 0 && j === n) continue;
          const sub = g.slice(i, j);
          if (maxSup[sub] == null || c > maxSup[sub]) maxSup[sub] = c;
        }
      }
    });
    return keys
      .filter(g => grams[g] >= 2 && (maxSup[g] || 0) < 0.55 * grams[g])
      .sort((a, b) => grams[b] - grams[a] || b.length - a.length)
      .slice(0, limit)
      .map(g => [g, grams[g]]);
  }

  // ── 渲染 ─────────────────────────────────────
  function renderAll() {
    if (!state.data) return;
    const arts = filtered();
    renderSentiment(arts);
    renderFact(arts);
    renderPrice(arts);
    renderWords(arts);
  }

  function renderSentiment(arts) {
    const el = document.getElementById('nh-chart-sentiment');
    const byYm = sentimentByYm(arts);
    const keys = Object.keys(byYm).sort();
    if (!keys.length) { el.innerHTML = '<div class="nh-none">该时间范围暂无数据</div>'; return; }

    const W = widthOf(el), padL = 26, padR = 6, padT = 10, padB = 26;
    const H = 170, plotH = H - padT - padB, plotW = W - padL - padR;
    const max = Math.max(1, ...keys.map(k => byYm[k].正 + byYm[k].中 + byYm[k].负));
    const bw = plotW / keys.length;
    const barW = Math.max(3, Math.min(bw * 0.7, 34));
    const tickEvery = Math.ceil(keys.length / 8);

    let s = `<svg viewBox="0 0 ${W} ${H}" role="img">`;
    // 基线与 y 刻度
    for (let t = 0; t <= 2; t++) {
      const y = padT + plotH - (plotH * t / 2);
      s += `<line class="axis" x1="${padL}" y1="${y.toFixed(1)}" x2="${W - padR}" y2="${y.toFixed(1)}"/>`;
      s += `<text x="${padL - 4}" y="${(y + 3).toFixed(1)}" text-anchor="end">${Math.round(max * t / 2)}</text>`;
    }
    keys.forEach((k, i) => {
      const b = byYm[k];
      const x = padL + i * bw + (bw - barW) / 2;
      let y = padT + plotH;
      [['负', COL.负], ['中', COL.中], ['正', COL.正]].forEach(([name, color]) => {
        const c = b[name] || 0;
        if (!c) return;
        const h = plotH * c / max;
        y -= h;
        s += `<rect class="hit" data-ym="${esc(k)}" data-sent="${name}" x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${barW.toFixed(1)}" height="${h.toFixed(1)}" fill="${color}" rx="1"><title>${esc(k)} · ${name} ${c} 条</title></rect>`;
      });
      if (i % tickEvery === 0 || i === keys.length - 1) {
        const lbl = k.length > 4 ? k.slice(2).replace('-', '/') : k.slice(2);
        s += `<text x="${(x + barW / 2).toFixed(1)}" y="${H - 8}" text-anchor="middle">${esc(lbl)}</text>`;
      }
    });
    s += '</svg>';
    el.innerHTML = s;
  }

  function renderFact(arts) {
    const el = document.getElementById('nh-chart-fact');
    const rows = factCounts(arts);
    if (!rows.length) { el.innerHTML = '<div class="nh-none">暂无数据</div>'; return; }
    const W = widthOf(el), rowH = 24, labelW = 68, padR = 34;
    const H = rows.length * rowH + 6;
    const max = Math.max(1, ...rows.map(r => r[1]));
    const barMax = W - labelW - padR;
    let s = `<svg viewBox="0 0 ${W} ${H}" role="img">`;
    rows.forEach(([name, count], i) => {
      const y = i * rowH + 4;
      const w = Math.max(2, barMax * count / max);
      s += `<text class="bar-label" x="0" y="${y + 13}">${esc(name)}</text>`;
      s += `<rect class="hit" data-fact="${esc(name)}" x="${labelW}" y="${y}" width="${w.toFixed(1)}" height="16" fill="${COL.fact}" rx="3"><title>${esc(name)} ${count} 条</title></rect>`;
      s += `<text class="bar-value" x="${(labelW + w + 5).toFixed(1)}" y="${y + 13}">${count}</text>`;
    });
    s += '</svg>';
    el.innerHTML = s;
  }

  function renderPrice(arts) {
    const series = (state.data.price_series || []).filter(p => inRange(p.period));
    const el = document.getElementById('nh-chart-price');
    if (!series.length) { $priceCard.style.display = 'none'; return; }
    $priceCard.style.display = '';
    const W = widthOf(el), padL = 40, padR = 14, padT = 12, padB = 28;
    const H = 180, plotH = H - padT - padB, plotW = W - padL - padR;
    const vals = series.map(p => p.value);
    const max = Math.max(...vals), min = Math.min(...vals);
    const span = max - min || 1;
    const xAt = i => padL + (series.length === 1 ? plotW / 2 : plotW * i / (series.length - 1));
    const yAt = v => padT + plotH - plotH * (v - min) / span;
    let s = `<svg viewBox="0 0 ${W} ${H}" role="img">`;
    s += `<line class="axis" x1="${padL}" y1="${padT + plotH}" x2="${W - padR}" y2="${padT + plotH}"/>`;
    s += `<text x="${padL - 4}" y="${padT + 8}" text-anchor="end">${max}</text>`;
    s += `<text x="${padL - 4}" y="${padT + plotH}" text-anchor="end">${min}</text>`;
    const pts = series.map((p, i) => `${xAt(i).toFixed(1)},${yAt(p.value).toFixed(1)}`).join(' ');
    if (series.length > 1) s += `<polyline points="${pts}" fill="none" stroke="${COL.price}" stroke-width="2"/>`;
    series.forEach((p, i) => {
      s += `<circle class="hit" data-price="${i}" cx="${xAt(i).toFixed(1)}" cy="${yAt(p.value).toFixed(1)}" r="4" fill="${COL.price}" data-link="${esc(p.link)}" data-title="${esc(p.title)}"><title>${esc(p.period)} · ${p.value}${esc(p.unit)} · ${esc(p.title)}</title></circle>`;
      if (i % Math.ceil(series.length / 6) === 0) {
        s += `<text x="${xAt(i).toFixed(1)}" y="${H - 8}" text-anchor="middle">${esc(p.period)}</text>`;
      }
    });
    s += '</svg>';
    el.innerHTML = s;
  }

  function renderWords(arts) {
    const el = document.getElementById('nh-chart-words');
    const rows = keywords(arts, 10);
    if (!rows.length) { el.innerHTML = '<div class="nh-none">暂无数据</div>'; return; }
    const W = widthOf(el), rowH = 24, labelW = 84, padR = 34;
    const H = rows.length * rowH + 6;
    const max = Math.max(1, ...rows.map(r => r[1]));
    const barMax = W - labelW - padR;
    let s = `<svg viewBox="0 0 ${W} ${H}" role="img">`;
    rows.forEach(([word, count], i) => {
      const y = i * rowH + 4;
      const w = Math.max(2, barMax * count / max);
      s += `<text class="bar-label" x="0" y="${y + 13}">${esc(word)}</text>`;
      s += `<rect class="hit" data-word="${esc(word)}" x="${labelW}" y="${y}" width="${w.toFixed(1)}" height="16" fill="${COL.word}" rx="3"><title>${esc(word)} ${count} 次</title></rect>`;
      s += `<text class="bar-value" x="${(labelW + w + 5).toFixed(1)}" y="${y + 13}">${count}</text>`;
    });
    s += '</svg>';
    el.innerHTML = s;
  }

  function inRange(period) {
    if (state.ym === 'all') return true;
    if (!period) return false;
    if (state.ym.length === 4) return String(period).slice(0, 4) === state.ym;
    return period === state.ym;
  }

  // ── 下钻 ─────────────────────────────────────
  function drill(title, items) {
    if (!items.length) return;
    $drillTitle.textContent = `${title}（${items.length}）`;
    $drillBody.innerHTML = items.map(a => `
      <a href="${esc(a.link || '#')}" target="_blank" rel="noopener">
        <span class="nh-drill-meta">${esc(a.published || '')}</span>${esc(a.title)}
      </a>`).join('');
    $drill.style.display = 'block';
    $drill.scrollIntoView({ block: 'nearest' });
  }

  window.nhCloseDrill = function () { $drill.style.display = 'none'; };

  const $chartWrap = $body;
  $chartWrap.addEventListener('click', e => {
    const hit = e.target.closest('.hit');
    if (!hit) return;
    const arts = filtered();
    if (hit.dataset.price != null) {
      const link = hit.dataset.link;
      if (link) window.open(link, '_blank', 'noopener');
      return;
    }
    if (hit.dataset.ym) {
      const { ym, sent } = hit.dataset;
      drill(`${ym} · ${sent}`, arts.filter(a => ymOf(a) === ym && a.sentiment === sent));
    } else if (hit.dataset.fact) {
      const fa = hit.dataset.fact;
      drill(`事实类型：${fa}`, arts.filter(a => a.fact_type === fa));
    } else if (hit.dataset.word) {
      const w = hit.dataset.word;
      drill(`关键词：${w}`, arts.filter(a => (a.title || '').includes(w) || (a.summary || '').includes(w)));
    }
  });

  $ym.addEventListener('change', () => {
    state.ym = $ym.value;
    window.nhCloseDrill();
    renderAll();
  });

  // ── 视图切换 ─────────────────────────────────
  window.nhSetView = function (view) {
    document.querySelectorAll('.nh-view-btn').forEach(b => {
      b.classList.toggle('active', b.dataset.view === view);
    });
    const isAnalyze = view === 'analyze';
    const isDigest = view === 'digest';
    const main = document.getElementById('main-feed');
    const $digest = document.getElementById('nh-digest');

    $app.classList.toggle('mode-analyze', isAnalyze);
    $app.classList.toggle('mode-digest', isDigest);
    $analysis.style.display = isAnalyze ? 'block' : 'none';
    if ($digest) $digest.style.display = isDigest ? 'block' : 'none';

    if (isAnalyze) {
      loadAnalysis().then(() => renderAll());
    } else if (isDigest) {
      if (window.nhLoadDigest) window.nhLoadDigest();
    }
    if ((isAnalyze || isDigest) && main) main.scrollTo({ top: 0 });
  };

  let resizeTimer = null;
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      if ($app.classList.contains('mode-analyze')) renderAll();
    }, 200);
  });
})();

// ════════════════════════════════════════════════════
// AI 解读视图：多期聚合解读（日 / 周 / 月 / 年）
// 每期含 综述 / 分行业要点 / 行动建议 / 关注信号 / 依据
// ════════════════════════════════════════════════════
(function () {
  'use strict';

  const DATA_FILE = '/data/ai_digest.json';
  const PERIOD_LABEL = { day: '日', week: '周', month: '月', year: '年' };
  const DEFAULT_CHAIN = ['week', 'month', 'year', 'day'];

  const state = { loading: false, loaded: false, data: null, period: 'week' };

  const $loading = document.getElementById('nh-digest-loading');
  const $empty = document.getElementById('nh-digest-empty');
  const $body = document.getElementById('nh-digest-body');
  const $meta = document.getElementById('nh-digest-meta');
  const $title = document.getElementById('nh-digest-title');
  const $disclaimer = document.getElementById('nh-digest-disclaimer');
  const $tabs = document.getElementById('nh-digest-tabs');

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function fmtTime(s) {
    if (!s) return '';
    const dt = new Date(s);
    if (isNaN(dt)) return s;
    return dt.toLocaleString('zh-CN', {
      year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit'
    });
  }

  function renderEvidence(ev) {
    const items = (ev || []).filter(e => e && (e.title || e.link));
    if (!items.length) return '';
    const lis = items.map(e => {
      const title = esc(e.title || e.link);
      return e.link
        ? `<li><a href="${esc(e.link)}" target="_blank" rel="noopener">${title}</a></li>`
        : `<li>${title}</li>`;
    }).join('');
    return `
      <div class="nh-insight-block">
        <div class="nh-insight-label">依据</div>
        <ul class="nh-insight-evidence">${lis}</ul>
      </div>`;
  }

  function renderSectors(sectors) {
    const items = (sectors || []).filter(s => s && (s.name || s.point));
    if (!items.length) return '';
    const lis = items.map(s => {
      const name = s.name ? `<strong class="nh-sector-name">${esc(s.name)}</strong>` : '';
      return `<li>${name}${esc(s.point || '')}</li>`;
    }).join('');
    return `
      <div class="nh-insight-block">
        <div class="nh-insight-label">分行业要点</div>
        <ul class="nh-sector-list">${lis}</ul>
      </div>`;
  }

  function renderList(label, items, cls) {
    const list = (items || []).filter(Boolean);
    if (!list.length) return '';
    return `
      <div class="nh-insight-block">
        <div class="nh-insight-label">${esc(label)}</div>
        <ul class="${cls}">${list.map(x => `<li>${esc(x)}</li>`).join('')}</ul>
      </div>`;
  }

  function renderPeriod(period) {
    const label = PERIOD_LABEL[state.period] || '';
    const head = `
      <div class="nh-period-head">
        <span class="nh-period-badge">${esc(label)}报</span>
        <span class="nh-period-range">${esc(period.range || '')}</span>
        <span class="nh-period-count">${period.count || 0} 条</span>
      </div>`;

    if (!period.count) {
      return `<div class="nh-period">${head}<div class="nh-period-empty">本期无更新</div></div>`;
    }

    const overview = period.overview ? `
      <div class="nh-insight-block">
        <div class="nh-insight-label">本期综述</div>
        <div class="nh-insight-text">${esc(period.overview)}</div>
      </div>` : '';

    return `
      <div class="nh-period">${head}
        <article class="nh-insight">
          ${overview}
          ${renderSectors(period.sectors)}
          ${renderList('行动建议', period.actions, 'nh-insight-actions')}
          ${renderList('值得关注的信号', period.signals, 'nh-signal-list')}
          ${renderEvidence(period.evidence)}
        </article>
      </div>`;
  }

  function setActiveTab() {
    if (!$tabs) return;
    $tabs.querySelectorAll('.nh-digest-tab').forEach(b => {
      b.classList.toggle('active', b.dataset.period === state.period);
    });
  }

  function render() {
    setActiveTab();
    const d = state.data || {};
    const periods = d.periods || {};
    const period = periods[state.period] || { count: 0, range: '' };

    if ($title) $title.textContent = `🤖 AI ${PERIOD_LABEL[state.period] || ''}度解读`;

    const meta = [];
    if (period.range) meta.push(period.range);
    if (period.count) meta.push(`${period.count} 条`);
    if (d.model) meta.push(`模型 ${d.model}`);
    if (d.generated_at) meta.push(`生成于 ${fmtTime(d.generated_at)}`);
    $meta.textContent = meta.join(' · ');

    $empty.style.display = 'none';
    $loading.style.display = 'none';
    $body.innerHTML = renderPeriod(period);
    $body.style.display = 'block';
    $disclaimer.textContent = '⚠️ ' + (d.disclaimer || '本解读由 AI 自动生成，仅供参考，不代表政府立场');
    $disclaimer.style.display = 'block';
  }

  window.nhSetDigestPeriod = function (p) {
    if (!PERIOD_LABEL[p]) return;
    state.period = p;
    if (state.data) render();
    else setActiveTab();
  };

  function pickDefaultPeriod(periods) {
    for (const p of DEFAULT_CHAIN) {
      if (periods[p] && periods[p].count) return p;
    }
    return 'week';
  }

  async function loadDigest() {
    if (state.loaded || state.loading) return;
    state.loading = true;
    $loading.style.display = 'block';
    $empty.style.display = 'none';
    try {
      const resp = await fetch(DATA_FILE + '?t=' + Date.now());
      if (!resp.ok) throw new Error('HTTP ' + resp.status);
      state.data = await resp.json();
      state.loaded = true;
      state.period = pickDefaultPeriod(state.data.periods || {});
      $loading.style.display = 'none';
      render();
    } catch (e) {
      console.error('load ai_digest:', e);
      setActiveTab();
      $loading.style.display = 'none';
      $body.style.display = 'none';
      $disclaimer.style.display = 'none';
      $empty.style.display = 'block';
    } finally {
      state.loading = false;
    }
  }

  window.nhLoadDigest = loadDigest;
})();
