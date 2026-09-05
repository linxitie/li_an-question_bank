/**
 * VTJ 版本号自动同步脚本
 *
 * 作用：扫描 .vtj/vue/*.vue 中的 useProvider({version}) 提取版本号，
 *       同步写入对应 .vtj/files/*.json 的 __VERSION__ 字段。
 *
 * 触发方式：
 *   - 手动执行：npm run sync:vtj-version
 *   - 构建前自动执行：npm run build（通过 prebuild 钩子）
 *
 * 设计原则：
 *   1. 仅同步版本号，不修改 nodes 节点树（遵守 VTJ 职责分离）
 *   2. 以 .vue 文件为单一数据源（Source of Truth）
 *   3. 幂等执行：多次运行结果一致，不会重复修改
 *   4. 详细的日志输出，便于审计
 */

import { readFileSync, writeFileSync, readdirSync, existsSync } from 'node:fs';
import { join, basename, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = fileURLToPath(new URL('.', import.meta.url));
const projectRoot = resolve(__dirname, '..');
const vueDir = join(projectRoot, '.vtj', 'vue');
const filesDir = join(projectRoot, '.vtj', 'files');

/**
 * 从 .vue 文件内容中提取 useProvider 的 id 和 version
 * 匹配模式：useProvider({ id: 'xxx', version: 'yyy' })
 */
function extractProviderInfo(content) {
  // 匹配 useProvider({ id: 'xxx', version: 'yyy' }) 或 useProvider({ id: "xxx", version: "yyy" })
  const regex = /useProvider\(\s*\{\s*id\s*:\s*['"]([^'"]+)['"]\s*,\s*version\s*:\s*['"]([^'"]+)['"]\s*\}\s*\)/;
  const match = content.match(regex);
  if (match) {
    return { id: match[1], version: match[2] };
  }
  return null;
}

/**
 * 从 .json 文件中提取 __VERSION__ 字段
 */
function extractJsonVersion(content) {
  try {
    const data = JSON.parse(content);
    return data.__VERSION__ || null;
  } catch (e) {
    return null;
  }
}

/**
 * 更新 .json 文件的 __VERSION__ 字段（保留原格式）
 */
function updateJsonVersion(content, newVersion) {
  // 匹配 "__VERSION__": "xxx" 或 "__VERSION__":"xxx"（含空格变体）
  const regex = /(["']__VERSION__["']\s*:\s*)(["'])([^"']*)(["'])/;
  return content.replace(regex, `$1$2${newVersion}$4`);
}

/**
 * 主流程
 */
function main() {
  console.log('[sync_vtj_version] 开始同步 VTJ 版本号...');
  console.log(`[sync_vtj_version] Vue 目录: ${vueDir}`);
  console.log(`[sync_vtj_version] JSON 目录: ${filesDir}`);

  if (!existsSync(vueDir)) {
    console.error('[sync_vtj_version] 错误：.vtj/vue 目录不存在');
    process.exit(1);
  }
  if (!existsSync(filesDir)) {
    console.error('[sync_vtj_version] 错误：.vtj/files 目录不存在');
    process.exit(1);
  }

  const vueFiles = readdirSync(vueDir).filter(f => f.endsWith('.vue'));
  console.log(`[sync_vtj_version] 发现 ${vueFiles.length} 个 .vue 文件`);

  let synced = 0;
  let skipped = 0;
  let failed = 0;
  const mismatches = [];

  for (const vueFile of vueFiles) {
    const vuePath = join(vueDir, vueFile);
    const baseName = basename(vueFile, '.vue');
    const jsonPath = join(filesDir, baseName + '.json');

    try {
      const vueContent = readFileSync(vuePath, 'utf-8');
      const providerInfo = extractProviderInfo(vueContent);

      if (!providerInfo) {
        // 该 .vue 文件不使用 useProvider，跳过
        skipped++;
        continue;
      }

      if (!existsSync(jsonPath)) {
        console.warn(`[sync_vtj_version] 警告：未找到 ${baseName}.json，跳过`);
        skipped++;
        continue;
      }

      const jsonContent = readFileSync(jsonPath, 'utf-8');
      const jsonVersion = extractJsonVersion(jsonContent);

      if (jsonVersion === providerInfo.version) {
        // 版本已一致，无需修改
        skipped++;
        continue;
      }

      // 版本不一致，执行同步
      const updatedContent = updateJsonVersion(jsonContent, providerInfo.version);
      writeFileSync(jsonPath, updatedContent, 'utf-8');

      console.log(`[sync_vtj_version] ✅ ${baseName}.vue → ${baseName}.json: ${jsonVersion} → ${providerInfo.version}`);
      mismatches.push({
        file: baseName,
        oldVersion: jsonVersion,
        newVersion: providerInfo.version
      });
      synced++;
    } catch (e) {
      console.error(`[sync_vtj_version] ❌ 处理 ${vueFile} 失败: ${e.message}`);
      failed++;
    }
  }

  console.log('\n[sync_vtj_version] ========== 同步结果 ==========');
  console.log(`[sync_vtj_version] 同步修改: ${synced} 个文件`);
  console.log(`[sync_vtj_version] 已跳过: ${skipped} 个文件（版本一致或无 useProvider）`);
  console.log(`[sync_vtj_version] 失败: ${failed} 个文件`);

  if (mismatches.length > 0) {
    console.log('\n[sync_vtj_version] 修改明细：');
    mismatches.forEach(m => {
      console.log(`  ${m.file}: ${m.oldVersion} → ${m.newVersion}`);
    });
  }

  if (failed > 0) {
    process.exit(1);
  }

  console.log('[sync_vtj_version] 同步完成。');
}

main();
