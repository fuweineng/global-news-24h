/* 情报哨兵 — 读 docs/data/signal.json，纯静态渲染（无框架） */
(function () {
  'use strict';

  var DATA_URL = 'data/signal.json';
  var TIER_LABEL = { act: '要动手', watch: '要留意', read: '有意思', sideline: '闲读' };
  var state = { data: null, tier: 'all' };

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function fmtAge(h) {
    if (h == null) return '';
    if (h < 1) return Math.max(1, Math.round(h * 60)) + ' 分钟前';
    if (h < 24) return Math.round(h) + ' 小时前';
    return Math.round(h / 24) + ' 天前';
  }

  function fmtTime(iso) {
    if (!iso) return '--:--';
    var d = new Date(iso);
    if (isNaN(d)) return '--:--';
    var p = function (n) { return n < 10 ? '0' + n : '' + n; };
    return p(d.getMonth() + 1) + '-' + p(d.getDate()) + ' ' + p(d.getHours()) + ':' + p(d.getMinutes());
  }

  function hostOf(url) {
    try { return new URL(url).hostname.replace(/^www\./, ''); } catch (e) { return ''; }
  }

  function card(item) {
    var a = el('a', 'sg-card is-' + item.tier);
    a.href = item.url || '#';
    a.target = '_blank';
    a.rel = 'noopener noreferrer';

    var top = el('div', 'sg-card-top');
    top.appendChild(el('span', 'sg-tier ' + item.tier, TIER_LABEL[item.tier] || item.tier));
    if (item.cvss) top.appendChild(el('span', 'sg-badge hot', 'CVSS ' + item.cvss));
    if (item.in_the_wild) top.appendChild(el('span', 'sg-badge hot', '在野利用'));
    if (item.source_count > 1) top.appendChild(el('span', 'sg-badge', item.source_count + ' 家转'));
    top.appendChild(el('span', null, fmtAge(item.age_h)));
    a.appendChild(top);

    a.appendChild(el('div', 'sg-card-title', item.title || ''));
    if (item.why) a.appendChild(el('div', 'sg-why', item.why));
    if (item.action) a.appendChild(el('div', 'sg-action', '→ ' + item.action));

    var foot = el('div', 'sg-card-foot');
    foot.appendChild(el('span', null, item.source_name || ''));
    var h = hostOf(item.url);
    if (h) foot.appendChild(el('span', null, h));
    a.appendChild(foot);
    return a;
  }

  function sectionBox(title, sub, total, items) {
    var box = el('section', 'sg-section');
    var head = el('div', 'sg-section-head');
    head.appendChild(el('span', 'sg-section-title', title));
    if (sub) head.appendChild(el('span', 'sg-section-sub', sub));
    head.appendChild(el('span', 'sg-section-count', total + ' 条'));
    box.appendChild(head);
    if (!items.length) {
      box.appendChild(el('div', 'sg-empty', '这一栏暂时没有需要你看的东西'));
    }
    items.forEach(function (i) { box.appendChild(card(i)); });
    return box;
  }

  function render() {
    var d = state.data;
    var main = document.getElementById('sg-main');
    main.innerHTML = '';
    if (!d) {
      main.appendChild(el('div', 'sg-empty', '数据没加载到，稍后刷新一次'));
      return;
    }

    var shown = 0;
    (d.sections || []).forEach(function (sec) {
      var items = (sec.items || []).filter(function (i) {
        return state.tier === 'all' || i.tier === state.tier;
      });
      if (state.tier !== 'all' && !items.length) return;
      if (state.tier === 'all') items = items.slice(0, 8);
      shown += items.length;
      main.appendChild(sectionBox(sec.name, sec.sub, sec.total != null ? sec.total : items.length, items));
    });

    if (state.tier === 'all' || state.tier === 'sideline') {
      var side = (d.sideline || []);
      if (side.length) {
        main.appendChild(sectionBox('📎 闲读（有趣但唔急，周更合集）', '无聊时先睇', side.length,
          state.tier === 'sideline' ? side : side.slice(0, 4)));
        shown += state.tier === 'sideline' ? side.length : Math.min(4, side.length);
      }
    }
    if (!shown) main.appendChild(el('div', 'sg-empty', '这个级别暂时没有条目'));
  }

  function renderStats(d) {
    var box = document.getElementById('sg-stats');
    box.innerHTML = '';
    var defs = [
      ['act', '要动手'], ['watch', '要留意'], ['read', '有意思'], ['sideline', '闲读']
    ];
    defs.forEach(function (p) {
      var b = el('div', 'sg-stat is-' + p[0]);
      b.appendChild(el('span', 'sg-stat-num', String((d.counts || {})[p[0]] || 0)));
      b.appendChild(el('span', 'sg-stat-label', p[1]));
      box.appendChild(b);
    });
  }

  function renderSources(d) {
    var box = document.getElementById('sg-sources');
    box.innerHTML = '';
    var grid = el('div', 'sg-src-grid');
    (d.sources || []).forEach(function (s) {
      var chip = el('span', 'sg-src' + (s.ok ? '' : ' bad'),
        (s.name || s.id) + ' ' + (s.ok ? s.items : '挂了'));
      if (!s.ok && s.error) chip.title = s.error;
      grid.appendChild(chip);
    });
    box.appendChild(grid);
    var dis = document.getElementById('sg-disclaimer');
    if (dis) dis.textContent = d.disclaimer || '';
  }

  function load() {
    fetch(DATA_URL, { cache: 'no-store' })
      .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .then(function (d) {
        state.data = d;
        document.getElementById('sg-loading') && document.getElementById('sg-loading').remove();
        renderStats(d);
        render();
        renderSources(d);
        var ov = document.getElementById('sg-overview');
        if (d.overview) { ov.textContent = d.overview; ov.hidden = false; }
        var upd = document.getElementById('last-updated');
        if (upd) upd.textContent = fmtTime(d.generated_at) + ' 更新';
        var foot = document.getElementById('sg-footer');
        if (foot) {
          var st = d.stats || {};
          foot.textContent = '抓取 ' + (st.facts_in || 0) + ' 条原始事实 · 合并成 ' +
            (st.clusters || 0) + ' 个事件 · 入口 ' + (st.items || 0) + ' 条';
        }
      })
      .catch(function (e) {
        var main = document.getElementById('sg-main');
        main.innerHTML = '';
        main.appendChild(el('div', 'sg-empty', '加载失败：' + e.message));
      });
  }

  document.getElementById('sg-filter').addEventListener('click', function (ev) {
    var btn = ev.target.closest('.cat-chip');
    if (!btn) return;
    Array.prototype.forEach.call(this.querySelectorAll('.cat-chip'), function (b) {
      b.classList.toggle('active', b === btn);
    });
    state.tier = btn.getAttribute('data-tier') || 'all';
    render();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });

  load();
})();
