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
export default defineComponent({
  name: 'SmartRecommend',
  setup(props) {
    const state = reactive({
      recommendedQuestions: []
    });
    return { state };
  },
  methods: {
    fetchRecommendedQuestions(wrongQuestion) {
      this.provider.call('fetchRecommendedQuestions', { wrongQuestion }).then((questions) => {
        this.state.recommendedQuestions = questions;
      });
    }
  }
});
</script>
<style scoped>
.smart-recommend {
  background: #fff;
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}
</style>