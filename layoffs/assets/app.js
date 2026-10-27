(function () {
  'use strict';

  var STATUS_TEXT = { confirmed: '已确认', rumor: '媒体消息 / 传闻', denied: '公司否认' };
  var TODAY = new Date();

  var state = {
    data: null,
    q: '',
    industry: '',
    status: '',
    range: 30,
    regions: { '国内': true, '中国区': true, '中国台湾': false, '境外': false }
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

  function fmtDate(dateStr) {
    var p = dateStr.split('-');
    return p[1] + '/' + p[2];
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
      if (daysAgo(it.date) > state.range) return false;
      if (q) {
        var hay = [it.company, it.industry, it.kind, it.summary, it.region, it.scale_text]
          .join(' ').toLowerCase();
        if (hay.indexOf(q) === -1) return false;
      }
      return true;
    });
  }

  // ---------- render ----------
  function renderKpis(items) {
    var sorted = items.map(function (i) { return i.date; }).sort();
    var lastDate = sorted.length ? sorted[sorted.length - 1] : '—';
    var todayCount = items.filter(function (i) { return i.date === lastDate; }).length;
    var weekCount = items.filter(function (i) { return daysAgo(i.date) <= 7; }).length;
    var headSum = items.reduce(function (a, i) { return a + (i.scale_num || 0); }, 0);
    var cos = {};
    items.forEach(function (i) { cos[i.company] = 1; });

    var html = [
      kpi('k1', '最新日期新增', todayCount, '条', lastDate + ' 当日'),
      kpi('k2', '近 7 日条目', weekCount, '条', '滚动统计'),
      kpi('k3', '披露涉及岗位', headSum ? headSum.toLocaleString() : '—', headSum ? '人' : '', '仅含明确披露人数口径'),
      kpi('k4', '涉及主体', Object.keys(cos).length, '家', '去重后企业 / 机构数')
    ].join('');
    document.getElementById('kpis').innerHTML = html;
  }

  function kpi(cls, label, value, unit, note) {
    return '<div class="kpi ' + cls + '">' +
      '<div class="k-label">' + esc(label) + '</div>' +
      '<div class="k-value">' + esc(value) + (unit ? '<small>' + esc(unit) + '</small>' : '') + '</div>' +
      '<div class="k-note">' + esc(note) + '</div></div>';
  }

  function renderTrend(items) {
    var days = [];
    for (var i = 13; i >= 0; i--) {
      var d = new Date(TODAY.getTime() - i * 86400000);
      var key = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
      days.push({ key: key, label: String(d.getMonth() + 1) + '/' + d.getDate(), n: 0 });
    }
    var map = {};
    days.forEach(function (d) { map[d.key] = d; });
    items.forEach(function (it) { if (map[it.date]) map[it.date].n++; });
    var max = Math.max.apply(null, days.map(function (d) { return d.n; }).concat([1]));

    var cols = days.map(function (d) {
      var h = d.n ? Math.max(6, Math.round(d.n / max * 100)) : 3;
      return '<div class="col" title="' + d.key + '：' + d.n + ' 条">' +
        (d.n ? '<div class="n">' + d.n + '</div>' : '') +
        '<div class="b" style="height:' + h + 'px"></div>' +
        '<div class="t">' + d.label + '</div></div>';
    }).join('');
    document.getElementById('chart-trend').innerHTML = '<div class="trend">' + cols + '</div>';
  }

  function renderIndustry(items) {
    var m = {};
    items.forEach(function (i) { m[i.industry] = (m[i.industry] || 0) + 1; });
    var arr = Object.keys(m).map(function (k) { return { k: k, v: m[k] }; })
      .sort(function (a, b) { return b.v - a.v; }).slice(0, 8);
    var max = arr.length ? arr[0].v : 1;
    document.getElementById('chart-industry').innerHTML = arr.map(function (o) {
      return '<div class="bar-row"><div class="lb">' + esc(o.k) + '</div>' +
        '<div class="track"><div class="fill" style="width:' + Math.round(o.v / max * 100) + '%"></div></div>' +
        '<div class="vl">' + o.v + ' 条</div></div>';
    }).join('') || '<div class="empty">暂无数据</div>';
  }

  function renderInsights(list) {
    document.getElementById('insights').innerHTML = (list || []).map(function (o) {
      return '<div class="insight"><h4>' + esc(o.title) + '</h4><p>' + esc(o.body) + '</p></div>';
    }).join('');
  }

  function renderList(items) {
    var box = document.getElementById('list');
    document.getElementById('empty').hidden = items.length > 0;
    box.innerHTML = items.map(function (it) {
      var facts = [
        '<span class="fact">' + esc(it.industry) + '</span>',
        '<span class="fact">' + esc(it.kind) + '</span>',
        it.scale_text ? '<span class="fact">规模 <b>' + esc(it.scale_text) + '</b></span>' : '',
        '<span class="fact">' + esc(it.region) + '</span>'
      ].join('');
      return '<article class="item s-' + it.status + '">' +
        '<div class="stripe"></div><div class="body">' +
        '<div class="head"><span class="co">' + esc(it.company) + '</span>' +
        '<span class="badge ' + it.status + '">' + STATUS_TEXT[it.status] + '</span>' +
        '<span class="date">' + esc(it.date) + '</span></div>' +
        '<p class="sum">' + esc(it.summary) + '</p>' +
        '<div class="facts">' + facts + '</div>' +
        (it.note ? '<div class="note">备注：' + esc(it.note) + '</div>' : '') +
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
      return a.date < b.date ? 1 : a.date > b.date ? -1 : 0;
    });
    renderKpis(items);
    renderTrend(items);
    renderIndustry(items);
    renderList(items);
    document.getElementById('fcount').textContent = '共 ' + items.length + ' 条 / 全库 ' + (state.data.items || []).length + ' 条';
  }

  // ---------- init ----------
  function init(data) {
    state.data = data;
    document.getElementById('m-updated').textContent = data.updated_at || '—';
    document.getElementById('m-count').textContent = (data.items || []).length + ' 条';

    var sel = document.getElementById('f-industry');
    var inds = {};
    (data.items || []).forEach(function (i) { inds[i.industry] = 1; });
    Object.keys(inds).sort().forEach(function (k) {
      var o = document.createElement('option');
      o.value = k; o.textContent = k;
      sel.appendChild(o);
    });

    renderInsights(data.insights);
    render();
    renderFeed();

    document.getElementById('q').addEventListener('input', function (e) { state.q = e.target.value; render(); });
    document.getElementById('f-industry').addEventListener('change', function (e) { state.industry = e.target.value; render(); });
    document.getElementById('f-status').addEventListener('change', function (e) { state.status = e.target.value; render(); });
    document.getElementById('f-range').addEventListener('change', function (e) { state.range = +e.target.value; render(); });
    document.getElementById('reset').addEventListener('click', function () {
      state.q = ''; state.industry = ''; state.status = ''; state.range = 30;
      state.regions = { '国内': true, '中国区': true, '中国台湾': false, '境外': false };
      document.getElementById('q').value = '';
      document.getElementById('f-industry').value = '';
      document.getElementById('f-status').value = '';
      document.getElementById('f-range').value = '30';
      Array.prototype.forEach.call(document.querySelectorAll('#region-chips input'), function (cb) {
        cb.checked = state.regions[cb.value];
        cb.closest('.chip').classList.toggle('active', cb.checked);
      });
      render();
    });
    Array.prototype.forEach.call(document.querySelectorAll('#region-chips input'), function (cb) {
      cb.addEventListener('change', function () {
        state.regions[cb.value] = cb.checked;
        cb.closest('.chip').classList.toggle('active', cb.checked);
        render();
      });
    });

    // 默认范围为空时自动放宽到全库
    if (!applyFilters(state.data.items || []).length && state.range === 30) {
      state.range = 3650;
      document.getElementById('f-range').value = '3650';
      render();
    }
  }

  load().then(init);
})();
