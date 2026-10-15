/**
 * 错误码定义与建议信息模块
 */

export const ERROR_CODES = {
  PROJECT_NOT_FOUND: 'PROJECT_NOT_FOUND',
  PAGE_NOT_FOUND: 'PAGE_NOT_FOUND',
  DSL_FILE_NOT_FOUND: 'DSL_FILE_NOT_FOUND',
  VUE_FILE_NOT_FOUND: 'VUE_FILE_NOT_FOUND',
  MATERIAL_NOT_FOUND: 'MATERIAL_NOT_FOUND',
  ROUTE_FILE_NOT_FOUND: 'ROUTE_FILE_NOT_FOUND',
  ROUTE_PARSE_ERROR: 'ROUTE_PARSE_ERROR',
  ROUTE_DUPLICATE: 'ROUTE_DUPLICATE',
  FILE_WRITE_ERROR: 'FILE_WRITE_ERROR',
  VERSION_MISMATCH: 'VERSION_MISMATCH',
  RAW_PAGE_PROTECTED: 'RAW_PAGE_PROTECTED',
  NODES_NOT_FOUND: 'NODES_NOT_FOUND',
  EMPTY_TEMPLATE: 'EMPTY_TEMPLATE',
  EMPTY_SCRIPT: 'EMPTY_SCRIPT',
  BACKUP_FAILED: 'BACKUP_FAILED',
  INVALID_MODE: 'INVALID_MODE',
  SECTION_NOT_FOUND: 'SECTION_NOT_FOUND'
};

const SUGGESTIONS = {
  [ERROR_CODES.PROJECT_NOT_FOUND]: '项目不存在或路径无效，请检查项目路径是否正确。',
  [ERROR_CODES.PAGE_NOT_FOUND]: '页面不存在，请检查页面 ID 是否正确。',
  [ERROR_CODES.DSL_FILE_NOT_FOUND]: 'DSL 文件不存在，请检查文件路径或页面 ID。',
  [ERROR_CODES.VUE_FILE_NOT_FOUND]: 'Vue 文件不存在，请检查文件路径或页面 ID。',
  [ERROR_CODES.MATERIAL_NOT_FOUND]: '物料不存在，请检查组件名称或物料 ID。',
  [ERROR_CODES.ROUTE_FILE_NOT_FOUND]: '路由文件不存在，请检查路由文件路径。',
  [ERROR_CODES.ROUTE_PARSE_ERROR]: '路由解析失败，请检查路由文件格式是否正确。',
  [ERROR_CODES.ROUTE_DUPLICATE]: '路由重复，请检查是否已存在相同路径的路由。',
  [ERROR_CODES.FILE_WRITE_ERROR]: '文件写入失败，请检查文件权限或磁盘空间。',
  [ERROR_CODES.VERSION_MISMATCH]: '版本不匹配，请同步 Vue 与 DSL 文件后再试。',
  [ERROR_CODES.RAW_PAGE_PROTECTED]: 'raw 页面受保护，无法修改，请先关闭 raw 模式。',
  [ERROR_CODES.NODES_NOT_FOUND]: '未找到节点，请检查页面结构或节点 ID。',
  [ERROR_CODES.EMPTY_TEMPLATE]: '模板为空，请先创建页面模板。',
  [ERROR_CODES.EMPTY_SCRIPT]: '脚本为空，请先编写页面脚本。',
  [ERROR_CODES.BACKUP_FAILED]: '备份失败，请检查文件权限或磁盘空间。',
  [ERROR_CODES.INVALID_MODE]: '无效的模式，请检查传入的 mode 参数。',
  [ERROR_CODES.SECTION_NOT_FOUND]: '未找到指定区块，请检查 section 参数。'
};

/**
 * 根据错误码返回建议信息
 * @param {string} code 错误码
 * @returns {string} 建议信息，未知错误码返回空字符串
 */
export function getSuggestion(code) {
  return SUGGESTIONS[code] || '';
}