<template>
  <div class="quote-banner">
    <div class="quote-header">
      <div class="quote-source">
        <XIcon :icon="ReadingLamp" :size="18" color="#c41e3a"></XIcon>
        <span> 《人民公安报》每日金句</span>
      </div>
      <span class="quote-date"> {{ state.currentDate }}</span>
    </div>
    <div class="quote-body">
      <div class="quote-mark left-mark">“</div>
      <p class="quote-text">
        {{ state.quote }}
      </p>
      <div class="quote-mark right-mark">”</div>
    </div>
    <div class="quote-footer">
      <span class="quote-author">
        <span>
          <span> ——</span>
          <span> {{ state.author }}</span></span
        ></span
      >
      <button class="refresh-btn" @click="refreshQuote">
        <XIcon :icon="RefreshRight" :size="14" color="#c41e3a"></XIcon>
        <span> 换一句</span>
      </button>
    </div>
    <div class="quote-decoration"></div>
  </div>
</template>
<script lang="ts">
  // @ts-nocheck
  import { defineComponent, reactive } from 'vue';
  import { XIcon } from '@vtj/ui';
  import { ReadingLamp, RefreshRight } from '@vtj/icons';
  import { useProvider } from '@vtj/renderer';
  export default defineComponent({
    name: 'QuoteBanner',
    components: { XIcon },
    setup(props) {
      const provider = useProvider({ id: '11jve6eq7', version: '1778918000715' });
      const state = reactive({
        quote: '忠诚是公安队伍代代相传的政治基因，是融入血脉的人民警察之魂。',
        author: '人民公安报',
        currentDate: ''
      });
      return { state, props, provider, ReadingLamp, RefreshRight };
    },
    methods: {
      formatDate() {
        const d = new Date();
        this.state.currentDate = `${d.getFullYear()}/${d.getMonth() + 1}/${d.getDate()}`;
      },
      refreshQuote() {
        const quotes = [
          {
            text: '忠诚是公安队伍代代相传的政治基因，是融入血脉的人民警察之魂。',
            author: '人民公安报'
          },
          {
            text: '坚持以人民为中心的发展思想，把人民对美好生活的向往作为奋斗目标。',
            author: '人民公安报'
          },
          {
            text: '公平正义是执法司法工作的生命线，要努力让人民群众在每一起案件办理中都能感受到公平正义。',
            author: '人民公安报'
          },
          {
            text: '公安民警要坚定理想信念，强化责任担当，练就过硬本领，锤炼纪律作风。',
            author: '人民公安报'
          },
          {
            text: '国家安全是安邦定国的重要基石，维护国家安全是全国各族人民根本利益所在。',
            author: '人民公安报'
          }
        ];
        const next = quotes[Math.floor(Math.random() * quotes.length)];
        this.state.quote = next.text;
        this.state.author = next.author;
      }
    },
    mounted() {
      this.formatDate();
    }
  })
</script>
<style lang="css" scoped>
  .quote-banner {
    background: linear-gradient(135deg, #ffffff 0%, #fdfdff 100%);
    border-radius: 16px;
    padding: 70px 28px 75px;
    box-shadow: 0 2px 16px rgba(26, 43, 95, 0.06);
    position: relative;
    overflow: hidden;
    border-left: 4px solid #c41e3a;
  }
  .quote-decoration {
    position: absolute;
    top: -30px;
    right: -30px;
    width: 100px;
    height: 100px;
    background: radial-gradient(
      circle,
      rgba(196, 30, 58, 0.04) 0%,
      transparent 70%
    );
    border-radius: 50%;
  }
  .quote-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 14px;
  }
  .quote-source {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 15px;
    font-weight: 600;
    color: #1a2b5f;
  }
  .quote-date {
    font-size: 14px;
    color: #8a8faa;
    background: #f8f9fc;
    padding: 2px 10px;
    border-radius: 10px;
  }
  .quote-body {
    position: relative;
    padding: 8px 0;
  }
  .quote-text {
    font-size: 15px;
    line-height: 1.8;
    color: #33375a;
    font-weight: 500;
    letter-spacing: 0.5px;
    font-family: 'Noto Serif SC', 'STSong', 'Songti SC', serif;
  }
  .quote-mark {
    font-size: 48px;
    color: rgba(196, 30, 58, 0.12);
    font-family: Georgia, serif;
    line-height: 1;
  }
  .left-mark {
    position: absolute;
    top: -10px;
    left: -4px;
  }
  .right-mark {
    position: absolute;
    bottom: -20px;
    right: 0;
  }
  .quote-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-top: 22px;
  }
  .quote-author {
    font-size: 14px;
    color: #8a8faa;
    font-style: italic;
  }
  .refresh-btn {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 6px 12px;
    border: none;
    background: #fef0f2;
    color: #c41e3a;
    border-radius: 14px;
    font-size: 12px;
    cursor: pointer;
    transition: all 0.3s;
    font-weight: 500;
  }
  .refresh-btn:hover {
    background: #fde2e6;
    transform: scale(1.02);
  }
</style>
