---
type: dashboard
status: published
---
# 系统总览看板 · __VAULT__

> **当前 Vault：** `__VAULT__`  
> 金句、新闻、招考已经是三个完全独立的 Obsidian Vault。Dataview 只能统计当前 Vault，不能跨库读取。  
> 今天的数字只代表当前库；其余两个库请分别打开各自的 `00-系统总览看板.md`。

```dataviewjs
const arr = dv.pages().array().filter(p => {
  const t = String(p.type || "").toLowerCase();
  return ["quote", "news", "job", "recruitment"].includes(t);
});

function statusOf(p) {
  const s = String(p.status ?? p.review_status ?? "").toLowerCase();
  if (["approved", "published", "已发布"].includes(s)) return "published";
  if (["rejected", "已拒绝"].includes(s)) return "rejected";
  if (["pending", "review", "待审核"].includes(s)) return "pending";
  return "inbox";
}

function dateKey(value) {
  if (!value) return "";
  if (value.toFormat) return value.toFormat("yyyy-MM-dd");
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "";
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return y + "-" + m + "-" + day;
}

const statuses = arr.map(p => statusOf(p));
const total = arr.length;
const pending = statuses.filter(s => s === "pending").length;
const published = statuses.filter(s => s === "published").length;
const rejected = statuses.filter(s => s === "rejected").length;
const today = dateKey(dv.date("today"));
let todayCount = 0;
for (const p of arr) {
  if (dateKey(p.create_time || p.file.ctime) === today) todayCount++;
}

const css = [
  ".dash-cards { display:flex; gap:12px; flex-wrap:wrap; margin:12px 0 24px; }",
  ".dash-card { flex:1 1 160px; min-width:160px; padding:16px 18px; border-radius:14px; background:linear-gradient(135deg,#163a5f,#2f5d50); color:#fff; box-shadow:0 8px 20px rgba(22,58,95,.16); }",
  ".dash-card .dash-value { font-size:30px; line-height:1.1; font-weight:800; }",
  ".dash-card .dash-label { margin-top:6px; font-size:12px; opacity:.82; }",
  ".dash-note { color:#8894a3; font-size:12px; margin:4px 0 18px; }",
  ".heatmap-wrap { overflow-x:auto; padding:8px 0 16px; }",
  ".heatmap { display:grid; grid-template-rows:repeat(7,14px); grid-auto-flow:column; grid-auto-columns:14px; gap:4px; width:max-content; }",
  ".heat-cell { width:14px; height:14px; border-radius:3px; background:#edf1ee; }",
  ".heat-legend { display:flex; align-items:center; gap:5px; margin-top:8px; color:#8894a3; font-size:11px; }",
  ".heat-legend .heat-cell { width:12px; height:12px; }",
  ".topic-row { display:grid; grid-template-columns:160px 1fr 44px; gap:10px; align-items:center; margin:7px 0; font-size:12px; color:#59635c; }",
  ".topic-bar { height:10px; border-radius:999px; background:#e8ede9; overflow:hidden; }",
  ".topic-bar > i { display:block; height:100%; border-radius:999px; background:#2f5d50; }",
  ".topic-count { text-align:right; color:#8894a3; }",
  ".health-row { margin:10px 0; }",
  ".health-label { display:flex; justify-content:space-between; color:#59635c; font-size:12px; margin-bottom:5px; }",
  ".health-track { height:12px; border-radius:999px; background:#e8ede9; overflow:hidden; }",
  ".health-track > i { display:block; height:100%; background:#2f5d50; }",
  ".health-pending > i { background:#c8763f; }",
  ".health-rejected > i { background:#c41e3a; }"
].join("\n");
dv.el("style", css);

const cards = dv.el("div", "", { cls: "dash-cards" });
function card(value, label) {
  const box = cards.createEl("div", { cls: "dash-card" });
  box.createEl("div", { cls: "dash-value", text: String(value) });
  box.createEl("div", { cls: "dash-label", text: label });
}
card(todayCount, "今日新增素材");
card(pending, "当前待审核");
card(published, "累计已发布");
dv.el("div", "统计口径：当前 Vault 中 frontmatter.type 为 quote / news / job 的 Markdown；日期优先使用 create_time，缺失时使用文件创建时间。", { cls: "dash-note" });

dv.header(2, "近 90 天活跃热力图");
const daily = {};
for (const p of arr) {
  const key = dateKey(p.create_time || p.file.ctime);
  if (key) daily[key] = (daily[key] || 0) + 1;
}
const heatWrap = dv.el("div", "", { cls: "heatmap-wrap" });
const heat = heatWrap.createEl("div", { cls: "heatmap" });
const todayDate = new Date();
todayDate.setHours(0, 0, 0, 0);
const start = new Date(todayDate);
start.setDate(start.getDate() - 89);
for (let i = 0; i < 90; i++) {
  const d = new Date(start);
  d.setDate(start.getDate() + i);
  const key = dateKey(d);
  const count = daily[key] || 0;
  const cell = heat.createEl("div", { cls: "heat-cell" });
  cell.title = key + "：" + count + " 篇";
  if (count >= 10) cell.style.background = "#1f4d3f";
  else if (count >= 5) cell.style.background = "#2f6b4b";
  else if (count >= 2) cell.style.background = "#6da487";
  else if (count === 1) cell.style.background = "#b9d2c2";
}
const legend = heatWrap.createEl("div", { cls: "heat-legend" });
legend.createEl("span", { text: "少" });
for (const color of ["#edf1ee", "#b9d2c2", "#6da487", "#2f6b4b", "#1f4d3f"]) {
  const c = legend.createEl("div", { cls: "heat-cell" });
  c.style.background = color;
}
legend.createEl("span", { text: "多" });

dv.header(2, "主题 / 分类排行");
const topics = {};
for (const p of arr) {
  const raw = p.topics ?? p.topic ?? p.category ?? p.type ?? "未分类";
  if (Array.isArray(raw)) {
    for (const v of raw) topics[String(v)] = (topics[String(v)] || 0) + 1;
  } else {
    for (const v of String(raw).split(/[,，、]/)) {
      const k = v.trim() || "未分类";
      topics[k] = (topics[k] || 0) + 1;
    }
  }
}
const topicRows = Object.entries(topics).sort((a, b) => b[1] - a[1]).slice(0, 12);
const maxTopic = Math.max(1, ...topicRows.map(([, n]) => n));
for (const [name, count] of topicRows) {
  const row = dv.el("div", "", { cls: "topic-row" });
  row.createEl("span", { text: name });
  const bar = row.createEl("div", { cls: "topic-bar" });
  const fill = bar.createEl("i");
  fill.style.width = Math.max(4, count / maxTopic * 100) + "%";
  row.createEl("span", { cls: "topic-count", text: String(count) });
}

dv.header(2, "审核流水线健康度");
const reviewed = published + rejected;
const completion = total ? Math.round(reviewed / total * 100) : 0;
const pendingPct = total ? Math.round(pending / total * 100) : 0;
const rejectedPct = total ? Math.round(rejected / total * 100) : 0;
function health(label, value, cls) {
  const row = dv.el("div", "", { cls: "health-row" });
  const head = row.createEl("div", { cls: "health-label" });
  head.createEl("span", { text: label });
  head.createEl("span", { text: value + "%" });
  const track = row.createEl("div", { cls: "health-track" });
  const fill = track.createEl("i", { cls });
  fill.style.width = Math.max(0, Math.min(100, value)) + "%";
}
health("审核完成率", completion, "");
health("待审核占比", pendingPct, "health-pending");
health("已拒绝占比", rejectedPct, "health-rejected");
dv.paragraph("已审核：" + reviewed + " / " + total + "（" + completion + "%）；待审核：" + pending + "；已拒绝：" + rejected + "。");
```
