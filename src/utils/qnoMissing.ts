/**
 * 从导题草稿的体检告警里解析「题号缺号 N 个：[46, 86, 92]」（Q3，2026-11-15）。
 *
 * 为什么单独抽纯函数：
 *   · 抽屉里那条告警是**后端拼好的字符串**（`splitter.draft_warnings`），前端不该再拼一遍；
 *   · 解析失败要能优雅退回"原文照旧显示"，所以返回 `null` 而不是空数组；
 *   · 纯函数可单测，不必挂载组件。
 */
export interface MissingQnos {
  /** 后端报的缺号个数（用于文案「题号缺号 N 个」） */
  count: number;
  /** 具体题号（去重、升序；用于 chips 与上一题/下一题） */
  nos: number[];
}

const MISSING_RE = /题号缺号\s*(\d+)\s*个\s*[：:]\s*[\[［]([^\]］]*)[\]］]/;

/**
 * `题号缺号 3 个：[46, 86, 92]` → `{ count: 3, nos: [46, 86, 92] }`；
 * 不含该告警 / 方括号里没有合法题号 → `null`（调用方按普通文本渲染）。
 */
export function parseMissingQnos(warning: string): MissingQnos | null {
  const m = MISSING_RE.exec(warning || '');
  if (!m) return null;
  const nos = (m[2] || '')
    .split(/[,，、\s]+/)
    .map((x) => Number(x))
    .filter((n) => Number.isInteger(n) && n > 0 && n <= 999);
  if (!nos.length) return null;
  const unique = [...new Set(nos)].sort((a, b) => a - b);
  return { count: Number(m[1]) || unique.length, nos: unique };
}
