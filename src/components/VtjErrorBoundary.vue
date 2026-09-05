<!--
  VTJ 错误边界组件
  -
  - 作用：捕获子组件渲染错误，显示友好提示，避免整页白屏
  - 实现：Vue 3 onErrorCaptured + 原生 DOM 提示（无 ElementPlus 依赖，避免循环引用）
  - 用法：<VtjErrorBoundary><MyComponent /></VtjErrorBoundary>
  -
  - 设计原则：
  -   1. 不依赖任何 UI 库，保证自身不会因依赖加载失败而崩溃
  -   2. 错误提示提供"刷新"按钮，用户可自助恢复
  -   3. 错误信息输出到 console，便于开发者调试
  -   4. 可选的 onError prop，允许父组件监听错误（用于上报）
-->
<template>
  <div class="vtj-error-boundary">
    <template v-if="!hasError">
      <slot></slot>
    </template>
    <div v-else class="vtj-error-fallback">
      <div class="vtj-error-icon">⚠️</div>
      <div class="vtj-error-title">模块加载失败</div>
      <div class="vtj-error-desc">{{ errorMessage }}</div>
      <button class="vtj-error-retry" @click="handleRetry">刷新页面</button>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, onErrorCaptured } from 'vue';

export default defineComponent({
  name: 'VtjErrorBoundary',
  props: {
    // 可选：错误回调，用于错误上报
    onError: {
      type: Function,
      default: null
    }
  },
  setup(props) {
    const hasError = ref(false);
    const errorMessage = ref('组件渲染异常');

    onErrorCaptured((err: any, instance, info) => {
      console.error('[VtjErrorBoundary] 捕获到组件错误:', err);
      console.error('[VtjErrorBoundary] 错误信息:', info);
      hasError.value = true;
      errorMessage.value = (err && err.message) ? err.message : '组件渲染异常';

      // 调用可选的错误回调
      if (typeof props.onError === 'function') {
        try {
          props.onError(err, info);
        } catch (e) {
          // 回调失败不影响边界功能
        }
      }

      // 返回 false 阻止错误继续向上冒泡
      return false;
    });

    function handleRetry() {
      // 重置错误状态并刷新页面
      hasError.value = false;
      errorMessage.value = '';
      // 使用硬刷新确保彻底清理
      window.location.reload();
    }

    return { hasError, errorMessage, handleRetry };
  }
});
</script>

<style scoped>
.vtj-error-boundary {
  width: 100%;
  min-height: 100%;
}
.vtj-error-fallback {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 400px;
  padding: 40px 20px;
  font-family: 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  background: #f8f9fc;
  color: #1a2b5f;
}
.vtj-error-icon {
  font-size: 48px;
  margin-bottom: 16px;
}
.vtj-error-title {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 8px;
}
.vtj-error-desc {
  font-size: 14px;
  color: #8a8faa;
  margin-bottom: 20px;
  max-width: 480px;
  text-align: center;
  word-break: break-all;
}
.vtj-error-retry {
  padding: 8px 24px;
  background: #1a2b5f;
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
  transition: background 0.2s;
}
.vtj-error-retry:hover {
  background: #c41e3a;
}
</style>
