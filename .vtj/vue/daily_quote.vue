<template>
  <PersonalGoalCard></PersonalGoalCard>
  <CountdownTimer></CountdownTimer>
</template>
<script lang="ts">
  // @ts-nocheck
  import { defineComponent, reactive } from 'vue';
  import PersonalGoalCard from './personal_goal.vue';
  import CountdownTimer from './countdown_block.vue';
  import { useProvider } from '@vtj/renderer';
  export default defineComponent({
    name: 'DailyQuote',
    components: { PersonalGoalCard, CountdownTimer },
    setup(props) {
      const provider = useProvider({ id: 'daily_quote', version: '1778914860907' });
      const state = reactive({});
      return { state, props, provider };
    }
  })
</script>
<style lang="css" scoped>
  /* 组件样式内容 */
</style>
