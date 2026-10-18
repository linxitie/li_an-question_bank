#!/usr/bin/env node
/**
 * 模块化约束校验脚本（P1-02）
 *
 * 三项检查：
 *   1. package.json 中 8 个 VTJ 包版本必须等于锁定值。
 *   2. src/router/index.ts 中所有动态 import 目标必须存在（92 处），
 *      其中 `$vtj/vue/<id>.vue` 映射到 `.vtj/vue/<id>.vue`，
 *      `@/...` 映射到 `src/...`。
 *   3. src/modules/<域>/** 中禁止出现 `@/modules/<其他域>` 的跨域 import。
 *      `--domain <name>` 可限定只扫描单个域。
 *
 * 退出码：0 = 全部通过；1 = 存在违规。
 * 无外部依赖，纯 Node ESM。
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');

const VTJ_LOCKED_VERSIONS = {
  '@vtj/web': '0.16.35',
  '@vtj/ui': '0.16.35',
  '@vtj/charts': '0.16.35',
  '@vtj/icons': '0.16.35',
  '@vtj/utils': '0.16.35',
  '@vtj/materials': '0.16.35',
  '@vtj/pro': '0.16.35',
  '@vtj/cli': '0.12.19',
};

const EXPECTED_DYNAMIC_IMPORTS = 92;

const violations = [];

function fail(message) {
  violations.push(message);
}

function readText(relPath) {
  return fs.readFileSync(path.join(ROOT, relPath), 'utf8');
}

function countLines(text) {
  return text.split(/\r?\n/).length;
}

// ---------------------------------------------------------------------------
// 检查 1：VTJ 包版本锁定
// ---------------------------------------------------------------------------
function checkVtjVersions() {
  const pkg = JSON.parse(readText('package.json'));
  const deps = pkg.dependencies || {};
  const devDeps = pkg.devDependencies || {};

  for (const [name, expected] of Object.entries(VTJ_LOCKED_VERSIONS)) {
    const actual = deps[name] ?? devDeps[name];
    if (actual === undefined) {
      fail(`[版本] package.json 缺少 ${name}（期望 ${expected}）`);
    } else if (actual !== expected) {
      fail(`[版本] ${name} 期望 ${expected}，实际 ${actual}`);
    }
  }
}

// ---------------------------------------------------------------------------
// 检查 2：router 动态 import 目标存在
// ---------------------------------------------------------------------------
function checkRouterImports() {
  const routerRel = 'src/router/index.ts';
  const text = readText(routerRel);
  const lineOf = (index) => text.slice(0, index).split(/\r?\n/).length;

  const dynamicImportRe = /import\s*\(\s*['"]([^'"]+)['"]\s*\)/g;
  let match;
  let total = 0;
  let vtjCount = 0;

  while ((match = dynamicImportRe.exec(text)) !== null) {
    const target = match[1];
    total += 1;

    let resolved;
    if (target.startsWith('$vtj/vue/')) {
      vtjCount += 1;
      resolved = path.join(ROOT, '.vtj', 'vue', target.slice('$vtj/vue/'.length));
    } else if (target.startsWith('@/')) {
      resolved = path.join(ROOT, 'src', target.slice('@/'.length));
    } else if (target.startsWith('.')) {
      resolved = path.resolve(path.dirname(path.join(ROOT, routerRel)), target);
    } else {
      continue; // 裸模块名（第三方包），跳过
    }

    if (!fs.existsSync(resolved)) {
      fail(`[路由] ${routerRel}:${lineOf(match.index)} 动态 import 目标不存在: ${target}`);
    }
  }

  if (total !== EXPECTED_DYNAMIC_IMPORTS) {
    fail(
      `[路由] 期望 ${EXPECTED_DYNAMIC_IMPORTS} 处动态 import，实际 ${total} 处` +
        `（其中 $vtj/vue ${vtjCount} 处）`
    );
  }
}

// ---------------------------------------------------------------------------
// 检查 3：模块间禁止跨域 import
// ---------------------------------------------------------------------------
function listFiles(dir) {
  const out = [];
  if (!fs.existsSync(dir)) return out;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      out.push(...listFiles(full));
    } else if (/\.(ts|tsx|js|jsx|mjs|cjs|vue)$/.test(entry.name)) {
      out.push(full);
    }
  }
  return out;
}

function checkDomainImports(domainFilter) {
  const modulesDir = path.join(ROOT, 'src', 'modules');
  if (!fs.existsSync(modulesDir)) {
    return; // 尚未创建模块目录，无违规
  }

  const importRe = /(?:import\s[^'"]*from\s*|import\s*\(\s*|require\s*\(\s*)['"]@\/modules\/([^'"]+)['"]/g;

  let domains;
  if (domainFilter) {
    if (!fs.existsSync(path.join(modulesDir, domainFilter))) {
      fail(`[模块] --domain ${domainFilter} 指定的域不存在: src/modules/${domainFilter}`);
      return;
    }
    domains = [domainFilter];
  } else {
    domains = fs
      .readdirSync(modulesDir, { withFileTypes: true })
      .filter((e) => e.isDirectory())
      .map((e) => e.name);
  }

  for (const domain of domains) {
    const files = listFiles(path.join(modulesDir, domain));
    for (const file of files) {
      const text = fs.readFileSync(file, 'utf8');
      const rel = path.relative(ROOT, file).replace(/\\/g, '/');
      let match;
      importRe.lastIndex = 0;
      while ((match = importRe.exec(text)) !== null) {
        const importedPath = match[1];
        const otherDomain = importedPath.split('/')[0];
        if (otherDomain && otherDomain !== domain) {
          const line = text.slice(0, match.index).split(/\r?\n/).length;
          fail(`[模块] ${rel}:${line} 跨域 import: @/modules/${importedPath}（域 ${domain} → ${otherDomain}）`);
        }
      }
    }
  }
}

// ---------------------------------------------------------------------------
// 入口
// ---------------------------------------------------------------------------
function parseArgs(argv) {
  let domain = null;
  for (let i = 0; i < argv.length; i += 1) {
    if (argv[i] === '--domain') {
      domain = argv[i + 1];
      i += 1;
    } else if (argv[i].startsWith('--domain=')) {
      domain = argv[i].slice('--domain='.length);
    } else if (argv[i] === '--help' || argv[i] === '-h') {
      console.log('用法: node scripts/verify-modularization-constraints.mjs [--domain <name>]');
      process.exit(0);
    }
  }
  return { domain };
}

function main() {
  const { domain } = parseArgs(process.argv.slice(2));

  checkVtjVersions();
  checkRouterImports();
  checkDomainImports(domain);

  if (violations.length > 0) {
    console.error(`模块化约束校验失败，共 ${violations.length} 项违规：`);
    for (const v of violations) console.error(`  - ${v}`);
    process.exit(1);
  }

  console.log('模块化约束校验通过：');
  console.log(`  - VTJ 包版本锁定 ${Object.keys(VTJ_LOCKED_VERSIONS).length}/8 项一致`);
  console.log(`  - 路由动态 import ${EXPECTED_DYNAMIC_IMPORTS} 处目标均存在`);
  console.log(`  - 跨域 import 检查${domain ? `（域 ${domain}）` : '（全部域）'}无违规`);
  process.exit(0);
}

main();
