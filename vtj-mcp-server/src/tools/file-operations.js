/**
 * 文件读写工具模块 — 读写 Vue SFC 和 DSL JSON 文件
 */

import {
  readText, writeText, readJSON, writeJSON, existsFile, createBackup,
  getVuePath, getDslPath
} from '../core/file-system.js';
import { parseVueSFC } from '../core/parser.js';
import { createSuccessResponse, createErrorResponse } from '../utils/logger.js';
import { createDryRunPreview, getNextSteps, syncAdvice } from '../utils/helpers.js';

// ── 工具定义 ──────────────────────────────────────────────

export const TOOLS = [
  {
    name: 'vtj_read_vue_file',
    description: '读取 VTJ 生成的 .vue 文件内容。可以读取完整文件或仅读取特定部分（template/script/style）。',
    inputSchema: {
      type: 'object',
      properties: {
        id: { type: 'string', description: '页面或区块的 ID' },
        section: {
          type: 'string',
          description: '要读取的部分：full（完整文件）、template、script、style',
          enum: ['full', 'template', 'script', 'style']
        }
      },
      required: ['id']
    }
  },
  {
    name: 'vtj_write_vue_script',
    description: '修改 VTJ 生成的 .vue 文件的 <script> 部分。',
    inputSchema: {
      type: 'object',
      properties: {
        id: { type: 'string', description: '页面或区块的 ID' },
        scriptContent: { type: 'string', description: '新的 <script> 部分完整内容' },
        mode: {
          type: 'string',
          description: '修改模式',
          enum: ['replace', 'methods', 'state', 'lifeCycles', 'addMethod']
        },
        methodName: { type: 'string', description: '当 mode=addMethod 时，新方法的名称' },
        methodBody: { type: 'string', description: '当 mode=addMethod 时，新方法的函数体' },
        dryRun: { type: 'boolean', description: '仅预览不实际写入', default: false }
      },
      required: ['id', 'scriptContent']
    }
  },
  {
    name: 'vtj_read_dsl_file',
    description: '读取 .vtj/files/ 下的 DSL JSON 文件。',
    inputSchema: {
      type: 'object',
      properties: {
        id: { type: 'string', description: '页面或区块的 ID' },
        section: {
          type: 'string',
          description: '读取指定部分',
          enum: ['full', 'nodes', 'state', 'methods', 'lifeCycles', 'dataSources', 'css']
        }
      },
      required: ['id']
    }
  },
  {
    name: 'vtj_write_vue_template',
    description: '写入 VTJ 生成的 .vue 文件的 <template> 部分。',
    inputSchema: {
      type: 'object',
      properties: {
        id: { type: 'string', description: '页面或区块的 ID' },
        templateContent: { type: 'string', description: '完整的 <template> 标签及内容' },
        dryRun: { type: 'boolean', description: '仅预览不实际写入', default: false }
      },
      required: ['id', 'templateContent']
    }
  },
  {
    name: 'vtj_write_vue_style',
    description: '写入 VTJ 生成的 .vue 文件的 <style> 部分。',
    inputSchema: {
      type: 'object',
      properties: {
        id: { type: 'string', description: '页面或区块的 ID' },
        styleContent: { type: 'string', description: '完整的 <style scoped> 标签及内容' },
        dryRun: { type: 'boolean', description: '仅预览不实际写入', default: false }
      },
      required: ['id', 'styleContent']
    }
  },
  {
    name: 'vtj_write_dsl_file',
    description: '写入 VTJ DSL JSON 文件的指定部分。',
    inputSchema: {
      type: 'object',
      properties: {
        id: { type: 'string', description: '页面或区块的 ID' },
        section: {
          type: 'string',
          enum: ['nodes', 'state', 'methods', 'lifeCycles', '__VERSION__', 'full'],
          description: '要写入的部分'
        },
        content: { type: 'string', description: '要写入的内容（JSON 字符串或纯文本）' },
        dryRun: { type: 'boolean', description: '仅预览不实际写入', default: false }
      },
      required: ['id', 'section', 'content']
    }
  },
  {
    name: 'vtj_write_vue_full',
    description: '写入完整的 .vue 文件（template + script + style）。',
    inputSchema: {
      type: 'object',
      properties: {
        id: { type: 'string', description: '页面或区块的 ID' },
        content: { type: 'string', description: '完整的 .vue 文件内容' },
        dryRun: { type: 'boolean', description: '仅预览不实际写入', default: false }
      },
      required: ['id', 'content']
    }
  }
];

// ── 处理器 ──────────────────────────────────────────────

export const handlers = {
  async vtj_read_vue_file({ id, section = 'full' }) {
    const vuePath = getVuePath(id);
    if (!existsFile(vuePath)) {
      return createErrorResponse('FILE_NOT_FOUND', `文件不存在: .vtj/vue/${id}.vue`);
    }

    const content = readText(vuePath);
    if (content === null) {
      return createErrorResponse('FILE_READ_ERROR', '无法读取文件');
    }

    if (section === 'full') {
      return createSuccessResponse(content);
    }

    const parsed = parseVueSFC(content);
    const sectionContent = section === 'template' ? parsed.template
      : section === 'script' ? (parsed.script || parsed.scriptSetup)
      : section === 'style' ? parsed.style
      : null;

    return createSuccessResponse({ id, section, content: sectionContent });
  },

  async vtj_write_vue_script({ id, scriptContent, mode = 'replace', methodName, methodBody, dryRun = false }) {
    const vuePath = getVuePath(id);
    if (!existsFile(vuePath)) {
      return createErrorResponse('FILE_NOT_FOUND', `文件不存在: .vtj/vue/${id}.vue`);
    }

    const original = readText(vuePath);
    if (original === null) {
      return createErrorResponse('FILE_READ_ERROR', '无法读取文件');
    }

    if (!['replace', 'methods', 'state', 'lifeCycles', 'addMethod'].includes(mode)) {
      return createErrorResponse('INVALID_MODE', `无效的模式: ${mode}`);
    }

    if (dryRun) {
      return createDryRunPreview({
        operation: 'write_vue_script',
        target: `.vtj/vue/${id}.vue`,
        changes: { mode, scriptContent },
        nextSteps: getNextSteps('write_vue_script', id)
      });
    }

    let newContent;

    if (mode === 'replace') {
      const templateMatch = original.match(/([\s\S]*?)<script/);
      const styleMatch = original.match(/<\/script>([\s\S]*)/);
      if (!templateMatch || !styleMatch) {
        newContent = scriptContent;
      } else {
        newContent = templateMatch[1] + scriptContent + styleMatch[1];
      }
    } else if (mode === 'methods') {
      const scriptTagRegex = /(<script[^>]*>)([\s\S]*?)(<\/script>)/i;
      const scriptMatch = original.match(scriptTagRegex);
      if (!scriptMatch) {
        return createErrorResponse('EMPTY_SCRIPT', '无法解析 script 标签');
      }
      const newScriptBody = scriptMatch[2].replace(
        /methods\s*:\s*\{[\s\S]*?\n\s*\}/,
        `methods: ${scriptContent}`
      );
      newContent = original.replace(scriptTagRegex, `${scriptMatch[1]}${newScriptBody}${scriptMatch[3]}`);
    } else if (mode === 'state') {
      newContent = original.replace(
        /(reactive\s*\(\s*)\{[\s\S]*?(\}\s*\))/,
        `$1${scriptContent}$2`
      );
    } else if (mode === 'addMethod') {
      if (!methodName || !methodBody) {
        return createErrorResponse('INVALID_MODE', 'addMethod 模式需要 methodName 和 methodBody');
      }
      const methodsEnd = original.match(/(methods\s*:\s*\{[\s\S]*?)(\n\s*\})/);
      if (!methodsEnd) {
        return createErrorResponse('EMPTY_SCRIPT', '找不到 methods 块');
      }
      const insert = `,\n    ${methodName}: ${methodBody}\n  `;
      newContent = original.replace(methodsEnd[0], methodsEnd[1] + insert + methodsEnd[2].trim());
    } else if (mode === 'lifeCycles') {
      newContent = original.replace(
        /(lifeCycles\s*:\s*\{[\s\S]*?\n\s*\})/,
        scriptContent
      );
    }

    if (!newContent) {
      return createErrorResponse('FILE_WRITE_ERROR', '无法生成新内容，请检查参数');
    }

    createBackup(vuePath);
    const success = writeText(vuePath, newContent);
    if (!success) {
      return createErrorResponse('FILE_WRITE_ERROR', '写入失败');
    }

    return createSuccessResponse({
      id,
      mode,
      path: `.vtj/vue/${id}.vue`,
      backupPath: `.vtj/vue/${id}.vue.bak`,
      message: `文件已更新。${syncAdvice(id)}`
    });
  },

  async vtj_read_dsl_file({ id, section = 'full' }) {
    const dslPath = getDslPath(id);
    if (!existsFile(dslPath)) {
      return createErrorResponse('FILE_NOT_FOUND', `文件不存在: .vtj/files/${id}.json`);
    }

    const dsl = readJSON(dslPath);
    if (!dsl) {
      return createErrorResponse('FILE_READ_ERROR', '无法解析 DSL JSON');
    }

    if (section === 'full') {
      return createSuccessResponse({
        id,
        path: `.vtj/files/${id}.json`,
        name: dsl.name,
        version: dsl.__VERSION__,
        hasState: !!dsl.state && Object.keys(dsl.state).length > 0,
        hasMethods: !!dsl.methods && Object.keys(dsl.methods).length > 0,
        hasComputed: !!dsl.computed && Object.keys(dsl.computed).length > 0,
        hasLifeCycles: !!dsl.lifeCycles && Object.keys(dsl.lifeCycles).length > 0,
        nodesCount: dsl.nodes?.length || 0,
        dsl
      });
    }

    const sections = {
      nodes: dsl.nodes,
      state: dsl.state,
      methods: dsl.methods,
      lifeCycles: dsl.lifeCycles,
      dataSources: dsl.dataSources,
      css: dsl.css
    };

    return createSuccessResponse({
      id,
      section,
      content: sections[section] || null
    });
  },

  async vtj_write_vue_template({ id, templateContent, dryRun = false }) {
    const vuePath = getVuePath(id);
    if (!existsFile(vuePath)) {
      return createErrorResponse('FILE_NOT_FOUND', `文件不存在: .vtj/vue/${id}.vue`);
    }

    if (dryRun) {
      return createDryRunPreview({
        operation: 'write_vue_template',
        target: `.vtj/vue/${id}.vue`,
        changes: { templateContent }
      });
    }

    const original = readText(vuePath);
    if (original === null) {
      return createErrorResponse('FILE_READ_ERROR', '无法读取文件');
    }

    const templateRegex = /<template>[\s\S]*?<\/template>/i;
    const newContent = templateRegex.test(original)
      ? original.replace(templateRegex, templateContent)
      : templateContent + '\n' + original;

    createBackup(vuePath);
    const success = writeText(vuePath, newContent);
    if (!success) {
      return createErrorResponse('FILE_WRITE_ERROR', '写入失败');
    }

    return createSuccessResponse({
      id,
      path: `.vtj/vue/${id}.vue`,
      backupPath: `.vtj/vue/${id}.vue.bak`,
      message: `template 已更新。${syncAdvice(id)}`
    });
  },

  async vtj_write_vue_style({ id, styleContent, dryRun = false }) {
    const vuePath = getVuePath(id);
    if (!existsFile(vuePath)) {
      return createErrorResponse('FILE_NOT_FOUND', `文件不存在: .vtj/vue/${id}.vue`);
    }

    if (dryRun) {
      return createDryRunPreview({
        operation: 'write_vue_style',
        target: `.vtj/vue/${id}.vue`,
        changes: { styleContent }
      });
    }

    const original = readText(vuePath);
    if (original === null) {
      return createErrorResponse('FILE_READ_ERROR', '无法读取文件');
    }

    const styleRegex = /<style[^>]*>[\s\S]*?<\/style>/i;
    const newContent = styleRegex.test(original)
      ? original.replace(styleRegex, styleContent)
      : original + '\n' + styleContent;

    createBackup(vuePath);
    const success = writeText(vuePath, newContent);
    if (!success) {
      return createErrorResponse('FILE_WRITE_ERROR', '写入失败');
    }

    return createSuccessResponse({
      id,
      path: `.vtj/vue/${id}.vue`,
      backupPath: `.vtj/vue/${id}.vue.bak`,
      message: 'style 已更新。'
    });
  },

  async vtj_write_dsl_file({ id, section, content, dryRun = false }) {
    const dslPath = getDslPath(id);
    if (!existsFile(dslPath)) {
      return createErrorResponse('FILE_NOT_FOUND', `文件不存在: .vtj/files/${id}.json`);
    }

    if (dryRun) {
      return createDryRunPreview({
        operation: 'write_dsl_file',
        target: `.vtj/files/${id}.json`,
        changes: { section, content }
      });
    }

    const dsl = readJSON(dslPath);
    if (!dsl) {
      return createErrorResponse('FILE_READ_ERROR', '无法读取 DSL 文件');
    }

    createBackup(dslPath);

    if (section === 'full') {
      writeJSON(dslPath, JSON.parse(content));
    } else if (section === '__VERSION__') {
      dsl['__VERSION__'] = String(content);
      writeJSON(dslPath, dsl);
    } else if (section === 'nodes') {
      dsl['nodes'] = JSON.parse(content);
      writeJSON(dslPath, dsl);
    } else {
      dsl[section] = JSON.parse(content);
      writeJSON(dslPath, dsl);
    }

    return createSuccessResponse({
      id,
      section,
      path: `.vtj/files/${id}.json`,
      backupPath: `.vtj/files/${id}.json.bak`,
      message: `DSL ${section} 已更新。`
    });
  },

  async vtj_write_vue_full({ id, content, dryRun = false }) {
    const vuePath = getVuePath(id);
    if (!existsFile(vuePath)) {
      return createErrorResponse('FILE_NOT_FOUND', `文件不存在: .vtj/vue/${id}.vue`);
    }

    if (dryRun) {
      return createDryRunPreview({
        operation: 'write_vue_full',
        target: `.vtj/vue/${id}.vue`,
        changes: { contentLength: content.length }
      });
    }

    const original = readText(vuePath);
    if (original === null) {
      return createErrorResponse('FILE_READ_ERROR', '无法读取文件');
    }

    createBackup(vuePath);
    const success = writeText(vuePath, content);
    if (!success) {
      return createErrorResponse('FILE_WRITE_ERROR', '写入失败');
    }

    return createSuccessResponse({
      id,
      path: `.vtj/vue/${id}.vue`,
      backupPath: `.vtj/vue/${id}.vue.bak`,
      message: `完整 .vue 文件已更新。${syncAdvice(id)}`
    });
  }
};
