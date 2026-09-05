/**
 * 题目内容过滤工具
 * 用于移除系统生成的 UTBxxx ID 等噪音内容
 */

/**
 * 过滤题目内容，移除系统ID和多余格式
 * @param {string} content - 原始题目内容
 * @returns {string} 清洗后的内容
 */
export function filterQuestionContent(content) {
  if (!content) return ''
  
  let filtered = content
  
  // 1. 移除 UTB 系统 ID (UTB + 16位十六进制)
  filtered = filtered.replace(/UTB[a-f0-9]{16}/gi, '')
  
  // 2. 移除题号前缀 (如 "第5题：" "第1题：")
  filtered = filtered.replace(/^第\s*\d+\s*题[：:]\s*/, '')
  
  // 3. 移除选项前缀的 UTB ID (如 "UTB7df857a7-选项A-5")
  filtered = filtered.replace(/UTB[a-f0-9]{16}[-－]\s*选项[A-D]\s*[\d\-]*/gi, '')
  
  // 4. 合并多余空白字符
  filtered = filtered.replace(/\s+/g, ' ')
  
  // 5. 去除首尾空格
  filtered = filtered.trim()
  
  return filtered
}

/**
 * 过滤选项内容
 * @param {string} optionContent - 选项内容
 * @returns {string} 清洗后的选项
 */
export function filterOptionContent(optionContent) {
  if (!optionContent) return ''
  
  let filtered = optionContent
  
  // 移除 UTB ID
  filtered = filtered.replace(/UTB[a-f0-9]{16}[-－]?/gi, '')
  
  // 移除选项编号前缀 (如 "选项A-" "A-" "A.")
  filtered = filtered.replace(/^(选项\s*[A-D]|[A-D])[\-．.]\s*/, '')
  
  // 合并空白
  filtered = filtered.replace(/\s+/g, ' ').trim()
  
  return filtered
}

/**
 * Vue 组件：题目内容显示
 * 自动过滤 UTB ID 等噪音内容
 */
export const QuestionContentFilter = {
  name: 'QuestionContentFilter',
  props: {
    content: {
      type: String,
      default: ''
    },
    showRaw: {
      type: Boolean,
      default: false
    }
  },
  computed: {
    displayContent() {
      if (this.showRaw) return this.content
      return filterQuestionContent(this.content)
    }
  },
  render(h) {
    return h('span', this.displayContent)
  }
}

/**
 * Vue 组件：选项内容显示
 */
export const OptionContentFilter = {
  name: 'OptionContentFilter',
  props: {
    content: {
      type: String,
      default: ''
    },
    showRaw: {
      type: Boolean,
      default: false
    }
  },
  computed: {
    displayContent() {
      if (this.showRaw) return this.content
      return filterOptionContent(this.content)
    }
  },
  render(h) {
    return h('span', this.displayContent)
  }
}

export default {
  filterQuestionContent,
  filterOptionContent,
  QuestionContentFilter,
  OptionContentFilter
}