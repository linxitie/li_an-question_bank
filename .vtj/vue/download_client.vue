<!-- 下载模块 -->
<template>
  <div class="download-page">
    <NavBar></NavBar>
    <main class="dl-main">
      <section class="dl-hero">
        <div class="hero-bg"></div>
        <div class="hero-content">
          <h1 class="hero-title">砺安题库 · 客户端</h1>
          <p class="hero-subtitle">多端同步，随时随地刷题备考</p>
          <p class="hero-desc">
            支持 Windows / macOS / iOS / Android
            全平台，数据实时同步，学习不间断
          </p>
        </div>
      </section>
      <section class="dl-cards">
        <div
          v-for="(platform, index) in platforms"
          :key="platform.name"
          class="dl-card">
          <div
            class="dl-icon div_2752jvf1ckl"
            :style="{ background: platform.bg }">
            <span> {{ platform.emoji }}</span>
          </div>
          <h3>
            {{ platform.name }}
          </h3>
          <p>
            {{ platform.version }}
          </p>
          <p class="dl-size">
            {{ platform.size }}
          </p>
          <button class="dl-btn" @click="handleDownload(platform.name)">
            <XIcon :icon="Download" :size="16" color="#ffffff"></XIcon>
            <span> 立即下载</span>
          </button>
        </div>
      </section>
      <div class="dl-qr-section">
        <div class="qr-card">
          <div class="qr-placeholder">
            <span class="qr-emoji"> 📱</span>
          </div>
          <p class="qr-label">扫码下载手机App</p>
          <p class="qr-tip">iOS / Android</p>
        </div>
        <div class="qr-card">
          <div class="qr-placeholder">
            <span class="qr-emoji"> 💻</span>
          </div>
          <p class="qr-label">PC客户端下载</p>
          <p class="qr-tip">Windows / macOS</p>
        </div>
      </div>
      <div class="dl-features">
        <h2>客户端特色功能</h2>
        <div class="feat-items">
          <div
            v-for="(feat, index) in clientFeatures"
            :key="feat.title"
            class="feat-item">
            <div
              class="feat-icon div_275djvf1ckl"
              :style="{ background: feat.bg }">
              {{ feat.emoji }}
            </div>
            <h4>
              {{ feat.title }}
            </h4>
            <p>
              {{ feat.desc }}
            </p>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>
<script lang="ts">
  // @ts-nocheck
  import { defineComponent, reactive } from 'vue';
  import { XIcon } from '@vtj/ui';
  import { Download } from '@vtj/icons';
  import NavBar from './navbar.vue';
  import { useProvider } from '@vtj/renderer';
  import { ElMessage } from 'element-plus';
  export default defineComponent({
    name: 'DownloadClient',
    components: { NavBar, XIcon },
    setup(props) {
      const provider = useProvider({ id: 'download_client', version: '1778919369987' });
      const state = reactive({});
      return { state, props, provider, Download };
    },
    computed: {
      platforms() {
        return [
          {
            name: 'Windows',
            version: 'v3.1.1 最新版',
            size: '168 MB',
            emoji: '🪟',
            bg: 'linear-gradient(135deg, #0078d4, #00bcf2)'
          },
          {
            name: 'macOS',
            version: 'v3.1.1 最新版',
            size: '152 MB',
            emoji: '🍎',
            bg: 'linear-gradient(135deg, #1a1a1a, #4a4a4a)'
          },
          {
            name: 'iOS',
            version: 'v3.1.1',
            size: '98 MB',
            emoji: '📱',
            bg: 'linear-gradient(135deg, #1a2b5f, #3b82f6)'
          },
          {
            name: 'Android',
            version: 'v3.1.1',
            size: '76 MB',
            emoji: '🤖',
            bg: 'linear-gradient(135deg, #34d399, #10b981)'
          }
        ];
      },
      clientFeatures() {
        return [
          {
            title: '离线刷题',
            desc: '下载题库到本地，无需网络也能随时刷题，流量不愁。',
            emoji: '📴',
            bg: '#eff6ff'
          },
          {
            title: '多端同步',
            desc: '手机、平板、电脑无缝切换，学习进度实时同步。',
            emoji: '🔄',
            bg: '#fef2f2'
          },
          {
            title: '极速启动',
            desc: '客户端秒开，无需等待网页加载，即点即刷。',
            emoji: '⚡',
            bg: '#fffbeb'
          },
          {
            title: '离线更新',
            desc: '自动检测题库更新，WiFi环境下静默下载。',
            emoji: '🔔',
            bg: '#f0fdf4'
          }
        ];
      }
    },
    methods: {
      handleDownload(name) {
        ElMessage.success('正在准备下载 ' + name + ' 客户端...');
      }
    }
  })
</script>
<style lang="css" scoped>
  .download-page {
    min-height: 100vh;
    background: linear-gradient(180deg, #f8f9fc 0%, #f1f3f8 100%);
    font-family: 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  }
  .dl-main {
    max-width: 1100px;
    margin: 0 auto;
    padding: 24px 32px 40px;
  }
  .dl-hero {
    text-align: center;
    padding: 60px 20px 40px;
    position: relative;
    margin-bottom: 40px;
  }
  .hero-bg {
    position: absolute;
    top: 0;
    left: 50%;
    transform: translateX(-50%);
    width: 400px;
    height: 400px;
    background: radial-gradient(
      circle,
      rgba(196, 30, 58, 0.08) 0%,
      transparent 70%
    );
    border-radius: 50%;
  }
  .hero-content {
    position: relative;
    z-index: 1;
  }
  .hero-title {
    font-size: 42px;
    font-weight: 900;
    color: #1a2b5f;
    margin: 0;
    letter-spacing: 3px;
  }
  .hero-subtitle {
    font-size: 18px;
    color: #5a6488;
    margin: 12px 0 8px;
  }
  .hero-desc {
    font-size: 14px;
    color: #8a8faa;
  }
  .dl-cards {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 20px;
    margin-bottom: 40px;
  }
  .dl-card {
    background: #ffffff;
    border-radius: 20px;
    padding: 32px 20px;
    text-align: center;
    box-shadow: 0 2px 16px rgba(26, 43, 95, 0.06);
    transition: all 0.3s;
  }
  .dl-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 8px 28px rgba(26, 43, 95, 0.12);
  }
  .dl-icon {
    width: 72px;
    height: 72px;
    border-radius: 20px;
    margin: 0 auto 16px;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .dl-icon span {
    font-size: 36px;
  }
  .dl-card h3 {
    font-size: 18px;
    font-weight: 800;
    color: #1a2b5f;
    margin: 0 0 4px;
  }
  .dl-card p {
    font-size: 13px;
    color: #5a6488;
    margin: 0;
  }
  .dl-size {
    font-size: 11px !important;
    color: #8a8faa !important;
    margin: 4px 0 16px !important;
  }
  .dl-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 10px 24px;
    border: none;
    border-radius: 12px;
    background: linear-gradient(135deg, #c41e3a, #e8384f);
    color: #ffffff;
    font-size: 14px;
    font-weight: 700;
    cursor: pointer;
    transition: all 0.3s;
    box-shadow: 0 2px 10px rgba(196, 30, 58, 0.3);
  }
  .dl-btn:hover {
    transform: scale(1.04);
    box-shadow: 0 4px 16px rgba(196, 30, 58, 0.4);
  }
  .dl-qr-section {
    display: flex;
    gap: 20px;
    margin-bottom: 40px;
    justify-content: center;
  }
  .qr-card {
    background: #ffffff;
    border-radius: 20px;
    padding: 24px;
    text-align: center;
    box-shadow: 0 2px 12px rgba(26, 43, 95, 0.04);
    width: 200px;
  }
  .qr-placeholder {
    width: 120px;
    height: 120px;
    margin: 0 auto 16px;
    background: #f8f9fc;
    border-radius: 16px;
    display: flex;
    align-items: center;
    justify-content: center;
    border: 2px dashed #e8eaf0;
  }
  .qr-emoji {
    font-size: 48px;
  }
  .qr-label {
    font-size: 14px;
    font-weight: 700;
    color: #1a2b5f;
    margin: 0 0 4px;
  }
  .qr-tip {
    font-size: 11px;
    color: #8a8faa;
    margin: 0;
  }
  .dl-features h2 {
    text-align: center;
    font-size: 20px;
    font-weight: 800;
    color: #1a2b5f;
    margin: 0 0 24px;
  }
  .feat-items {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
  }
  .feat-item {
    background: #ffffff;
    border-radius: 16px;
    padding: 24px;
    box-shadow: 0 2px 10px rgba(26, 43, 95, 0.04);
    text-align: center;
    transition: all 0.3s;
  }
  .feat-item:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 16px rgba(26, 43, 95, 0.08);
  }
  .feat-icon {
    width: 52px;
    height: 52px;
    border-radius: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 24px;
    margin: 0 auto 14px;
  }
  .feat-item h4 {
    font-size: 15px;
    font-weight: 700;
    color: #1a2b5f;
    margin: 0 0 6px;
  }
  .feat-item p {
    font-size: 12px;
    color: #5a6488;
    margin: 0;
    line-height: 1.5;
  }
</style>
