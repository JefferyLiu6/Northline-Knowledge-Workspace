<template>
  <main class="not-found">
    <RouterLink class="not-found-brand" to="/" aria-label="Knowledge Workspace home"><WorkspaceBrand /></RouterLink>
    <div>
      <el-icon class="not-found-icon"><Document /></el-icon>
      <h1>Page not found</h1>
      <p>The address may have changed or the page may have been removed.</p>
      <RouterLink class="el-button el-button--primary" :to="home">Back to workspace</RouterLink>
    </div>
  </main>
</template>

<script setup>
import { Document } from '@element-plus/icons-vue'
import WorkspaceBrand from '@/components/WorkspaceBrand.vue'

const user = JSON.parse(localStorage.getItem('xm-user') || '{}')
const home = user.role === 'ADMIN' ? '/manager/home' : user.id ? '/front/home' : '/login'
</script>

<style scoped>
.not-found {
  min-height: 100dvh;
  display: grid;
  place-items: center;
  padding: 84px 24px 36px;
  text-align: center;
  background: var(--canvas);
}

.not-found-brand {
  position: absolute;
  top: 22px;
  left: 22px;
  color: var(--ink);
}

.not-found-icon {
  width: 58px;
  height: 58px;
  border-radius: 14px;
  background: var(--accent-soft);
  color: var(--accent-strong);
  font-size: 26px;
}

.not-found h1 {
  margin: 16px 0 0;
  font-size: clamp(29px, 5vw, 44px);
  letter-spacing: -.045em;
}

.not-found p {
  margin: 6px 0 24px;
  color: var(--ink-muted);
}
</style>
