<template>
  <main class="account-layout">
    <aside class="account-art">
      <WorkspaceBrand />
      <p>Find answers in your company knowledge.</p>
    </aside>
    <section class="account-panel">
      <div class="account-content">
        <div class="account-mobile-brand"><WorkspaceBrand /></div>
        <h1>{{ title }}</h1>
        <p>{{ description }}</p>
        <slot />
      </div>
    </section>
  </main>
</template>

<script setup>
import WorkspaceBrand from '@/components/WorkspaceBrand.vue'

defineProps({
  title: { type: String, required: true },
  description: { type: String, required: true },
})
</script>

<style>
.account-layout {
  min-height: 100dvh;
  display: grid;
  grid-template-columns: 47.5% minmax(0, 1fr);
  background: #fff;
}

.account-art {
  min-height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 40px;
  padding: clamp(25px, 3vw, 52px);
  color: white;
  background: #101a28 url('@/assets/imgs/workspace-library.webp') center center / cover no-repeat;
}

.account-art .workspace-brand {
  font-size: clamp(19px, 2.1vw, 30px);
  text-shadow: 0 2px 9px #0b1323;
}

.account-art p {
  max-width: 13em;
  margin: 0;
  font-size: clamp(32px, 3.5vw, 56px);
  font-weight: 680;
  line-height: 1.05;
  letter-spacing: -.055em;
  text-wrap: balance;
  text-shadow: 0 2px 18px #080d18, 0 0 6px #080d18;
}

.account-panel {
  display: grid;
  place-items: center;
  min-width: 0;
  padding: clamp(24px, 5vw, 80px);
}

.account-content {
  width: min(100%, 410px);
}

.account-mobile-brand {
  display: none;
}

.account-content h1 {
  margin: 0;
  color: var(--ink);
  font-size: clamp(38px, 4vw, 56px);
  font-weight: 720;
  line-height: 1.1;
  letter-spacing: -.055em;
}

.account-content > p {
  margin: 9px 0 34px;
  color: var(--ink-muted);
  font-size: clamp(15px, 1.55vw, 20px);
}

.account-content .el-form-item {
  margin-bottom: 25px;
}

.account-content .el-form-item__label {
  display: inline-block;
  height: auto;
  margin-bottom: 7px;
  padding: 0;
  color: var(--ink);
  font-size: 14px;
  font-weight: 640;
  line-height: 1.4;
}

.account-content .el-input {
  --el-input-height: 50px;
  --el-input-border-radius: 9px;
}

.account-content .el-input__wrapper {
  border-radius: 9px;
}

.account-content .account-submit {
  width: 100%;
  min-height: 49px;
  margin-top: 4px;
  border-radius: 9px;
  font-size: 15px;
}

.account-alternate {
  margin: 21px 0 0;
  text-align: center;
}

.account-alternate a {
  color: var(--accent-strong);
  font-weight: 650;
}

.account-alternate a:hover {
  text-decoration: underline;
}

@media (max-width: 720px) {
  .account-layout {
    grid-template-columns: minmax(0, 1fr);
  }

  .account-art {
    display: none;
  }

  .account-panel {
    align-items: start;
    padding-top: clamp(26px, 10vh, 80px);
  }

  .account-mobile-brand {
    display: block;
    margin-bottom: clamp(36px, 8vh, 74px);
  }
}
</style>
