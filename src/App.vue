<template>
  <ElConfigProvider :locale="zhCn">
    <Suspense>
      <VtjErrorBoundary>
        <XMask
          :title="title"
          :logo="logo || _logo"
          :menus="menus"
          :disabled="disabled"
          :pure="pure"
          :actions="actions"
          @action-click="onActionClick"
          :theme="themeSwitchable"></XMask>
      </VtjErrorBoundary>
    </Suspense>
    <BackToTop />
    <!-- 番茄钟挂件：全局常驻，任何页面都能随时专注（用户要求：不要埋在页面里） -->
    <PomodoroWidget />
    <!-- 学生端导航补丁：把铃铛/头像/下载入口统一到顶部导航（R3：不改 .vtj 模板） -->
    <StudentTopBar />
    <!-- 复习提醒铃铛 + 版本角标：全局常驻，弹窗由顶部铃铛触发 -->
    <ReviewBell />
    <BuildStamp />
  </ElConfigProvider>
</template>
<script setup lang="ts">
import { Suspense } from 'vue';
import PomodoroWidget from '@/components/focus/PomodoroWidget.vue';
import { ElConfigProvider, ElMessage } from 'element-plus';
import {
  XMask,
  useMask,
  Bell,
  Lock,
  SwitchButton,
  type ActionBarItems,
  type ActionProps
} from '@vtj/web';
import zhCn from 'element-plus/es/locale/lang/zh-cn';
import _logo from './assets/logo.svg';
import VtjErrorBoundary from './components/common/VtjErrorBoundary.vue';
import BackToTop from './components/common/BackToTop.vue';
import BuildStamp from './components/common/BuildStamp.vue';
import ReviewBell from './components/domain/ReviewBell.vue';
import StudentTopBar from './components/layout/StudentTopBar.vue';
const { disabled, title, menus, logo, themeSwitchable, pure } = useMask();

const actions: ActionBarItems = [
  {
    name: 'message',
    icon: Bell,
    badge: 1
  },
  {
    name: 'lock',
    icon: Lock
  },
  {
    name: 'logout',
    icon: SwitchButton
  }
];

const onActionClick = (action: ActionProps) => {
  ElMessage.success(`click: ${action.name}`);
};
</script>
