/**
 * 项目健康度统一守卫（接入 prebuild）。
 *
 * 覆盖四类长期稳定性问题，分级如下：
 *   1. 图标导入合法性   —— 阻断：未知 @vtj/icons 导出会在 vite build 时才炸，且报错难定位
 *   2. typecheck 错误基线 —— 阻断：复用 verify-typecheck-baseline，仅在出现新错误时失败
 *   3. 孤立文件扫描     —— 警告：.vue 未被任何路由引用（VTJ Provider 可注册动态路由，故不阻断）
 *   4. VTJ 版本漂移     —— 警告：useProvider version 与 DSL __VERSION__ 不一致，手改会被设计器覆盖
 *
 * 用法：
 *   node scripts/verify-project-health.mjs              # 完整检查
 *   node scripts/verify-project-health.mjs --skip-typecheck   # 跳过较慢的 typecheck 基线检查
 */

import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { verifyTypecheck } from './verify-typecheck-baseline.mjs';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');

const ICON_IMPORT_RE = /import\s*\{([^}]*)\}\s*from\s*['"]@vtj\/icons['"]/g;
const PROVIDER_VERSION_RE = /useProvider\(\s*\{[^}]*?version:\s*'(\d+)'/;

const problems = [];
const warnings = [];

function rel(p) {
  return relative(root, p).replace(/\\/g, '/');
}

function walkVue(dir, out = []) {
  if (!existsSync(dir)) return out;
  for (const name of readdirSync(dir)) {
    if (name === 'node_modules') continue;
    const p = join(dir, name);
    const st = statSync(p);
    if (st.isDirectory()) walkVue(p, out);
    else if (name.endsWith('.vue')) out.push(p);
  }
  return out;
}

function allVueFiles() {
  return [...walkVue(join(root, '.vtj/vue')), ...walkVue(join(root, 'src'))];
}

/**
 * 页面级 .vue：这些文件理应被路由引用，未被引用即为可疑死文件。
 * 刻意排除 src/App.vue（根组件）、src/components、src/layouts 等本就不经路由引用的位置，
 * 否则误报会稀释真实信号。
 */
function routableVueFiles() {
  return [...walkVue(join(root, '.vtj/vue')), ...walkVue(join(root, 'src/views'))];
}

// ---------------------------------------------------------------- 检查 1（阻断）
async function checkIconImports() {
  let valid;
  try {
    valid = new Set(Object.keys(await import('@vtj/icons')));
  } catch (error) {
    problems.push(`[icons] 无法加载 @vtj/icons：${error.message}`);
    return;
  }

  const missing = [];
  for (const file of allVueFiles()) {
    const src = readFileSync(file, 'utf8');
    ICON_IMPORT_RE.lastIndex = 0;
    let m;
    while ((m = ICON_IMPORT_RE.exec(src))) {
      for (const part of m[1].split(',')) {
        const t = part.trim();
        if (!t) continue;
        const name = t.split(/\s+as\s+/)[0].trim();
        if (!valid.has(name)) missing.push({ file: rel(file), name });
      }
    }
  }

  if (missing.length) {
    for (const { file, name } of missing) {
      const lower = name.toLowerCase();
      const candidates = [...valid]
        .filter((v) => v.toLowerCase().includes(lower) || lower.includes(v.toLowerCase()))
        .slice(0, 3);
      problems.push(
        `[icons] ${file}: "${name}" 不是 @vtj/icons 的导出` +
          (candidates.length ? `；可能想用：${candidates.join(' / ')}` : '')
      );
    }
  } else {
    console.log(`[1/4] 图标导入合法性：通过（已扫描 ${allVueFiles().length} 个 .vue）`);
  }
}

// ---------------------------------------------------------------- 检查 3（警告）
function checkOrphanFiles() {
  const referenced = new Set();
  const routerFiles = [join(root, 'src/router/index.ts'), join(root, '.vtj/router.js')];

  for (const rf of routerFiles) {
    if (!existsSync(rf)) continue;
    const src = readFileSync(rf, 'utf8');
    // 匹配三种引用形式：@/views/x.vue、$vtj/vue/x.vue、./vue/x.vue
    for (const m of src.matchAll(/['"]([^'"]*\.vue)['"]/g)) {
      referenced.add(m[1].split('/').pop());
    }
  }

  const orphans = [];
  for (const file of routableVueFiles()) {
    const name = rel(file).split('/').pop();
    if (!referenced.has(name)) orphans.push(rel(file));
  }

  // src/vtj 是非标准 VTJ 输出目录，历史遗留容易堆积无人引用的副本，单独提示
  for (const file of walkVue(join(root, 'src/vtj'))) {
    orphans.push(`${rel(file)}  (非标准 VTJ 输出目录，请确认是否为遗留副本)`);
  }

  if (orphans.length) {
    for (const o of orphans) {
      warnings.push(`[orphans] 未被 src/router 或 .vtj/router 引用：${o}`);
    }
  } else {
    console.log('[3/4] 孤立文件扫描：无孤立 .vue');
  }
}

// ---------------------------------------------------------------- 检查 4（警告）
function checkVtjVersionDrift() {
  const dir = join(root, '.vtj/vue');
  if (!existsSync(dir)) return;

  let drifted = 0;
  let missingDsl = 0;

  for (const file of walkVue(dir)) {
    const src = readFileSync(file, 'utf8');
    const m = src.match(PROVIDER_VERSION_RE);
    if (!m) continue;

    const name = rel(file).split('/').pop().replace(/\.vue$/, '');
    const dslPath = join(root, '.vtj/files', `${name}.json`);
    if (!existsSync(dslPath)) {
      missingDsl += 1;
      warnings.push(`[vtj-drift] ${rel(file)}：找不到对应 DSL .vtj/files/${name}.json，无法比对版本`);
      continue;
    }

    let dslVersion;
    try {
      const dsl = JSON.parse(readFileSync(dslPath, 'utf8'));
      dslVersion = dsl.__VERSION__;
    } catch {
      dslVersion = undefined;
    }

    if (dslVersion === undefined) {
      warnings.push(`[vtj-drift] ${rel(file)}：DSL 缺少 __VERSION__ 字段，无法比对`);
    } else if (String(dslVersion) !== m[1]) {
      drifted += 1;
      warnings.push(
        `[vtj-drift] ${rel(file)}：.vue version=${m[1]} 与 DSL __VERSION__=${dslVersion} 不一致，` +
          '该文件已被手工修改，下次在 VTJ 设计器保存会被覆盖'
      );
    }
  }

  if (!drifted && !missingDsl) {
    console.log('[4/4] VTJ 版本漂移：无漂移');
  }
}

// ---------------------------------------------------------------- 主流程
async function main() {
  const skipTypecheck = process.argv.includes('--skip-typecheck');

  await checkIconImports();

  if (skipTypecheck) {
    console.log('[2/4] typecheck 错误基线：已跳过（--skip-typecheck）');
  } else {
    const r = verifyTypecheck();
    if (r.ok) {
      console.log(`[2/4] typecheck 错误基线：通过（当前 ${r.total} 项，与基线一致）`);
    } else {
      problems.push('[typecheck] 出现新增类型错误，详见上方输出');
    }
  }

  checkOrphanFiles();
  checkVtjVersionDrift();

  if (warnings.length) {
    console.log('');
    console.log(`警告 ${warnings.length} 条（不阻断构建）：`);
    for (const w of warnings) console.log(`  ! ${w}`);
  }

  if (problems.length) {
    console.error('');
    console.error(`阻断问题 ${problems.length} 条：`);
    for (const p of problems) console.error(`  x ${p}`);
    console.error('');
    console.error('项目健康度检查未通过，已阻断。');
    process.exitCode = 1;
    return;
  }

  console.log('');
  console.log('项目健康度检查通过（阻断类 0 项）。');
}

main().catch((error) => {
  console.error('项目健康度检查执行失败：', error);
  process.exitCode = 1;
});
