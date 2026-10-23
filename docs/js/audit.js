// news 审计 — 内容中立化质量
// 读取 data/audit.json 并渲染审计项、按源覆盖率、中立度命中与诚实性。
(function () {
  'use strict';

  var DATA_URL = 'data/audit.json';
  var MAX_RETRIES = 3;       // 首次请求失败后最多再重试 3 次
  var RETRY_DELAY = 1000;    // 每次重试间隔约 1s

  var STATUS = {
    pass: { cls: 'pass', label: '通过' },
    warn: { cls: 'warn', label: '警告' },
    fail: { cls: 'fail', label: '不通过' }
  };

  var RULE_LABELS = { emotion: '情绪', irony: '反讽' };

  // ── Helpers ─────────────────────────────────────
  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function byId(id) {
    return document.getElementById(id);
  }

  function sleep(ms) {
    return new Promise(function (resolve) { setTimeout(resolve, ms); });
  }

  function isNum(v) {
    return typeof v === 'number' && isFinite(v);
  }

  function toInt(v) {
    var n = Number(v);
    return isFinite(n) ? String(Math.round(n)) : '0';
  }

  function statusMeta(status) {
    return STATUS[status] || STATUS.warn; // 未知状态按 warn 处理
  }

  function badge(status) {
    var m = statusMeta(status);
    return '<span class="badge ' + m.cls + '">' + m.label + '</span>';
  }

  function formatObserved(v) {
    if (!isNum(v)) return { main: '—', raw: '' };
    if (v >= 0 && v <= 1) {
      return { main: (v * 100).toFixed(1) + '%', raw: String(v) };
    }
    return { main: String(v), raw: '' };
  }

  function fmtTime(iso) {
    if (!iso) return '未知';
    var d = new Date(iso);
    if (isNaN(d.getTime())) return String(iso);
    try {
      return d.toLocaleString('zh-CN', {
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit'
      });
    } catch (e) {
      return d.toISOString();
    }
  }

  function metricText(metric) {
    if (!metric || typeof metric !== 'object') return '';
    var bits = [];
    if (metric.processed != null || metric.total != null) {
      bits.push('已加工 ' + toInt(metric.processed) + '/' + toInt(metric.total));
    }
    if (metric.hits != null) bits.push('命中 ' + toInt(metric.hits));
    if (metric.zero_rate_sources != null) bits.push('零加工源 ' + toInt(metric.zero_rate_sources));
    if (metric.sources_total != null) bits.push('源总数 ' + toInt(metric.sources_total));
    return bits.join(' · ');
  }

  // ── 加载状态 ────────────────────────────────────
  function setLoading(text) {
    var el = byId('generated-at');
    if (el) el.textContent = text || '加载中…';
  }

  function showNotice(text) {
    var el = byId('load-state');
    if (!el) return;
    el.textContent = text;
    el.hidden = false;
  }

  function hideNotice() {
    var el = byId('load-state');
    if (el) el.hidden = true;
  }

  // 解析失败 / 截断 / HTTP 404 都走同一套重试；不把失败文案写成“加载失败”。
  async function fetchAudit() {
    var lastErr = null;
    for (var attempt = 0; attempt <= MAX_RETRIES; attempt++) {
      try {
        setLoading('加载中…');
        var resp = await fetch(DATA_URL + '?t=' + Date.now(), { cache: 'no-store' });
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        var data = await resp.json();
        if (!data || typeof data !== 'object' || Array.isArray(data)) {
          throw new Error('unexpected payload');
        }
        return data;
      } catch (err) {
        lastErr = err;
        if (attempt < MAX_RETRIES) await sleep(RETRY_DELAY);
      }
    }
    throw lastErr || new Error('audit data unavailable');
  }

  // ── 渲染：更新时间 / 总状态 ──────────────────────
  function renderGeneratedAt(iso) {
    var el = byId('generated-at');
    if (!el) return;
    el.textContent = fmtTime(iso);
    if (iso) el.title = String(iso);
  }

  function renderSummary(summary) {
    var el = byId('summary-status');
    if (!el) return;
    summary = summary || {};
    var html = badge(summary.status);
    var total = Number(summary.checks_total);
    if (isFinite(total) && total > 0) {
      html += '<span class="audit-summary-count">' +
        esc(toInt(summary.checks_passed)) + '/' + esc(toInt(total)) + ' 项通过</span>';
    }
    el.innerHTML = html;
  }

  // ── 渲染：审计项卡片 ────────────────────────────
  function renderChecks(checks) {
    var el = byId('checks');
    if (!el) return;
    var list = Array.isArray(checks) ? checks : [];
    if (!list.length) {
      el.innerHTML = '<div class="audit-empty">暂无审计项</div>';
      return;
    }

    el.innerHTML = list.map(function (c) {
      c = c || {};
      var m = statusMeta(c.status);
      var obs = formatObserved(c.observed);
      var meta = [];

      if (c.threshold != null && c.threshold !== '') {
        meta.push('<span>阈值 ' + esc(c.threshold) + '</span>');
      }
      var mt = metricText(c.metric);
      if (mt) meta.push('<span>' + esc(mt) + '</span>');

      var raw = obs.raw
        ? '<span class="audit-observed-raw" title="原始值 ' + esc(obs.raw) + '">' + esc(obs.raw) + '</span>'
        : '';
      var titleAttr = '原始值 ' + (obs.raw || obs.main);

      return '<article class="audit-card status-' + m.cls + '">' +
        '<div class="audit-card-head">' +
          '<span class="audit-card-label">' + esc(c.label || c.id || '未命名审计项') + '</span>' +
          badge(c.status) +
        '</div>' +
        '<div class="audit-observed" title="' + esc(titleAttr) + '">' +
          '<span class="audit-observed-value">' + esc(obs.main) + '</span>' + raw +
        '</div>' +
        '<div class="audit-detail">' + esc(c.detail == null ? '—' : c.detail) + '</div>' +
        (meta.length ? '<div class="audit-meta">' + meta.join('') + '</div>' : '') +
        '</article>';
    }).join('');
  }

  // ── 渲染：按源覆盖率 ────────────────────────────
  function renderBySource(rows) {
    var el = byId('by-source');
    if (!el) return;
    var list = Array.isArray(rows) ? rows.slice() : [];
    if (!list.length) {
      el.innerHTML = '<div class="audit-empty">暂无分源数据</div>';
      return;
    }

    list.sort(function (a, b) {
      var ra = a && isNum(a.rate) ? a.rate : 0;
      var rb = b && isNum(b.rate) ? b.rate : 0;
      return ra - rb;
    });

    var trs = list.map(function (r) {
      r = r || {};
      var total = isNum(r.total) ? r.total : 0;
      var processed = isNum(r.processed) ? r.processed : 0;
      var rate = isNum(r.rate) ? r.rate : (total > 0 ? processed / total : 0);
      var zero = !(rate > 0);
      var pct = (rate * 100).toFixed(1) + '%';

      return '<tr' + (zero ? ' class="is-zero"' : '') + '>' +
        '<td class="audit-src">' + esc(r.source || '未知来源') + '</td>' +
        '<td>' + esc(toInt(total)) + '</td>' +
        '<td>' + esc(toInt(processed)) + '</td>' +
        '<td>' + esc(pct) + '</td>' +
        '</tr>';
    }).join('');

    el.innerHTML = '<table class="audit-table">' +
      '<thead><tr><th>源</th><th>总数</th><th>已加工</th><th>比率</th></tr></thead>' +
      '<tbody>' + trs + '</tbody>' +
      '</table>';
  }

  // ── 渲染：中立度命中 ────────────────────────────
  function renderNeutrality(hits) {
    var el = byId('neutrality-hits');
    if (!el) return;
    var list = Array.isArray(hits) ? hits : [];
    if (!list.length) {
      el.innerHTML = '<div class="audit-empty">未发现残留</div>';
      return;
    }

    el.innerHTML = '<ul class="audit-hits">' + list.map(function (h) {
      h = h || {};
      var rule = RULE_LABELS[h.rule] || h.rule || '未知';

      return '<li class="audit-hit">' +
        '<div class="audit-hit-head">' +
          '<span class="audit-hit-source">' + esc(h.source || '未知来源') + '</span>' +
          '<span class="audit-hit-rule">' + esc(rule) + '</span>' +
          (h.matched ? '<span class="audit-hit-word">命中：' + esc(h.matched) + '</span>' : '') +
        '</div>' +
        (h.title ? '<div class="audit-hit-orig">' + esc(h.title) + '</div>' : '') +
        (h.zh_title ? '<div class="audit-hit-zh">' + esc(h.zh_title) + '</div>' : '') +
        '</li>';
    }).join('') + '</ul>';
  }

  // ── 渲染：诚实性 ────────────────────────────────
  function chips(items, cls) {
    var list = Array.isArray(items) ? items : [];
    if (!list.length) return '<span class="audit-muted">无</span>';
    return '<ul class="audit-chips">' + list.map(function (x) {
      return '<li class="audit-chip' + (cls ? ' ' + cls : '') + '">' + esc(x) + '</li>';
    }).join('') + '</ul>';
  }

  function renderHonesty(footerClaims, deadSources) {
    var el = byId('honesty');
    if (!el) return;
    var f = footerClaims || {};

    el.innerHTML =
      '<div class="audit-honesty-grid">' +
        '<div class="audit-honesty-col">' +
          '<h3 class="audit-honesty-label">声明覆盖（claimed）</h3>' +
          chips(f.claimed) +
        '</div>' +
        '<div class="audit-honesty-col">' +
          '<h3 class="audit-honesty-label">实际产出（actually_producing）</h3>' +
          chips(f.actually_producing) +
        '</div>' +
      '</div>' +
      '<div class="audit-honesty-col">' +
        '<h3 class="audit-honesty-label">虚假声明（false_claims）</h3>' +
        chips(f.false_claims, 'is-false') +
      '</div>' +
      '<div class="audit-honesty-col">' +
        '<h3 class="audit-honesty-label">失联源（dead_sources）</h3>' +
        chips(deadSources, 'is-dead') +
      '</div>';
  }

  function renderAll(data) {
    data = data || {};
    renderGeneratedAt(data.generated_at || data.source_updated);
    renderSummary(data.summary);
    renderChecks(data.checks);
    renderBySource(data.by_source);
    renderNeutrality(data.neutrality_hits);
    renderHonesty(data.footer_claims, data.dead_sources);
  }

  // ── 启动 ────────────────────────────────────────
  async function init() {
    setLoading('加载中…');
    try {
      var data = await fetchAudit();
      hideNotice();
      renderAll(data);
    } catch (err) {
      // 最终仍失败：保留“加载中”语感，引导重试，而非“加载失败”。
      setLoading('加载中…');
      showNotice('数据加载中，请重试');
      if (typeof console !== 'undefined' && console.warn) {
        console.warn('[audit] 数据加载失败:', err && err.message ? err.message : err);
      }
    }
  }

  init();
})();
