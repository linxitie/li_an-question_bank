<template>
  <div class="app-navigation">
    <div
      v-for="(item, index) in state.navItems"
      :key="item.name"
      :class="
        Object.assign(
          { 'nav-item-box': true },
          { 'nav-active': isActive(item) }
        )
      "
      @click="handleNavClick(item)">
      <span class="nav-text"> {{ item.title }}</span>
      <span v-if="item.name === 'login'">
        <div class="login-wrapper">
          <XIcon :icon="UserFilled" :size="26" color="#ffffff"></XIcon></div
      ></span>
    </div>
  </div>
</template>
<script lang="ts">
  // @ts-nocheck
  import { defineComponent, reactive } from 'vue';
  import { XIcon } from '@vtj/ui';
  import { UserFilled } from '@vtj/icons';
  import { useProvider } from '@vtj/renderer';
  export default defineComponent({
    name: 'AppNavigation',
    components: { XIcon },
    setup(props) {
      const provider = useProvider({ id: '8jv82kin', version: '1778915425695' });
      const state = reactive({
        navItems: [
          { name: 'home', title: '首页', route: '/page/9jvcm4zp' },
          { name: 'questions', title: '题库', route: '/page/2jv81sx2' },
          { name: 'about', title: '关于砺安题库', route: '/page/3jv81w69' },
          { name: 'forum', title: '论坛', route: '/page/1jvbfecd' },
          { name: 'download', title: '下载客户端', route: '/page/2jvbfiuf' },
          { name: 'login', title: '登录头像', route: '' }
        ]
      });
      return { state, props, provider, UserFilled };
    },
    computed: {
      currentRoute() {
        return this.$route.path;
      }
    },
    methods: {
      isActive(item) {
        if (item.name === 'login') return false;
        return this.currentRoute === item.route;
      },
      handleNavClick(item) {
        if (item.name === 'login') {
          this.$message.info('登录功能开发中');
          return;
        }
        if (item.route) {
          this.$router.push(item.route);
        } else {
          this.$message.info(`${item.title}功能开发中`);
        }
      }
    }
  })
</script>
<style lang="css" scoped>
  .app-navigation {
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(135deg, #0a1628 0%, #12233f 30%, #1a2a4a 100%);
    padding: 0 30px;
    height: 76px;
    border-bottom: 2px solid rgba(200, 22, 30, 0.25);
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.3);
    font-family: 'PingFang SC', 'Microsoft YaHei', 'Segoe UI', sans-serif;
    position: relative;
    z-index: 100;
  }
  /* 每个模块的盒子 */
  .nav-item-box {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 8px 24px;
    margin: 10px 0 10px 16px;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
    min-width: 100px;
    height: 44px;
    background: rgba(255, 255, 255, 0.03);
    color: #cfd8e3;
    font-size: 17px;
    font-weight: 500;
    letter-spacing: 1px;
    position: relative;
    box-sizing: border-box;
    user-select: none;
  }
  .nav-item-box:first-child {
    margin-left: 20px;
  }
  .nav-item-box .nav-text {
    transition:
      transform 0.3s ease,
      color 0.3s ease;
    display: inline-block;
    line-height: 1;
  }
  /* 悬停：灰度增加 + 圆角25px + 文字上移变色 */
  .nav-item-box:not(.nav-active):hover {
    background: rgba(230, 57, 70, 0.12);
    border-radius: 8px;
    color: #e63946;
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(230, 57, 70, 0.2);
  }
  /* 激活：藏蓝色底+中国红边框 */
  .nav-item-box.nav-active {
    background: linear-gradient(
      135deg,
      rgba(10, 22, 40, 0.95) 0%,
      rgba(20, 30, 55, 0.9) 100%
    );
    color: #ffffff;
    border-radius: 8px;
    filter: none;
    border: 1.5px solid #c8161e;
    box-shadow:
      0 0 20px rgba(200, 22, 30, 0.4),
      inset 0 1px 0 rgba(255, 255, 255, 0.05);
    font-weight: 600;
  }
  .nav-item-box.nav-active .nav-text {
    color: #ffffff;
    text-shadow: 0 0 10px rgba(255, 255, 255, 0.3);
  }
  /* 点击缩放反馈 */
  .nav-item-box:active {
    transform: scale(0.95);
  }
  /* 登录头像样式 */
  .login-wrapper {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 40px;
    height: 40px;
    border-radius: 50%;
    background: rgba(200, 22, 30, 0.3);
    border: 2px solid rgba(200, 22, 30, 0.5);
    transition: all 0.4s ease;
    margin-left: 8px;
  }
  .nav-item-box:hover .login-wrapper {
    background: rgba(200, 22, 30, 0.6);
    border-color: #c8161e;
    transform: scale(1.08);
    box-shadow: 0 0 16px rgba(200, 22, 30, 0.5);
  }
</style>
