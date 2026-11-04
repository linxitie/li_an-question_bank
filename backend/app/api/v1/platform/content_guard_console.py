"""管理员端敏感词治理工作台（单文件 HTML，无前端构建依赖）。

以 HTMLResponse 提供；所有数据请求走 /api/v1/admin/content-guard/*，
页面不内嵌凭据，token 只保存在浏览器 sessionStorage/localStorage。
"""

CONSOLE_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>敏感词治理工作台 · 砺安题库</title>
<style>
:root{
  --primary:#2563EB; --accent:#0EA5E9; --bg:#F8FAFC; --card:#FFFFFF;
  --text:#1A1A1A; --muted:#64748B; --line:#E2E8F0; --danger:#DC2626;
  --warn:#D97706; --ok:#059669; --radius:12px;
  --xs:4px; --sm:8px; --md:16px; --lg:24px; --xl:32px;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:14px/1.7 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif}
button{font:inherit;cursor:pointer;border:1px solid var(--line);background:#fff;border-radius:8px;padding:6px 12px}
button:hover{border-color:var(--primary);color:var(--primary)}
button.primary{background:var(--primary);border-color:var(--primary);color:#fff}
button.primary:hover{opacity:.92;color:#fff}
button.danger{color:var(--danger);border-color:#FECACA}
input,select,textarea{font:inherit;border:1px solid var(--line);border-radius:8px;padding:7px 10px;background:#fff;color:var(--text)}
input:focus,select:focus,textarea:focus{outline:2px solid #BFDBFE;border-color:var(--primary)}
table{width:100%;border-collapse:collapse}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--muted);font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.04em}
code,pre{font-family:ui-monospace,Consolas,monospace;font-size:12px}
pre{background:#0F172A;color:#E2E8F0;padding:12px;border-radius:8px;overflow:auto;max-height:360px}
#login{max-width:380px;margin:12vh auto;background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:var(--xl);box-shadow:0 8px 30px rgba(15,23,42,.06)}
#login h1{font-size:20px;margin:0 0 var(--sm)}
#login p{color:var(--muted);margin:0 0 var(--lg)}
.field{display:flex;flex-direction:column;gap:6px;margin-bottom:12px}
.field label{font-size:12px;color:var(--muted)}
.header{display:flex;align-items:center;gap:var(--md);padding:14px var(--lg);background:var(--card);border-bottom:1px solid var(--line);position:sticky;top:0;z-index:5}
.header h1{font-size:16px;margin:0;flex:1}
.badge{display:inline-block;padding:2px 8px;border-radius:999px;font-size:12px;background:#EFF6FF;color:var(--primary)}
.badge.blocked{background:#FEF2F2;color:var(--danger)}
.badge.masked{background:#FFFBEB;color:var(--warn)}
.badge.reviewed{background:#ECFDF5;color:var(--ok)}
nav{display:flex;gap:var(--xs);padding:0 var(--lg);background:var(--card);border-bottom:1px solid var(--line);overflow:auto}
nav button{border:none;border-bottom:2px solid transparent;border-radius:0;background:transparent;padding:10px 12px;color:var(--muted)}
nav button.active{color:var(--primary);border-bottom-color:var(--primary);font-weight:600}
main{max-width:1240px;margin:0 auto;padding:var(--lg)}
section{display:none}
section.active{display:block}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:var(--md)}
.card{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:var(--md)}
.card h3{margin:0 0 var(--sm);font-size:13px;color:var(--muted);font-weight:600}
.kpi{font-size:28px;font-weight:700;line-height:1.2}
.row{display:flex;gap:var(--sm);align-items:center;flex-wrap:wrap}
.spread{display:flex;justify-content:space-between;align-items:center;gap:var(--sm);flex-wrap:wrap}
.muted{color:var(--muted)}
.mt{margin-top:var(--md)}
.mb{margin-bottom:var(--md)}
.table-wrap{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);overflow:auto}
.bars{display:flex;align-items:flex-end;gap:6px;height:120px;padding-top:10px}
.bar{flex:1;background:#DBEAFE;border-radius:4px 4px 0 0;min-height:2px;position:relative}
.bar span{position:absolute;top:-18px;left:0;right:0;text-align:center;font-size:10px;color:var(--muted)}
.toast{position:fixed;right:20px;bottom:20px;background:#0F172A;color:#fff;padding:10px 16px;border-radius:8px;opacity:0;transition:.2s;pointer-events:none;max-width:420px}
.toast.show{opacity:1}
.detail{position:fixed;inset:0;background:rgba(15,23,42,.45);display:none;align-items:center;justify-content:center;padding:var(--lg);z-index:20}
.detail.show{display:flex}
.detail-box{background:#fff;border-radius:var(--radius);max-width:760px;width:100%;max-height:86vh;overflow:auto;padding:var(--lg)}
.hint{font-size:12px;color:var(--muted)}
@media(max-width:720px){main{padding:var(--md)} .header h1{font-size:14px}}
</style>
</head>
<body>
<div id="login">
  <h1>敏感词治理工作台</h1>
  <p>审核即研判，研判即知识沉淀。请使用管理员账号登录。</p>
  <div class="field"><label>账号</label><input id="username" autocomplete="username" placeholder="用户名 / 工号 / 手机号"></div>
  <div class="field"><label>密码</label><input id="password" type="password" autocomplete="current-password"></div>
  <button class="primary" id="login-btn" style="width:100%">登录</button>
  <p class="hint mt">也可以粘贴已有 access_token：</p>
  <div class="row"><input id="token-input" style="flex:1" placeholder="eyJhbGci..."><button id="token-btn">使用令牌</button></div>
</div>
<div id="app" hidden>
  <div class="header">
    <h1>敏感词自生长知识库</h1>
    <span class="badge" id="engine-badge">引擎 -</span>
    <span class="muted" id="today-badge"></span>
    <button id="refresh-btn">刷新</button>
    <button id="logout-btn">退出</button>
  </div>
  <nav>
    <button data-tab="overview" class="active">总览</button>
    <button data-tab="terms">词条</button>
    <button data-tab="judgments">判定</button>
    <button data-tab="proposals">提案</button>
    <button data-tab="graph">图谱</button>
    <button data-tab="tools">工具</button>
  </nav>
  <main>
    <section id="tab-overview" class="active">
      <div class="grid" id="kpis"></div>
      <div class="card mt"><div class="spread"><h3>近 14 天审核趋势</h3><span class="hint">柱高=总量，红色=阻断</span></div><div class="bars" id="trend"></div></div>
      <div class="table-wrap mt"><table><thead><tr><th>高频词条</th><th>等级</th><th>命中</th><th>误判</th><th>置信度</th></tr></thead><tbody id="top-terms"></tbody></table></div>
    </section>
    <section id="tab-terms">
      <div class="card mb">
        <div class="spread"><h3>新增词条</h3></div>
        <div class="row mt">
          <input id="new-term" placeholder="词条" style="width:160px">
          <select id="new-level"><option value="blocked">blocked 阻断</option><option value="masked" selected>masked 打码</option><option value="reviewed">reviewed 研判</option></select>
          <input id="new-category" placeholder="类别，如 abuse" value="abuse" style="width:140px">
          <input id="new-confidence" type="number" min="0" max="1" step="0.05" value="0.8" style="width:90px">
          <button class="primary" id="create-term">新增</button>
        </div>
      </div>
      <div class="row mb">
        <input id="term-query" placeholder="搜索词条" style="width:200px">
        <select id="term-level"><option value="">全部等级</option><option>blocked</option><option>masked</option><option>reviewed</option></select>
        <button id="term-search">查询</button>
        <span class="hint" id="term-count"></span>
      </div>
      <div class="table-wrap"><table><thead><tr><th>ID</th><th>词条</th><th>等级</th><th>类别</th><th>置信度</th><th>命中/误判</th><th>操作</th></tr></thead><tbody id="terms"></tbody></table></div>
      <div class="card mt" id="term-detail" hidden></div>
    </section>
    <section id="tab-judgments">
      <div class="row mb">
        <select id="judge-decision"><option value="">全部处置</option><option>block</option><option>mask</option><option>review</option></select>
        <select id="judge-scene"><option value="">全部场景</option><option>forum_post</option><option>forum_comment</option><option>profile</option></select>
        <button id="judge-search">查询</button>
      </div>
      <div class="table-wrap"><table><thead><tr><th>ID</th><th>场景/来源</th><th>摘要</th><th>等级</th><th>处置</th><th>置信度</th><th>人工复核</th><th></th></tr></thead><tbody id="judgments"></tbody></table></div>
    </section>
    <section id="tab-proposals">
      <div class="row mb">
        <select id="proposal-status"><option value="pending" selected>待审</option><option value="applied">已通过</option><option value="rejected">已拒绝</option><option value="">全部</option></select>
        <select id="proposal-kind"><option value="">全部类型</option><option>add_term</option><option>add_variant</option><option>update_level</option><option>deprecate_term</option><option>new_policy</option><option>merge_terms</option><option>consistency</option></select>
        <button id="proposal-search">查询</button>
      </div>
      <div class="table-wrap"><table><thead><tr><th>ID</th><th>类型</th><th>标题</th><th>提出方</th><th>状态</th><th>操作</th></tr></thead><tbody id="proposals"></tbody></table></div>
    </section>
    <section id="tab-graph">
      <div class="card mb">
        <div class="row">
          <select id="graph-type"><option>term</option><option>policy</option><option>judgment</option><option>task</option><option>proposal</option><option>case</option><option>variant</option></select>
          <input id="graph-id" placeholder="节点 ID，如 1" style="width:140px">
          <select id="graph-depth"><option value="1">1 跳</option><option value="2" selected>2 跳</option><option value="3">3 跳</option></select>
          <button id="graph-load">展开</button>
        </div>
      </div>
      <div class="grid" style="grid-template-columns:1fr 1fr">
        <div class="card"><h3>节点</h3><div id="graph-nodes" class="hint">选择节点后展开</div></div>
        <div class="card"><h3>关系</h3><div id="graph-edges" class="hint">-</div></div>
      </div>
    </section>
    <section id="tab-tools">
      <div class="grid" style="grid-template-columns:1fr 1fr">
        <div class="card">
          <h3>文本检测（不落判定）</h3>
          <textarea id="detect-text" rows="4" style="width:100%" placeholder="输入待测文本"></textarea>
          <div class="row mt"><button class="primary" id="detect-btn">检测</button></div>
          <pre id="detect-result" class="mt" hidden></pre>
        </div>
        <div class="card">
          <h3>红队与对账</h3>
          <div class="row">
            <button id="redteam-btn">运行红队</button>
            <button id="reconcile-btn">跨层对账</button>
            <button id="reload-btn">热加载词库</button>
            <button id="seed-btn">补种目录</button>
          </div>
          <pre id="tool-result" class="mt" hidden></pre>
        </div>
        <div class="card">
          <h3>Obsidian 投影</h3>
          <p class="hint">导出只读投影与待审队列；导入会应用人工勾选结果。</p>
          <div class="row"><button id="export-btn">导出投影</button><button id="import-btn">导入审阅</button></div>
          <pre id="obsidian-result" class="mt" hidden></pre>
        </div>
        <div class="card">
          <h3>审计链</h3>
          <p class="hint">逐条重算 prev_hash + 内容哈希，校验是否被篡改。</p>
          <div class="row"><button id="audit-btn">校验哈希链</button></div>
          <pre id="audit-result" class="mt" hidden></pre>
        </div>
      </div>
    </section>
  </main>
</div>
<div class="detail" id="detail"><div class="detail-box"><div class="spread"><h3 id="detail-title"></h3><button id="detail-close">关闭</button></div><div id="detail-body"></div></div></div>
<div class="toast" id="toast"></div>
<script>
(function(){
  var TOKEN_KEY = 'cg_token';
  var API = '/api/v1/admin/content-guard';
  var state = { tab: 'overview' };

  function $(sel){ return document.querySelector(sel); }
  function $$(sel){ return Array.prototype.slice.call(document.querySelectorAll(sel)); }
  function esc(value){
    return String(value == null ? '' : value).replace(/[&<>"']/g, function(ch){
      return { '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' }[ch];
    });
  }
  function toast(message){
    var node = $('#toast');
    node.textContent = message;
    node.className = 'toast show';
    setTimeout(function(){ node.className = 'toast'; }, 2600);
  }
  function saveToken(value){
    sessionStorage.setItem(TOKEN_KEY, value);
    localStorage.setItem(TOKEN_KEY, value);
  }
  function token(){
    return sessionStorage.getItem(TOKEN_KEY) || localStorage.getItem(TOKEN_KEY) || '';
  }
  function clearToken(){
    sessionStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(TOKEN_KEY);
  }
  function fmt(value){
    if (!value) return '-';
    try { return new Date(value).toLocaleString(); } catch (e) { return value; }
  }
  function levelBadge(level){
    return '<span class="badge ' + esc(level) + '">' + esc(level || '-') + '</span>';
  }

  async function api(path, options){
    options = options || {};
    var headers = options.headers || {};
    headers['Authorization'] = 'Bearer ' + token();
    if (options.body && typeof options.body !== 'string'){
      headers['Content-Type'] = 'application/json';
      options.body = JSON.stringify(options.body);
    }
    var response = await fetch(API + path, {
      method: options.method || 'GET',
      headers: headers,
      body: options.body
    });
    var data = {};
    try { data = await response.json(); } catch (e) { data = {}; }
    if (response.status === 401 || response.status === 403){
      clearToken();
      showLogin();
      throw new Error('登录已过期或无管理员权限');
    }
    if (!response.ok){
      throw new Error(data.detail || ('HTTP ' + response.status));
    }
    return data;
  }

  function showLogin(){
    $('#app').hidden = true;
    $('#login').hidden = false;
  }
  function showApp(){
    $('#login').hidden = true;
    $('#app').hidden = false;
    loadOverview();
    showTab('overview');
  }

  function showTab(name){
    state.tab = name;
    $$('nav button').forEach(function(btn){
      btn.className = btn.getAttribute('data-tab') === name ? 'active' : '';
    });
    $$('main section').forEach(function(sec){
      sec.className = sec.id === 'tab-' + name ? 'active' : '';
    });
    if (name === 'terms') loadTerms();
    if (name === 'judgments') loadJudgments();
    if (name === 'proposals') loadProposals();
  }

  async function loadOverview(){
    try {
      var data = await api('/overview');
      var today = data.today || {};
      $('#engine-badge').textContent = '引擎 v' + (data.engine_version || 0);
      $('#today-badge').textContent = '今日 ' + (today.total || 0) + ' 条｜待复核 ' + (data.pending_tasks || 0);
      var cards = [
        ['词条', (data.terms || {}).total || 0],
        ['待复核', data.pending_tasks || 0],
        ['待审提案', data.pending_proposals || 0],
        ['案例', data.cases || 0],
        ['审计事件', data.audit_events || 0],
        ['红队漏放', data.redteam_undetected || 0]
      ];
      $('#kpis').innerHTML = cards.map(function(item){
        return '<div class="card"><h3>' + esc(item[0]) + '</h3><div class="kpi">' + esc(item[1]) + '</div></div>';
      }).join('');
      renderTrend(data.trend || []);
      var top = data.top_terms || [];
      $('#top-terms').innerHTML = top.length ? top.map(function(item){
        return '<tr><td><strong>' + esc(item.term) + '</strong></td><td>' + levelBadge(item.level) +
          '</td><td>' + esc(item.hit_count) + '</td><td>' + esc(item.false_positive_count) +
          '</td><td>' + esc(item.confidence) + '</td></tr>';
      }).join('') : '<tr><td colspan="5" class="muted">暂无命中</td></tr>';
      var chain = data.audit || {};
      if (chain.ok === false){ toast('审计链异常，请立即排查'); }
    } catch (error) { toast(error.message); }
  }

  function renderTrend(items){
    if (!items.length){ $('#trend').innerHTML = '<span class="muted">暂无数据</span>'; return; }
    var max = 1;
    items.forEach(function(item){ max = Math.max(max, item.total || 0); });
    $('#trend').innerHTML = items.map(function(item){
      var height = Math.max(2, Math.round((item.total || 0) / max * 100));
      var color = (item.blocked || 0) > 0 ? '#FCA5A5' : '#BFDBFE';
      return '<div class="bar" style="height:' + height + '%;background:' + color + '"><span>' +
        esc(item.total) + '</span></div>';
    }).join('');
  }

  async function loadTerms(){
    var query = $('#term-query').value.trim();
    var level = $('#term-level').value;
    var path = '/terms?limit=100';
    if (query) path += '&query=' + encodeURIComponent(query);
    if (level) path += '&level=' + encodeURIComponent(level);
    try {
      var data = await api(path);
      $('#term-count').textContent = '共 ' + data.total + ' 条';
      $('#terms').innerHTML = data.items.map(function(item){
        var levels = ['blocked','masked','reviewed'].map(function(name){
          return '<option value="' + name + '"' + (item.level === name ? ' selected' : '') + '>' + name + '</option>';
        }).join('');
        return '<tr><td>' + esc(item.term_id) + '</td><td><strong>' + esc(item.term) + '</strong></td>' +
          '<td><select data-level-for="' + item.term_id + '">' + levels + '</select></td>' +
          '<td>' + esc(item.category) + '</td><td>' + esc(item.confidence) + '</td>' +
          '<td>' + esc(item.hit_count) + ' / ' + esc(item.false_positive_count) + '</td>' +
          '<td><button data-save="' + item.term_id + '">保存等级</button> ' +
          '<button data-variants="' + item.term_id + '">变体</button></td></tr>';
      }).join('') || '<tr><td colspan="7" class="muted">无词条</td></tr>';
      $$('#terms button[data-save]').forEach(function(btn){
        btn.onclick = async function(){
          var id = btn.getAttribute('data-save');
          var level = document.querySelector('select[data-level-for="' + id + '"]').value;
          try {
            await api('/terms/' + id, { method: 'PATCH', body: { level: level } });
            toast('已更新词条 ' + id);
            loadTerms();
          } catch (error) { toast(error.message); }
        };
      });
      $$('#terms button[data-variants]').forEach(function(btn){
        btn.onclick = function(){ loadVariants(btn.getAttribute('data-variants')); };
      });
    } catch (error) { toast(error.message); }
  }

  async function loadVariants(termId){
    var panel = $('#term-detail');
    panel.hidden = false;
    try {
      var data = await api('/terms/' + termId + '/variants');
      panel.innerHTML = '<div class="spread"><h3>词条 ' + esc(termId) + ' 的变体</h3><button id="variant-close">收起</button></div>' +
        '<div class="table-wrap mt"><table><thead><tr><th>ID</th><th>变体</th><th>类型</th><th>状态</th></tr></thead><tbody>' +
        (data.items.map(function(item){
          return '<tr><td>' + esc(item.variant_id) + '</td><td>' + esc(item.variant) + '</td><td>' + esc(item.kind) +
            '</td><td>' + esc(item.status) + '</td></tr>';
        }).join('') || '<tr><td colspan="4" class="muted">暂无变体</td></tr>') +
        '</tbody></table></div>' +
        '<div class="row mt"><input id="variant-text" placeholder="新增变体写法" style="flex:1">' +
        '<select id="variant-kind"><option>homophone</option><option>symbol</option><option>traditional</option><option>leet</option></select>' +
        '<button class="primary" id="variant-add">新增</button></div>';
      $('#variant-close').onclick = function(){ panel.hidden = true; };
      $('#variant-add').onclick = async function(){
        try {
          await api('/terms/' + termId + '/variants', {
            method: 'POST',
            body: { variant: $('#variant-text').value.trim(), kind: $('#variant-kind').value }
          });
          toast('变体已新增');
          loadVariants(termId);
        } catch (error) { toast(error.message); }
      };
    } catch (error) { toast(error.message); }
  }

  async function loadJudgments(){
    var decision = $('#judge-decision').value;
    var scene = $('#judge-scene').value;
    var path = '/judgments?limit=100';
    if (decision) path += '&decision=' + decision;
    if (scene) path += '&scene=' + scene;
    try {
      var data = await api(path);
      $('#judgments').innerHTML = data.items.map(function(item){
        return '<tr><td>' + esc(item.judgment_id) + '</td><td>' + esc(item.scene) + ' / ' + esc(item.source_id || '-') +
          '</td><td>' + esc(item.content_snippet) + '</td><td>' + levelBadge(item.level) + '</td><td>' + esc(item.decision) +
          '</td><td>' + esc(item.confidence) + '</td><td>' + esc(item.human_override || '-') +
          '</td><td><button data-judge="' + item.judgment_id + '">详情/复核</button></td></tr>';
      }).join('') || '<tr><td colspan="8" class="muted">暂无判定</td></tr>';
      $$('#judgments button[data-judge]').forEach(function(btn){
        btn.onclick = function(){ showJudgment(btn.getAttribute('data-judge')); };
      });
    } catch (error) { toast(error.message); }
  }

  async function showJudgment(id){
    try {
      var data = await api('/judgments/' + id);
      var canReview = !data.human_override;
      $('#detail-title').textContent = '判定 #' + data.judgment_id;
      $('#detail-body').innerHTML =
        '<p>场景：' + esc(data.scene) + '｜等级：' + levelBadge(data.level) + '｜处置：' + esc(data.decision) +
        '｜置信度：' + esc(data.confidence) + '</p>' +
        '<p>摘要：' + esc(data.content_snippet) + '</p>' +
        '<h3>证据链</h3><pre>' + esc(JSON.stringify(data.evidence, null, 2)) + '</pre>' +
        (canReview ? '<div class="row mt"><button class="primary" id="ov-confirm">确认违规</button>' +
          '<button class="danger" id="ov-reject">判定误判</button></div>' : '<p class="muted">已复核：' + esc(data.human_override) + '</p>');
      $('#detail').className = 'detail show';
      if (canReview){
        $('#ov-confirm').onclick = function(){ override(id, 'confirm'); };
        $('#ov-reject').onclick = function(){ override(id, 'reject'); };
      }
    } catch (error) { toast(error.message); }
  }

  async function override(id, action){
    var reason = prompt('复核备注（可留空）') || '';
    try {
      await api('/judgments/' + id + '/override', { method: 'POST', body: { action: action, reason: reason } });
      toast('复核已提交');
      $('#detail').className = 'detail';
      loadJudgments();
      loadOverview();
    } catch (error) { toast(error.message); }
  }

  async function loadProposals(){
    var status = $('#proposal-status').value;
    var kind = $('#proposal-kind').value;
    var path = '/proposals?limit=100';
    if (status) path += '&status=' + status;
    if (kind) path += '&kind=' + kind;
    try {
      var data = await api(path);
      $('#proposals').innerHTML = data.items.map(function(item){
        var actions = item.status === 'pending'
          ? '<button class="primary" data-approve="' + item.proposal_id + '">通过</button> <button class="danger" data-reject="' + item.proposal_id + '">拒绝</button>'
          : '<span class="muted">' + esc(item.status) + '</span>';
        return '<tr><td>' + esc(item.proposal_id) + '</td><td>' + esc(item.kind) + '</td><td>' + esc(item.title) +
          '</td><td>' + esc(item.proposer) + '</td><td>' + esc(item.status) + '</td><td>' + actions + '</td></tr>';
      }).join('') || '<tr><td colspan="6" class="muted">暂无提案</td></tr>';
      $$('#proposals button[data-approve]').forEach(function(btn){
        btn.onclick = function(){ reviewProposal(btn.getAttribute('data-approve'), 'approve'); };
      });
      $$('#proposals button[data-reject]').forEach(function(btn){
        btn.onclick = function(){ reviewProposal(btn.getAttribute('data-reject'), 'reject'); };
      });
    } catch (error) { toast(error.message); }
  }

  async function reviewProposal(id, action){
    var reason = prompt(action === 'approve' ? '通过备注（可留空）' : '拒绝原因（建议填写）') || '';
    try {
      await api('/proposals/' + id + '/' + action, { method: 'POST', body: { action: 'confirm', reason: reason } });
      toast(action === 'approve' ? '提案已写入知识库' : '提案已拒绝');
      loadProposals();
      loadOverview();
    } catch (error) { toast(error.message); }
  }

  async function loadGraph(){
    var type = $('#graph-type').value;
    var id = $('#graph-id').value.trim();
    var depth = $('#graph-depth').value;
    if (!id){ toast('请输入节点 ID'); return; }
    try {
      var data = await api('/graph?node_type=' + encodeURIComponent(type) + '&node_id=' + encodeURIComponent(id) + '&depth=' + depth);
      $('#graph-nodes').innerHTML = data.nodes.map(function(node){
        return '<div class="row" style="justify-content:space-between;border-bottom:1px solid var(--line);padding:4px 0">' +
          '<span>' + esc(node.label) + '</span><span class="hint">' + esc(node.type) + ':' + esc(node.id) + '</span></div>';
      }).join('');
      $('#graph-edges').innerHTML = data.edges.map(function(edge){
        return '<div class="hint" style="padding:4px 0;border-bottom:1px solid var(--line)">' +
          esc(edge.src.type) + ':' + esc(edge.src.id) + ' -[' + esc(edge.rel) + ']-> ' +
          esc(edge.dst.type) + ':' + esc(edge.dst.id) + '</div>';
      }).join('') || '<span class="muted">无关系</span>';
    } catch (error) { toast(error.message); }
  }

  function showJson(sel, data){
    var node = $(sel);
    node.hidden = false;
    node.textContent = JSON.stringify(data, null, 2);
  }

  async function runTool(sel, fn){
    try { showJson(sel, await fn()); toast('完成'); }
    catch (error) { toast(error.message); }
  }

  function bind(){
    $('#login-btn').onclick = async function(){
      var body = new URLSearchParams();
      body.set('username', $('#username').value.trim());
      body.set('password', $('#password').value);
      body.set('client_type', 'web');
      try {
        var response = await fetch('/api/auth/login', { method: 'POST', body: body });
        var data = await response.json();
        if (!response.ok) throw new Error(data.detail || '登录失败');
        saveToken(data.access_token);
        showApp();
      } catch (error) { toast(error.message); }
    };
    $('#token-btn').onclick = function(){
      var value = $('#token-input').value.trim();
      if (!value){ toast('请粘贴 access_token'); return; }
      saveToken(value);
      showApp();
    };
    $('#password').onkeydown = function(event){ if (event.key === 'Enter') $('#login-btn').click(); };
    $('#logout-btn').onclick = function(){ clearToken(); showLogin(); };
    $('#refresh-btn').onclick = function(){ loadOverview(); };
    $$('nav button').forEach(function(btn){
      btn.onclick = function(){ showTab(btn.getAttribute('data-tab')); };
    });
    $('#term-search').onclick = loadTerms;
    $('#judge-search').onclick = loadJudgments;
    $('#proposal-search').onclick = loadProposals;
    $('#create-term').onclick = async function(){
      var payload = {
        term: $('#new-term').value.trim(),
        level: $('#new-level').value,
        category: $('#new-category').value.trim() || 'other',
        confidence: parseFloat($('#new-confidence').value || '0.8')
      };
      if (!payload.term){ toast('请填写词条'); return; }
      try {
        await api('/terms', { method: 'POST', body: payload });
        toast('词条已新增');
        $('#new-term').value = '';
        loadTerms();
        loadOverview();
      } catch (error) { toast(error.message); }
    };
    $('#graph-load').onclick = loadGraph;
    $('#detail-close').onclick = function(){ $('#detail').className = 'detail'; };
    $('#detect-btn').onclick = function(){
      runTool('#detect-result', function(){
        return api('/detect', { method: 'POST', body: { text: $('#detect-text').value, persist: false } });
      });
    };
    $('#redteam-btn').onclick = function(){
      runTool('#tool-result', function(){ return api('/redteam/run', { method: 'POST', body: { limit: 30 } }); });
    };
    $('#reconcile-btn').onclick = function(){
      runTool('#tool-result', function(){ return api('/reconcile', { method: 'POST', body: {} }); });
    };
    $('#reload-btn').onclick = function(){
      runTool('#tool-result', function(){ return api('/reload', { method: 'POST', body: {} }); });
    };
    $('#seed-btn').onclick = function(){
      runTool('#tool-result', function(){ return api('/seed', { method: 'POST', body: {} }); });
    };
    $('#export-btn').onclick = function(){
      runTool('#obsidian-result', function(){ return api('/obsidian/export', { method: 'POST', body: {} }); });
    };
    $('#import-btn').onclick = function(){
      runTool('#obsidian-result', function(){ return api('/obsidian/import', { method: 'POST', body: {} }); });
    };
    $('#audit-btn').onclick = function(){
      runTool('#audit-result', function(){ return api('/audit/verify'); });
    };
  }

  bind();
  if (token()){ showApp(); } else { showLogin(); }
})();
</script>
</body>
</html>
"""
