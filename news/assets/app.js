(function () {
  var state = { data: null, tab: 'all', q: '' };

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function el(id) { return document.getElementById(id); }

  function renderCards(chans) {
    var box = el('cards');
    box.innerHTML = chans.map(function (c) {
      var p = c.latest;
      if (!p) {
        return '<div class="card emptyc" style="--c:' + c.color + '">' +
          '<div class="crow"><span class="cname">' + esc(c.name) + '</span>' +
          '<span class="cdate">' + esc(c.freq) + '</span></div>' +
          '<h3>暂无产出</h3>' +
          '<p class="exc">该频道尚未检测到可发布的内容' +
          (c.warn ? '：' + esc(c.warn) : '') + '</p></div>';
      }
      return '<div class="card" style="--c:' + c.color + '">' +
        '<div class="crow"><span class="cname">' + esc(c.name) + '</span>' +
        '<span class="cdate">' + esc(p.date) + '</span></div>' +
        '<h3><a href="' + esc(p.url) + '">' + esc(p.title) + '</a></h3>' +
        '<p class="exc">' + esc(p.excerpt) + '</p>' +
        '<a class="go" href="' + esc(p.url) + '">阅读全文 →</a></div>';
    }).join('');
  }

  function renderTabs(chans) {
    var box = el('tabs');
    var items = [{ id: 'all', tab: '全部', count: state.data.total }].concat(
      chans.map(function (c) { return { id: c.id, tab: c.tab, count: c.count }; })
    );
    box.innerHTML = items.map(function (t) {
      return '<span class="tab' + (state.tab === t.id ? ' on' : '') +
        '" data-id="' + t.id + '">' + esc(t.tab) +
        ' <b style="font-weight:600;opacity:.6">' + t.count + '</b></span>';
    }).join('');
    box.querySelectorAll('.tab').forEach(function (n) {
      n.addEventListener('click', function () {
        state.tab = n.getAttribute('data-id');
        renderTabs(chans); renderArchive();
      });
    });
  }

  function flat() {
    var rows = [];
    state.data.channels.forEach(function (c) {
      c.posts.forEach(function (p) {
        rows.push({
          date: p.date, title: p.title, excerpt: p.excerpt, url: p.url,
          cid: c.id, cname: c.name, color: c.color
        });
      });
    });
    rows.sort(function (a, b) {
      if (a.date === b.date) return a.cname < b.cname ? -1 : 1;
      return a.date < b.date ? 1 : -1;
    });
    return rows;
  }

  function renderArchive() {
    var rows = flat().filter(function (r) {
      if (state.tab !== 'all' && r.cid !== state.tab) return false;
      if (!state.q) return true;
      var q = state.q.toLowerCase();
      return (r.title + ' ' + r.excerpt + ' ' + r.cname).toLowerCase().indexOf(q) >= 0;
    });
    el('archive').innerHTML = rows.map(function (r) {
      return '<div class="arow" style="--c:' + r.color + '">' +
        '<span class="ad">' + esc(r.date) + '</span>' +
        '<span class="ac">' + esc(r.cname) + '</span>' +
        '<span class="at"><a href="' + esc(r.url) + '">' + esc(r.title) + '</a></span>' +
        '<span class="ae">' + esc(r.excerpt) + '</span></div>';
    }).join('');
    el('empty').hidden = rows.length > 0;
    el('fcount').textContent = rows.length + ' 篇';
  }

  function boot() {
    fetch('data/index.json', { cache: 'no-store' })
      .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .then(function (d) {
        state.data = d;
        el('m-updated').textContent = d.generated_at || '—';
        el('m-total').textContent = (d.total || 0) + ' 篇';
        el('hint').textContent = d.channels.length + ' 个频道 · 各频道最新一期';
        renderCards(d.channels);
        renderTabs(d.channels);
        renderArchive();
      })
      .catch(function (e) {
        el('cards').innerHTML = '<div class="card emptyc" style="--c:#999">' +
          '<h3>数据加载失败</h3><p class="exc">' + esc(e.message) +
          '。若在本地直接打开文件，请用本地服务器访问（如 python -m http.server）。</p></div>';
      });

    el('q').addEventListener('input', function (e) {
      state.q = e.target.value.trim();
      if (state.data) renderArchive();
    });
  }

  boot();
})();
