/**
 * 解析器模块
 *
 * 从 vtj-mcp-server.js 单体中提取的解析函数：
 * - parseVueSFC / parseVueTemplateSection / parseVueScriptSection / parseVueStyleSection
 * - parseDslFileSections
 * - parseNodes（递归解析节点树）
 */

/**
 * 解析 Vue SFC 文件，提取各区块
 * 返回 { template, script, style, scriptSetup, styles }
 */
export function parseVueSFC(source) {
  const result = { template: '', script: '', style: '', scriptSetup: '', styles: [] };

  // 提取 <template>
  const templateMatch = source.match(/<template>([\s\S]*?)<\/template>/i);
  if (templateMatch) result.template = templateMatch[1];

  // 提取 <script setup> 或 <script>
  const scriptSetupMatch = source.match(/<script\s+setup[^>]*>([\s\S]*?)<\/script>/i);
  if (scriptSetupMatch) {
    result.scriptSetup = scriptSetupMatch[1];
  } else {
    const scriptMatch = source.match(/<script[^>]*>([\s\S]*?)<\/script>/i);
    if (scriptMatch) result.script = scriptMatch[1];
  }

  // 提取所有 <style> 块
  const styleRegex = /<style[^>]*>([\s\S]*?)<\/style>/gi;
  let styleMatch;
  while ((styleMatch = styleRegex.exec(source)) !== null) {
    result.styles.push(styleMatch[1]);
  }
  if (result.styles.length > 0) {
    result.style = result.styles.join('\n');
  }

  return result;
}

/**
 * 提取 Vue SFC 的 <template> 内容
 */
export function parseVueTemplateSection(source) {
  const match = source.match(/<template>([\s\S]*?)<\/template>/i);
  return match ? match[1] : '';
}

/**
 * 提取 Vue SFC 的 <script> 内容
 */
export function parseVueScriptSection(source) {
  const match = source.match(/<script[^>]*>([\s\S]*?)<\/script>/i);
  return match ? match[1] : '';
}

/**
 * 提取 Vue SFC 的 <style> 内容
 */
export function parseVueStyleSection(source) {
  const match = source.match(/<style[^>]*>([\s\S]*?)<\/style>/i);
  return match ? match[1] : '';
}

/**
 * 解析 DSL JSON 字符串，返回解析后的对象
 */
export function parseDslFileSections(content) {
  return JSON.parse(content);
}

/**
 * 递归解析单个节点
 */
function parseNode(node, currentDepth = 0, depth = 3) {
  if (currentDepth > depth) return { __truncated__: true };

  const info = {
    id: node.id,
    name: node.name,
    from: node.from || '(原生 HTML)',
    hasProps: !!node.props && Object.keys(node.props).length > 0,
    hasEvents: !!node.events && Object.keys(node.events).length > 0,
    directives: node.directives?.map(d => d.name) || [],
    childrenType: typeof node.children
  };

  // 提取关键属性
  if (node.props) {
    info.props = Object.keys(node.props).map(k => {
      const v = node.props[k];
      return {
        name: k,
        type: v?.type || 'literal',
        isDynamic: v?.type === 'JSExpression'
      };
    });
  }

  // 提取事件
  if (node.events) {
    info.events = Object.keys(node.events).map(k => {
      const v = node.events[k];
      return {
        event: k,
        handler: v?.handler?.value?.substring(0, 80) || '(native)'
      };
    });
  }

  // 递归子节点
  if (Array.isArray(node.children)) {
    info.children = node.children.map(c => parseNode(c, currentDepth + 1, depth));
    info.childrenCount = node.children.length;
  } else if (typeof node.children === 'object' && node.children?.type === 'JSExpression') {
    info.dynamicChildren = node.children.value?.substring(0, 60);
  } else if (typeof node.children === 'string') {
    info.textContent = node.children.substring(0, 100);
  }

  return info;
}

/**
 * 递归解析节点树
 */
export function parseNodes(nodes, depth = 3) {
  return nodes.map(n => parseNode(n, 0, depth));
}