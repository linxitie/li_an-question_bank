/**
 * typecheck 错误基线校验。
 *
 * 背景：`.vtj/vue/teacher_papers.vue` 由 VTJ codegen 生成，其无类型 `reactive({...})`
 * 会导致模板类型推断退化，产生 8 项 TS2365/TS2345 噪音。这些错误无法从配置层消除
 * （已实测 `vueCompilerOptions.strictTemplates: false` 对它们完全无效），也不宜用
 * `// @ts-nocheck` 屏蔽（会连带掩盖该文件未来的真实缺陷）。
 *
 * 机制：将已知噪音记入 `.typecheck-baseline.json`，本脚本仅在出现「新增错误」或
 * 「新增受影响文件」时失败，从而在不掩盖真实问题的前提下让 typecheck 长期可用。
 *
 * 归一化：以 `文件 + 错误码 + 行号` 为键，丢弃列号与消息正文，避免无关改动引发误报。
 *
 * 用法：
 *   node scripts/verify-typecheck-baseline.mjs            # 校验
 *   node scripts/verify-typecheck-baseline.mjs --update   # 重新生成基线
 */

import { spawnSync } from 'node:child_process';
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const baselinePath = resolve(root, '.typecheck-baseline.json');
const TSCONFIG = 'tsconfig.json';

// 形如： some/file.vue(113,45): error TS2365: Operator '+' cannot be ...
// 扩展名必须紧邻左括号，避免把 `.vtj/vue/` 这类含 ".vue" 的目录名误判为扩展名边界
const ERROR_LINE = /^(.+?\.(?:vue|tsx|ts|jsx|js|mjs))\((\d+),(\d+)\):\s+error\s+(TS\d+):/;

function entryKey(entry) {
  return `${entry.file}(${entry.line}) ${entry.code}`;
}

export function runTypecheck() {
  const result = spawnSync(
    process.execPath,
    ['node_modules/vue-tsc/bin/vue-tsc.js', '--noEmit', '-p', TSCONFIG],
    { cwd: root, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 }
  );

  const output = `${result.stdout || ''}\n${result.stderr || ''}`;
  const entries = [];

  for (const rawLine of output.split(/\r?\n/)) {
    const line = rawLine.trim();
    const m = line.match(ERROR_LINE);
    if (!m) continue;
    // vue-tsc 输出绝对路径；统一裁剪为相对仓库根目录并转正斜杠
    let file = m[1].trim().replace(/\\/g, '/');
    const rel = file.indexOf('/src/') >= 0 ? file.slice(file.indexOf('/src/') + 1)
      : file.indexOf('/.vtj/') >= 0 ? file.slice(file.indexOf('/.vtj/') + 1)
      : file;
    file = rel.replace(/^[A-Za-z]:\//, '');
    entries.push({ file, line: Number(m[2]), code: m[4] });
  }

  // 去重后按文件/行/码稳定排序，保证基线文件不产生无意义 diff
  const seen = new Set();
  const unique = [];
  for (const e of entries.sort((a, b) =>
    a.file === b.file ? a.line - b.line || a.code.localeCompare(b.code) : a.file.localeCompare(b.file)
  )) {
    const k = entryKey(e);
    if (seen.has(k)) continue;
    seen.add(k);
    unique.push(e);
  }

  return { entries: unique, output };
}

function writeBaseline(entries) {
  const payload = {
    generatedAt: new Date().toISOString(),
    command: `vue-tsc --noEmit -p ${TSCONFIG}`,
    note: '仅记录无法从配置层消除的 codegen 噪音；新增错误会使 verify-typecheck-baseline 失败',
    totalErrors: entries.length,
    entries,
  };
  writeFileSync(baselinePath, `${JSON.stringify(payload, null, 2)}\n`, 'utf8');
}

function readBaseline() {
  if (!existsSync(baselinePath)) return null;
  try {
    return JSON.parse(readFileSync(baselinePath, 'utf8'));
  } catch (error) {
    console.error(`[typecheck-baseline] 基线文件无法解析：${baselinePath}`);
    console.error(`  ${error.message}`);
    return null;
  }
}

export function verifyTypecheck({ update = false } = {}) {
  const { entries } = runTypecheck();
  const baseline = readBaseline();

  if (update) {
    writeBaseline(entries);
    console.log(`[typecheck-baseline] 已更新基线：${entries.length} 项 -> .typecheck-baseline.json`);
    return { ok: true, created: true, updated: true, added: [], removed: [], total: entries.length };
  }

  if (!baseline || !Array.isArray(baseline.entries)) {
    writeBaseline(entries);
    console.log(
      `[typecheck-baseline] 首次建立基线：${entries.length} 项已写入 .typecheck-baseline.json`
    );
    if (entries.length) {
      console.log('[typecheck-baseline] 请人工复核下列条目是否均可接受为已知噪音：');
      for (const e of entries) console.log(`  ${entryKey(e)}`);
    }
    return { ok: true, created: true, updated: false, added: [], removed: [], total: entries.length };
  }

  const baseSet = new Set(baseline.entries.map(entryKey));
  const curSet = new Set(entries.map(entryKey));

  const added = entries.filter((e) => !baseSet.has(entryKey(e)));
  const removed = baseline.entries.filter((e) => !curSet.has(entryKey(e)));

  if (removed.length) {
    console.log(`[typecheck-baseline] 以下 ${removed.length} 项已不再出现（可清理基线）：`);
    for (const e of removed) console.log(`  - ${entryKey(e)}`);
  }

  if (added.length) {
    console.error(
      `[typecheck-baseline] 检出 ${added.length} 项新增类型错误（基线 ${baseline.entries.length} 项 -> 当前 ${entries.length} 项）：`
    );
    const files = [...new Set(added.map((e) => e.file))];
    console.error(`  受影响文件：${files.join(', ')}`);
    for (const e of added) console.error(`  + ${entryKey(e)}`);
    console.error('  处理方式：修复代码；若确属无法消除的 codegen 噪音，执行');
    console.error('    node scripts/verify-typecheck-baseline.mjs --update');
    return { ok: false, created: false, updated: false, added, removed, total: entries.length };
  }

  console.log(
    `[typecheck-baseline] 通过：零新增错误（当前 ${entries.length} 项，与基线一致）`
  );
  return { ok: true, created: false, updated: false, added: [], removed, total: entries.length };
}

const invokedDirectly =
  process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url));

if (invokedDirectly) {
  const result = verifyTypecheck({ update: process.argv.includes('--update') });
  if (!result.ok) process.exitCode = 1;
}
