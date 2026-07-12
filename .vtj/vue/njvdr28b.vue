<template>
  <div class="about-page">
    <NavBar></NavBar>
    <main class="about-main">
      <div class="hero-section">
        <div class="hero-overlay">
          <h1 class="hero-title">砺安题库</h1>
          <p class="hero-subtitle">专注公安联考 · 助力警官梦</p>
          <div class="hero-stats">
            <div class="hero-stat">
              <span class="hs-number"> 50,000+</span>
              <span class="hs-label"> 精选题库</span>
            </div>
            <div class="hero-stat">
              <span class="hs-number"> 10,000+</span>
              <span class="hs-label"> 注册学员</span>
            </div>
            <div class="hero-stat">
              <span class="hs-number"> 98.5%</span>
              <span class="hs-label"> 好评率</span>
            </div>
          </div>
        </div>
      </div>
      <section class="feature-section">
        <h2 class="section-title">
          <XIcon :icon="StarFilled" :size="22" color="#c41e3a"></XIcon>
          <span> 核心功能</span>
        </h2>
        <div class="feature-grid">
          <div
            v-for="(feat, index) in features"
            :key="feat.title"
            class="feature-card">
            <div
              class="feat-icon div_2714jveuxoi"
              :style="{ background: feat.bg }">
              <span> {{ feat.emoji }}</span>
            </div>
            <h3>
              {{ feat.title }}
            </h3>
            <p>
              {{ feat.desc }}
            </p>
          </div>
        </div>
      </section>
      <section class="advantage-section">
        <h2 class="section-title">
          <XIcon :icon="TrophyBase" :size="22" color="#c41e3a"></XIcon>
          <span> 为什么选择砺安题库</span>
        </h2>
        <div class="adv-grid">
          <div
            v-for="(adv, index) in advantages"
            :key="adv.title"
            class="adv-card">
            <div class="adv-num">
              {{ adv.num }}
            </div>
            <div class="adv-content">
              <h4>
                {{ adv.title }}
              </h4>
              <p>
                {{ adv.desc }}
              </p>
            </div>
          </div>
        </div>
      </section>
      <section class="team-section">
        <h2 class="section-title">
          <XIcon :icon="UserFilled" :size="22" color="#c41e3a"></XIcon>
          <span> 关于我们</span>
        </h2>
        <div class="team-content">
          <p>
            砺安题库由资深公安教育专家和一线民警联合打造，致力于为广大警校生和社招考生提供专业、精准、高效的公安联考备考服务。我们深谙公安考试命题规律，持续更新题库内容，确保每一道题目都贴近真实考情。
          </p>
          <p>
            我们的使命：用科技赋能公安教育，让每一位怀揣警官梦想的考生都能得到最优质的备考资源。
          </p>
        </div>
      </section>
      <footer class="about-footer">
        <p>
          © 2025 砺安题库 · 联系方式：service@lianzhi.com ·
          客服热线：400-000-0000
        </p>
      </footer>
    </main>
  </div>
</template>
<script lang="ts">
  // @ts-nocheck
  import { defineComponent, reactive } from 'vue';
  import { XIcon } from '@vtj/ui';
  import { StarFilled, TrophyBase, UserFilled } from '@vtj/icons';
  import NavBar from './ijvdn7sw.vue';
  import { useProvider } from '@vtj/renderer';
  export default defineComponent({
    name: 'About',
    components: { NavBar, XIcon },
    setup(props) {
      const provider = useProvider({ id: 'njvdr28b', version: '1778919070888' });
      const state = reactive({});
      return { state, props, provider, StarFilled, TrophyBase, UserFilled };
    },
    computed: {
      features() {
        return [
          {
            title: '智能组卷',
            desc: '基于AI算法，根据个人薄弱点智能生成专属试卷，高效提分。',
            emoji: '🤖',
            bg: '#eff6ff'
          },
          {
            title: '全真模考',
            desc: '还原真实机考环境，计时计分，实战演练，提前适应考场节奏。',
            emoji: '💻',
            bg: '#fef2f2'
          },
          {
            title: '错题分析',
            desc: '自动归纳错题，知识点分类统计，精准推送同类题目强化训练。',
            emoji: '📊',
            bg: '#fffbeb'
          },
          {
            title: '阶梯刷题',
            desc: '按难度分级，从基础到冲刺，循序渐进提升做题能力。',
            emoji: '🪜',
            bg: '#f0fdf4'
          },
          {
            title: '备考资料',
            desc: '行测/申论/公专精品课程，视频讲解与文档分析结合。',
            emoji: '📚',
            bg: '#ede9fe'
          },
          {
            title: '学习记录',
            desc: '详细记录每日学习情况，打卡签到激励，可视化成长轨迹。',
            emoji: '📅',
            bg: '#fdf2f8'
          }
        ];
      },
      advantages() {
        return [
          {
            num: '01',
            title: '权威题库',
            desc: '资深公安教育专家团队精心编纂，紧贴考试大纲。'
          },
          {
            num: '02',
            title: '实时更新',
            desc: '考题资源动态更新，第一时间反映最新命题趋势。'
          },
          {
            num: '03',
            title: '精准解析',
            desc: '每道题目附带详细解析，知其然更知其所以然。'
          },
          {
            num: '04',
            title: '个性化推荐',
            desc: 'AI算法分析薄弱环节，智能推送针对性训练。'
          }
        ];
      }
    }
  })
</script>
<style lang="css" scoped>
  .about-page {
    min-height: 100vh;
    background: linear-gradient(180deg, #f8f9fc 0%, #f1f3f8 100%);
    font-family: 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  }
  .about-main {
    max-width: 1200px;
    margin: 0 auto;
    padding: 24px 32px 40px;
  }
  /* Hero */
  .hero-section {
    background: linear-gradient(135deg, #1a2b5f 0%, #1e3470 50%, #1a2b5f 100%);
    border-radius: 24px;
    padding: 60px 40px;
    margin-bottom: 40px;
    position: relative;
    overflow: hidden;
    text-align: center;
  }
  .hero-section::before {
    content: '';
    position: absolute;
    top: -50%;
    left: -50%;
    width: 200%;
    height: 200%;
    background: radial-gradient(
      circle,
      rgba(196, 30, 58, 0.1) 0%,
      transparent 50%
    );
  }
  .hero-overlay {
    position: relative;
    z-index: 1;
  }
  .hero-title {
    font-size: 52px;
    font-weight: 900;
    color: #ffffff;
    margin: 0;
    letter-spacing: 6px;
    text-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
  }
  .hero-subtitle {
    font-size: 18px;
    color: rgba(255, 255, 255, 0.8);
    margin: 12px 0 32px;
    letter-spacing: 2px;
  }
  .hero-stats {
    display: flex;
    justify-content: center;
    gap: 60px;
  }
  .hero-stat {
    text-align: center;
  }
  .hs-number {
    display: block;
    font-size: 36px;
    font-weight: 900;
    color: #ffd700;
    font-family: 'DIN Alternate', 'SF Pro Display', sans-serif;
  }
  .hs-label {
    font-size: 13px;
    color: rgba(255, 255, 255, 0.7);
    margin-top: 4px;
  }
  /* Features */
  .section-title {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 20px;
    font-weight: 800;
    color: #1a2b5f;
    margin: 0 0 24px;
  }
  .feature-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 20px;
    margin-bottom: 40px;
  }
  .feature-card {
    background: #ffffff;
    border-radius: 16px;
    padding: 28px;
    box-shadow: 0 2px 12px rgba(26, 43, 95, 0.05);
    transition: all 0.3s;
  }
  .feature-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 6px 24px rgba(26, 43, 95, 0.1);
  }
  .feat-icon {
    width: 52px;
    height: 52px;
    border-radius: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 24px;
    margin-bottom: 16px;
  }
  .feature-card h3 {
    font-size: 17px;
    font-weight: 700;
    color: #1a2b5f;
    margin: 0 0 8px;
  }
  .feature-card p {
    font-size: 13px;
    color: #5a6488;
    line-height: 1.6;
    margin: 0;
  }
  /* Advantages */
  .adv-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 16px;
    margin-bottom: 40px;
  }
  .adv-card {
    background: #ffffff;
    border-radius: 16px;
    padding: 24px;
    display: flex;
    gap: 20px;
    box-shadow: 0 2px 10px rgba(26, 43, 95, 0.04);
  }
  .adv-num {
    font-size: 32px;
    font-weight: 900;
    color: #c41e3a;
    line-height: 1;
    min-width: 50px;
  }
  .adv-content h4 {
    font-size: 16px;
    font-weight: 700;
    color: #1a2b5f;
    margin: 0 0 6px;
  }
  .adv-content p {
    font-size: 13px;
    color: #5a6488;
    margin: 0;
    line-height: 1.5;
  }
  /* Team */
  .team-section {
    margin-bottom: 40px;
  }
  .team-content {
    background: #ffffff;
    border-radius: 16px;
    padding: 28px;
    box-shadow: 0 2px 12px rgba(26, 43, 95, 0.04);
  }
  .team-content p {
    font-size: 14px;
    color: #333;
    line-height: 1.8;
    margin: 0 0 12px;
  }
  .team-content p:last-child {
    margin-bottom: 0;
  }
  /* Footer */
  .about-footer {
    text-align: center;
    padding: 20px 0 0;
    border-top: 1px solid #e8eaf0;
  }
  .about-footer p {
    font-size: 12px;
    color: #8a8faa;
    margin: 0;
  }
</style>
