<!-- 职能组卷模块 -->
<template>
  <div class="smart-recommend">
    <h3>智能推荐相似题目</h3>
    <ul>
      <li v-for="(q, index) in state.recommendedQuestions" :key="index">
        {{ q.title }}
      </li>
    </ul>
  </div>
</template>
<script lang="ts">
import { defineComponent, reactive } from 'vue';
import { useProvider } from '@vtj/renderer';
export default defineComponent({
  name: 'SmartRecommend',
  setup(props) {
    const provider = useProvider({ id: 'smart_recommend', version: '1778918346107' });
    const state = reactive({
      recommendedQuestions: []
    });
    return { state, provider };
  },
  methods: {
    fetchRecommendedQuestions(wrongQuestion) {
      this.provider.call('fetchRecommendedQuestions', { wrongQuestion }).then((questions) => {
        this.recommendedQuestions = questions;
      });
    }
  }
});
</script>
<style lang="css" scoped>
.smart-recommend {
  background: #ffffff;
  padding: 20px 24px;
  border-radius: 16px;
  box-shadow: 0 2px 16px rgba(26, 43, 95, 0.06);
  font-family: 'Noto Sans SC', 'PingFang SC', sans-serif;
}
.smart-recommend h3 {
  font-size: 17px;
  font-weight: 700;
  color: #1a2b5f;
  margin: 0 0 12px;
}
.smart-recommend ul {
  list-style: none;
  padding: 0;
  margin: 0;
}
.smart-recommend li {
  padding: 8px 0;
  font-size: 14px;
  color: #5a6488;
  border-bottom: 1px solid #f0f2f5;
}
</style>