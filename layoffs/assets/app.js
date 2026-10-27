(function () {
  'use strict';

  var STATUS_TEXT = { confirmed: '已确认', rumor: '媒体消息 / 传闻', denied: '公司否认' };
  var TODAY = new Date();
  var YEAR = 2026;

  var state = {
    data: null,
    q: '',
    industry: '',
    status: '',
    verify: '',
    onlyCounted: false,
    sortAsc: false,
    range: 3650,
    regions: { '国内': true, '中国区': true, '中国香港': true, '中国台湾': true, '境外': false }
  };

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function daysAgo(dateStr) {
    var d = new Date(dateStr + 'T00:00:00');
    return Math.round((TODAY - d) / 86400000);
  }

  function load() {
    if (window.__LAYOFFS__) { return Promise.resolve(window.__LAYOFFS__); }
    return fetch('data/layoffs.json', { cache: 'no-store' })
      .then(function (r) { return r.json(); })
      .catch(function () { return window.__LAYOFFS__ || { items: [], insights: [] }; });
  }

  // ---------- filters ----------
  function applyFilters(items) {
    var q = state.q.trim().toLowerCase();
    return items.filter(function (it) {
      if (!state.regions[it.region]) return false;
      if (state.industry && it.industry !== state.industry) return false;
      if (state.status && it.status !== state.status) return false;
      if (state.verify && it.verify !== state.verify) return false;
      if (state.onlyCounted && !it.scale_num) return false;
      if (daysAgo(it.date) > state.range) return false;
      if (q) {
        var hay = [it.company, it.industry, it.kind, it.summary, it.region,
          it.scale_text, it.scope, it.dept, it.reason, it.pct_text]
          .join(' ').toLowerCase();
        if (hay.indexOf(q) === -1) return false;
      }
      return true;
    });
  }

  // ---------- KPI ----------
  function renderKpis(items) {
    var months = {};
    items.forEach(function (i) { months[i.date.slice(0, 7)] = 1; });
    var withNum = items.filter(function (i) { return i.scale_num; }).length;
    var flagged = items.filter(function (i) {
      return i.missing && i.missing.length;
    }).length;
    var cos = {};
    items.forEach(function (i) { cos[i.company] = 1; });

    var html = [
      kpi('k1', '收录条目', items.length, '条', '当前筛选范围内'),
      kpi('k2', '覆盖月份', Object.keys(months).length, '个月', '2026 年 1 月 — 10 月'),
      kpi('k3', '披露明确人数', withNum, '条',
        '共 ' + items.length + ' 条中，' + (items.length - withNum) + ' 条未披露人数'),
      kpi('k4', '数据待补 / 待核实', flagged, '条', '缺失字段或未获官方确认')
    ].join('');
    document.getElementById('kpis').innerHTML = html;
  }

  function kpi(cls, label, value, unit, note) {
    return '<div class="kpi ' + cls + '">' +
      '<div class="k-label">' + esc(label) + '</div>' +
      '<div class="k-value">' + esc(value) + (unit ? '<small>' + esc(unit) + '</small>' : '') + '</div>' +
      '<div class="k-note">' + esc(note) + '</div></div>';
  }

  // ---------- 逐月分布 ----------
  function renderTrend(items) {
    var buckets = [];
    for (var m = 1; m <= 12; m++) {
      buckets.push({ key: YEAR + '-' + String(m).padStart(2, '0'), label: m + '月', n: 0 });
    }
    var map = {};
    buckets.forEach(function (b) { map[b.key] = b; });
    items.forEach(function (it) {
      var k = it.date.slice(0, 7);
      if (map[k]) map[k].n++;
    });
    var max = Math.max.apply(null, buckets.map(function (b) { return b.n; }).concat([1]));

    var cols = buckets.map(function (b) {
      var h = b.n ? Math.max(8, Math.round(b.n / max * 100)) : 3;
      return '<div class="col" title="' + b.key + '：' + b.n + ' 条">' +
        (b.n ? '<div class="n">' + b.n + '</div>' : '') +
        '<div class="b" style="height:' + h + 'px"></div>' +
        '<div class="t">' + b.label + '</div></div>';
    }).join('');
    document.getElementById('chart-trend').innerHTML = '<div class="trend">' + cols + '</div>';
  }

  function renderIndustry(items) {
    var m = {};
    items.forEach(function (i) { m[i.industry] = (m[i.industry] || 0) + 1; });
    var arr = Object.keys(m).map(function (k) { return { k: k, v: m[k] }; })
      .sort(function (a, b) { return b.v - a.v; }).slice(0, 10);
    var max = arr.length ? arr[0].v : 1;
    document.getElementById('chart-industry').innerHTML = arr.map(function (o) {
      return '<div class="bar-row"><div class="lb" title="' + esc(o.k) + '">' + esc(o.k) + '</div>' +
        '<div class="track"><div class="fill" style="width:' + Math.round(o.v / max * 100) + '%"></div></div>' +
        '<div class="vl">' + o.v + ' 条</div></div>';
    }).join('') || '<div class="empty">暂无数据</div>';
  }

  function renderInsights(list) {
    document.getElementById('insights').innerHTML = (list || []).map(function (o) {
      return '<div class="insight"><h4>' + esc(o.title) + '</h4><p>' + esc(o.body) + '</p></div>';
    }).join('');
  }

  function renderCoverage(cov) {
    if (!cov) return;
    var box = document.getElementById('coverage');
    if (!box) return;
    box.innerHTML =
      '<div class="covhead"><span class="covrange">数据时间范围：' + esc(cov.from) + ' — ' + esc(cov.to) + '</span>' +
      '<span class="tag-soft">覆盖范围与统计口径</span></div>' +
      '<div class="covgrid">' +
      '<div><h4>覆盖范围</h4><p>' + esc(cov.scope_note) + '</p></div>' +
      '<div><h4>数据来源</h4><p>' + esc(cov.sources_note) + '</p></div>' +
      '<div><h4>统计口径</h4><p>' + esc(cov.count_note) + '</p></div>' +
      '</div>';
  }

  // ---------- 列表 ----------
  function renderList(items) {
    var box = document.getElementById('list');
    document.getElementById('empty').hidden = items.length > 0;
    box.innerHTML = items.map(function (it) {
      var facts = [
        '<span class="fact">' + esc(it.industry) + '</span>',
        '<span class="fact">' + esc(it.region) + '</span>',
        '<span class="fact">' + esc(it.kind) + '</span>'
      ];

      var rows = [
        ['裁员日期', it.date],
        ['涉及人数', it.scale_text || '未披露'],
        ['人数占比', it.pct_text || '未披露'],
        ['涉及部门', it.dept || '未披露'],
        ['涉及地区', it.scope || '未披露'],
        ['裁员原因', it.reason || '未披露']
      ];

      var grid = rows.map(function (r) {
        var v = r[1] || '未披露';
        var blank = !v || v === '未披露';
        return '<div class="fr"><span class="fk">' + esc(r[0]) + '</span>' +
          '<span class="fv' + (blank ? ' fv-miss' : '') + '">' + esc(v) + '</span></div>';
      }).join('');

      var missTags = (it.missing || []).length
        ? '<div class="misstags">数据缺失 / 待确认：' + it.missing.map(function (m) {
            return '<span class="mtag">' + esc(m) + '</span>';
          }).join('') + '</div>'
        : '';

      var verifyCls = it.verify && it.verify.indexOf('未核实') === 0 ? 'v-warn'
        : (it.verify && it.verify.indexOf('部分') === 0 ? 'v-mid' : 'v-ok');

      return '<article class="item s-' + it.status + '">' +
        '<div class="stripe"></div><div class="body">' +
        '<div class="head"><span class="co">' + esc(it.company) + '</span>' +
        '<span class="badge ' + it.status + '">' + STATUS_TEXT[it.status] + '</span>' +
        '<span class="verify ' + verifyCls + '">' + esc(it.verify || '未核实') + '</span>' +
        '<span class="date">' + esc(it.date) + '</span></div>' +
        '<p class="sum">' + esc(it.summary) + '</p>' +
        '<div class="fgrid">' + grid + '</div>' +
        '<div class="facts">' + facts.join('') + '</div>' +
        missTags +
        (it.note ? '<div class="note">口径提醒：' + esc(it.note) + '</div>' : '') +
        '<div class="src">来源：<a href="' + esc(it.source_url) + '" target="_blank" rel="noopener">' + esc(it.source_name) + '</a></div>' +
        '</div></article>';
    }).join('');
  }

  function renderFeed() {
    fetch('data/auto_feed.json', { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) {
        if (!j || !j.items || !j.items.length) return;
        document.getElementById('feedpanel').hidden = false;
        document.getElementById('feed').innerHTML = j.items.slice(0, 20).map(function (o) {
          return '<div class="fi"><span>' + esc(o.date) + '</span>' +
            '<a href="' + esc(o.url) + '" target="_blank" rel="noopener">' + esc(o.title) + '</a>' +
            '<span>' + esc(o.source || '') + '</span></div>';
        }).join('');
      }).catch(function () {});
  }

  function render() {
    var items = applyFilters(state.data.items || []).sort(function (a, b) {
      if (a.date === b.date) { return a.company < b.company ? -1 : 1; }
      return state.sortAsc ? (a.date > b.date ? 1 : -1) : (a.date < b.date ? 1 : -1);
    });
    renderKpis(items);
    renderTrend(items);
    renderIndustry(items);
    renderList(items);
    document.getElementById('fcount').textContent =
      '共 ' + items.length + ' 条 / 全库 ' + (state.data.items || []).length + ' 条';
  }

  // ---------- init ----------
  function init(data) {
    state.data = data;
    document.getElementById('m-updated').textContent = data.updated_at || '—';
    document.getElementById('m-count').textContent = (data.items || []).length + ' 条';
    var pn = document.getElementById('m-period');
    if (pn) pn.textContent = data.period_note || '—';

    var sel = document.getElementById('f-industry');
    var inds = {};
    (data.items || []).forEach(function (i) { inds[i.industry] = 1; });
    Object.keys(inds).sort().forEach(function (k) {
      var o = document.createElement('option');
      o.value = k; o.textContent = k;
      sel.appendChild(o);
    });

    renderCoverage(data.coverage);
    renderInsights(data.insights);
    render();
    renderFeed();

    document.getElementById('q').addEventListener('input', function (e) { state.q = e.target.value; render(); });
    document.getElementById('f-industry').addEventListener('change', function (e) { state.industry = e.target.value; render(); });
    document.getElementById('f-status').addEventListener('change', function (e) { state.status = e.target.value; render(); });
    document.getElementById('f-verify').addEventListener('change', function (e) { state.verify = e.target.value; render(); });
    document.getElementById('f-sort').addEventListener('change', function (e) { state.sortAsc = e.target.value === 'asc'; render(); });
    document.getElementById('only-counted').addEventListener('change', function (e) { state.onlyCounted = e.target.checked; render(); });
    document.getElementById('reset').addEventListener('click', function () {
      state.q = ''; state.industry = ''; state.status = ''; state.verify = '';
      state.onlyCounted = false; state.sortAsc = false;
      state.regions = { '国内': true, '中国区': true, '中国香港': true, '中国台湾': true, '境外': false };
      document.getElementById('q').value = '';
      document.getElementById('f-industry').value = '';
      document.getElementById('f-status').value = '';
      document.getElementById('f-verify').value = '';
      document.getElementById('f-sort').value = 'desc';
      document.getElementById('only-counted').checked = false;
      Array.prototype.forEach.call(document.querySelectorAll('#region-chips input[data-region]'), function (cb) {
        cb.checked = state.regions[cb.value];
        cb.closest('.chip').classList.toggle('active', cb.checked);
      });
      render();
    });
    Array.prototype.forEach.call(document.querySelectorAll('#region-chips input[data-region]'), function (cb) {
      cb.addEventListener('change', function () {
        state.regions[cb.value] = cb.checked;
        cb.closest('.chip').classList.toggle('active', cb.checked);
        render();
      });
    });
  }

  load().then(init);
})();
