<template>
  <div class="gold-purchase-page">
    <NavBar></NavBar>
    <main class="gp-main">
      <div class="gp-header">
        <h2>
          <XIcon :icon="ShoppingCartFull" :size="24" color="#f59e0b"></XIcon>
          <span> 金币购</span>
        </h2>
        <div class="gold-balance">
          <span class="balance-label"> 我的金币</span>
          <span class="balance-value"> {{ state.balance }}</span>
          <XIcon :icon="Medal" :size="20" color="#f59e0b"></XIcon>
        </div>
      </div>
      <div class="gp-section">
        <h3 class="section-title">
          <XIcon :icon="Shop" :size="18" color="#c41e3a"></XIcon>
          <span> 兑换商城</span>
        </h3>
        <div class="goods-grid">
          <div
            v-for="(item, index) in goodsList"
            :key="item.id"
            class="goods-card">
            <div class="goods-image">
              <span class="goods-emoji"> {{ item.icon }}</span>
            </div>
            <div class="goods-info">
              <h4 class="goods-name">
                {{ item.name }}
              </h4>
              <p class="goods-desc">
                {{ item.desc }}
              </p>
              <div class="goods-footer">
                <span class="goods-price">
                  <XIcon :icon="GoldMedal" :size="14" color="#f59e0b"></XIcon>
                  <span>
                    <span> </span>
                    <span> {{ item.price }}</span>
                    <span> 金币</span></span
                  ></span
                >
                <button
                  class="buy-btn"
                  :disabled="state.balance < item.price"
                  @click="handleBuy(item)">
                  {{ state.balance < item.price ? '金币不足' : '兑换' }}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div class="gp-dual">
        <div class="gp-card">
          <h4>
            <XIcon :icon="RefreshRight" :size="16" color="#10b981"></XIcon>
            <span> 金币使用记录</span>
          </h4>
          <div class="record-list">
            <div
              v-for="(r, idx) in state.usedRecords"
              :key="idx"
              class="record-item">
              <span class="record-desc"> {{ r.desc }}</span>
              <span class="record-amount minus">
                <span>
                  <span> -</span>
                  <span> {{ r.amount }}</span></span
                ></span
              >
              <span class="record-date"> {{ r.date }}</span>
            </div>
          </div>
        </div>
        <div class="gp-card">
          <h4>
            <XIcon :icon="CirclePlus" :size="16" color="#3b82f6"></XIcon>
            <span> 金币获得记录</span>
          </h4>
          <div class="record-list">
            <div
              v-for="(r, idx) in state.earnedRecords"
              :key="idx"
              class="record-item">
              <span class="record-desc"> {{ r.desc }}</span>
              <span class="record-amount plus">
                <span>
                  <span> +</span>
                  <span> {{ r.amount }}</span></span
                ></span
              >
              <span class="record-date"> {{ r.date }}</span>
            </div>
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
  import {
    ShoppingCartFull,
    Medal,
    Shop,
    GoldMedal,
    RefreshRight,
    CirclePlus
  } from '@vtj/icons';
  import NavBar from './ijvdn7sw.vue';
  import { useProvider } from '@vtj/renderer';
  export default defineComponent({
    name: 'GoldPurchase',
    components: { NavBar, XIcon },
    setup(props) {
      const provider = useProvider({ id: 'tjvdux1w', version: '1778918740312' });
      const state = reactive({
        balance: 1280,
        usedRecords: [],
        earnedRecords: []
      });
      return {
        state,
        props,
        provider,
        ShoppingCartFull,
        Medal,
        Shop,
        GoldMedal,
        RefreshRight,
        CirclePlus
      };
    },
    computed: {
      goodsList() {
        return [
          {
            id: 1,
            name: '精品文具套装',
            desc: '含笔记本、签字笔、文件袋等',
            price: 200,
            icon: '✏️'
          },
          {
            id: 2,
            name: '公安联考专用教材',
            desc: '最新版行测+申论+公专三本装',
            price: 500,
            icon: '📚'
          },
          {
            id: 3,
            name: '申论精批服务',
            desc: '教师一对一批改，详细点评',
            price: 800,
            icon: '📝'
          },
          {
            id: 4,
            name: '行测精讲视频课',
            desc: '16课时名师精讲+配套练习',
            price: 600,
            icon: '🎬'
          },
          {
            id: 5,
            name: '公专知识卡片',
            desc: '全套必背知识点便携卡片',
            price: 300,
            icon: '🃏'
          },
          {
            id: 6,
            name: '模拟考试券',
            desc: '校内排名模拟考试资格',
            price: 150,
            icon: '🎫'
          }
        ];
      }
    },
    methods: {
      handleBuy(item) {
        if (this.state.balance >= item.price) {
          this.state.balance -= item.price;
          this.state.usedRecords.unshift({
            desc: item.name,
            amount: item.price,
            date: new Date().toISOString().slice(0, 10)
          });
          this.$message.success('兑换成功！');
        } else {
          this.$message.warning('金币不足，快去刷题赚金币吧');
        }
      },
      loadRecords() {
        this.state.usedRecords = [
          { desc: '行测精讲视频课', amount: 600, date: '2024-12-20' },
          { desc: '模拟考试券', amount: 150, date: '2024-12-18' }
        ];
        this.state.earnedRecords = [
          { desc: '每日签到奖励', amount: 10, date: '2024-12-22' },
          { desc: '完成一套试卷', amount: 50, date: '2024-12-21' },
          { desc: '连续刷题7天', amount: 100, date: '2024-12-20' },
          { desc: '分享题库给好友', amount: 30, date: '2024-12-19' }
        ];
      }
    },
    mounted() {
      this.loadRecords();
    }
  })
</script>
<style lang="css" scoped>
  .gold-purchase-page {
    min-height: 100vh;
    background: linear-gradient(180deg, #f8f9fc 0%, #f1f3f8 100%);
    font-family: 'Noto Sans SC', 'PingFang SC', sans-serif;
  }
  .gp-main {
    max-width: 1300px;
    margin: 0 auto;
    padding: 24px 32px 40px;
  }
  .gp-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 28px;
  }
  .gp-header h2 {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 22px;
    font-weight: 800;
    color: #1a2b5f;
    margin: 0;
  }
  .gold-balance {
    display: flex;
    align-items: center;
    gap: 8px;
    background: linear-gradient(135deg, #fffbeb, #fef3c7);
    padding: 12px 24px;
    border-radius: 18px;
    box-shadow: 0 2px 10px rgba(245, 158, 11, 0.2);
  }
  .balance-label {
    font-size: 13px;
    color: #92400e;
    font-weight: 500;
  }
  .balance-value {
    font-size: 28px;
    font-weight: 900;
    color: #b45309;
    font-family: 'DIN Alternate', sans-serif;
  }
  .gp-section {
    margin-bottom: 28px;
  }
  .section-title {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 17px;
    font-weight: 700;
    color: #1a2b5f;
    margin: 0 0 16px;
  }
  .goods-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
  }
  .goods-card {
    background: #ffffff;
    border-radius: 18px;
    padding: 20px;
    box-shadow: 0 2px 14px rgba(26, 43, 95, 0.05);
    transition: all 0.3s;
    cursor: pointer;
    display: flex;
    gap: 16px;
  }
  .goods-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 6px 24px rgba(26, 43, 95, 0.1);
  }
  .goods-image {
    width: 64px;
    height: 64px;
    border-radius: 16px;
    background: linear-gradient(135deg, #f8f9fc, #f0f2f5);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }
  .goods-emoji {
    font-size: 30px;
  }
  .goods-info {
    flex: 1;
    display: flex;
    flex-direction: column;
  }
  .goods-name {
    font-size: 15px;
    font-weight: 700;
    color: #1a2b5f;
    margin: 0 0 4px;
  }
  .goods-desc {
    font-size: 12px;
    color: #8a8faa;
    margin: 0 0 12px;
    flex: 1;
  }
  .goods-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .goods-price {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 14px;
    font-weight: 700;
    color: #b45309;
  }
  .buy-btn {
    padding: 6px 16px;
    background: linear-gradient(135deg, #1a2b5f, #1e3470);
    color: #fff;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 600;
    transition: all 0.3s;
  }
  .buy-btn:hover:not(:disabled) {
    background: linear-gradient(135deg, #c41e3a, #e8384f);
  }
  .buy-btn:disabled {
    background: #d1d5db;
    cursor: default;
  }
  .gp-dual {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
  }
  .gp-card {
    background: #ffffff;
    border-radius: 16px;
    padding: 24px;
    box-shadow: 0 2px 12px rgba(26, 43, 95, 0.04);
  }
  .gp-card h4 {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 15px;
    font-weight: 700;
    color: #1a2b5f;
    margin: 0 0 16px;
  }
  .record-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .record-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 8px 12px;
    background: #f8f9fc;
    border-radius: 10px;
    font-size: 13px;
  }
  .record-desc {
    flex: 1;
    color: #333;
  }
  .record-amount {
    font-weight: 700;
  }
  .record-amount.minus {
    color: #ef4444;
  }
  .record-amount.plus {
    color: #10b981;
  }
  .record-date {
    color: #8a8faa;
    font-size: 11px;
  }
</style>
