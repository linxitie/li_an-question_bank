/**
 * 项目操作工具模块 — 创建页面脚手架
 */

import { existsFile, readJSON, writeJSON, writeText, getProjectConfig, getVuePath, getDslPath, getVtjProjectsDir } from '../core/file-system.js';
import { createSuccessResponse, createErrorResponse } from '../utils/logger.js';
import { createDryRunPreview } from '../utils/helpers.js';
import { addStaticRoute } from './route-management.js';
import { readdirSync } from 'fs';
import { join } from 'path';

// ── 工具定义 ──────────────────────────────────────────────

export const TOOLS = [
  {
    name: 'vtj_create_page_scaffold',
    description: `为新页面创建基础脚手架文件。会同时创建：
1. .vtj/files/<id>.json — DSL 定义文件
2. .vtj/vue/<id>.vue — Vue SFC 文件
3. 可选的静态路由条目`,
    inputSchema: {
      type: 'object',
      properties: {
        id: {
          type: 'string',
          description: '新页面的唯一 ID'
        },
        name: {
          type: 'string',
          description: '组件名称（PascalCase），如 "MyNewPage"'
        },
        title: {
          type: 'string',
          description: '页面标题（中文），如 "我的新页面"'
        },
        icon: {
          type: 'string',
          description: 'Element Plus 图标名',
          default: 'Collection'
        },
        addRoute: {
          type: 'boolean',
          description: '是否同时添加静态路由条目',
          default: false
        },
        routePath: {
          type: 'string',
          description: '当 addRoute=true 时的路由路径，如 "/my-page"'
        },
        dryRun: {
          type: 'boolean',
          description: '仅预览不实际创建文件',
          default: false
        }
      },
      required: ['id', 'name', 'title']
    }
  }
];

// ── 处理器 ──────────────────────────────────────────────

export const handlers = {
  async vtj_create_page_scaffold({ id, name: pageName, title, icon = 'Collection', addRoute = false, routePath, dryRun = false }) {
    const vuePath = getVuePath(id);
    const dslPath = getDslPath(id);

    if (existsFile(vuePath)) {
      return createErrorResponse('FILE_WRITE_ERROR', `Vue 文件已存在: .vtj/vue/${id}.vue`);
    }
    if (existsFile(dslPath)) {
      return createErrorResponse('FILE_WRITE_ERROR', `DSL 文件已存在: .vtj/files/${id}.json`);
    }

    const project = getProjectConfig();
    const version = String(Date.now());

    // 创建 Vue SFC
    const vueContent = `<!-- ${title} -->
<template>
  <div class="${pageName.toLowerCase()}">
    <h1>${title}</h1>
    <!-- VTJ 设计器生成的模板内容将在此处 -->
  </div>
</template>

<script lang="ts">
// @ts-nocheck
import { defineComponent, reactive } from 'vue';
import { useProvider } from '@vtj/renderer';

export default defineComponent({
  name: '${pageName}',
  setup(props) {
    const provider = useProvider({ id: '${id}', version: '${version}' });
    const state = reactive({
      loading: false
    });
    return { state, provider };
  },
  methods: {
    async handleInit() {
      // TODO: 初始化逻辑
    }
  },
  mounted() {
    this.handleInit();
  }
});
</script>

<style lang="css" scoped>
.${pageName.toLowerCase()} {
  padding: 20px;
  font-family: 'Noto Sans SC', 'PingFang SC', sans-serif;
}
</style>`;

    // 创建 DSL JSON
    const dslContent = {
      id,
      name: pageName,
      __VTJ_BLOCK__: true,
      __VERSION__: version,
      state: {
        loading: { type: 'JSExpression', value: 'false' }
      },
      methods: {
        handleInit: { type: 'asyncMethod' }
      },
      lifeCycles: {
        mounted: { type: 'method' }
      },
      nodes: [
        {
          id: `${id}_root`,
          name: 'div',
          from: '',
          props: {
            class: {
              type: 'JSExpression',
              value: `'${pageName.toLowerCase()}'`
            }
          },
          children: [
            {
              id: `${id}_title`,
              name: 'h1',
              from: '',
              children: title
            }
          ],
          locked: false,
          invisible: false
        }
      ],
      locked: false
    };

    if (dryRun) {
      return createDryRunPreview({
        operation: 'create_page_scaffold',
        target: `.vtj/vue/${id}.vue + .vtj/files/${id}.json`,
        changes: { id, name: pageName, title }
      });
    }

    // 写入文件
    writeText(vuePath, vueContent);
    writeJSON(dslPath, dslContent);

    // 可选：添加路由
    let routeResult = null;
    if (addRoute && routePath) {
      const { readText: readTextFn } = await import('../core/file-system.js');
      const { getSrcRouterFile } = await import('../core/file-system.js');
      const srcRouterPath = getSrcRouterFile();
      const routerContent = readTextFn(srcRouterPath);
      if (routerContent) {
        const routeAddResult = addStaticRoute(routerContent, {
          path: routePath,
          name: pageName,
          componentPath: `$vtj/vue/${id}.vue`
        });
        if (routeAddResult.success) {
          writeText(srcRouterPath + '.bak', routerContent);
          writeText(srcRouterPath, routeAddResult.content);
          routeResult = { success: true, path: routePath };
        }
      }
    }

    // 可选：添加到项目配置
    try {
      const projectsDir = getVtjProjectsDir();
      const projectFiles = readdirSync(projectsDir).filter(f => f.endsWith('.json'));
      const projectFile = projectFiles.length > 0 ? join(projectsDir, projectFiles[0]) : null;
      const updatedProject = projectFile ? readJSON(projectFile) : null;
      if (updatedProject) {
        updatedProject.pages = updatedProject.pages || [];
        if (!updatedProject.pages.find(p => p.id === id)) {
          updatedProject.pages.push({
            id,
            dir: false,
            raw: true,
            icon,
            mask: false,
            meta: '',
            name: pageName,
            page: 'page',
            pure: true,
            type: 'page',
            cache: false,
            style: null,
            title,
            hidden: false,
            layout: false,
            needLogin: false
          });
          writeJSON(projectFile, updatedProject);
        }
      }
    } catch (e) {
      // 项目配置更新失败不影响主要功能
    }

    return createSuccessResponse({
      id,
      name: pageName,
      title,
      files: {
        vue: `.vtj/vue/${id}.vue`,
        dsl: `.vtj/files/${id}.json`
      },
      route: routeResult,
      message: `页面"${title}" (${pageName}) 脚手架已创建。`
    });
  }
};
