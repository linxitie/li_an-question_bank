<template>
  <div class="ex-page">
    <header class="ex-head">
      <div>
        <h1>我的兑换</h1>
        <p class="ex-sub">
          金币兑换的订单都在这里。虚拟卡类当场发卡密，实物/需开通的商品显示「待发货/待开通」。
        </p>
      </div>
    </header>

    <MyExchangesPanel />
  </div>
</template>

<script setup lang="ts">
import MyExchangesPanel from '@/components/shop/MyExchangesPanel.vue';
</script>

<style scoped>
.ex-page {
  max-width: 920px;
  margin: 0 auto;
  padding: 24px 20px 48px;
  font-family: 'Noto Sans SC', 'PingFang SC', system-ui, sans-serif;
  color: #1a1a1a;
}

.ex-head {
  margin-bottom: 16px;
}
.ex-head h1 {
  margin: 0 0 6px;
  font-size: 24px;
  font-weight: 600;
}
.ex-sub {
  margin: 0;
  font-size: 13px;
  color: #6b7280;
  line-height: 1.6;
}
</style>
