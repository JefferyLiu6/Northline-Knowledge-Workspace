<template>
  <section class="dashboard">
    <header class="dashboard-header">
      <h1>Dashboard</h1>
      <p>Welcome, {{ user.name }}.</p>
    </header>

    <div class="dashboard-primary">
      <RouterLink v-for="link in primaryLinks" :key="link.to" :to="link.to" class="dashboard-feature">
        <el-icon class="dashboard-feature-icon"><component :is="link.icon" /></el-icon>
        <div>
          <h2>{{ link.title }} <el-icon><Right /></el-icon></h2>
          <p>{{ link.description }}</p>
        </div>
      </RouterLink>
    </div>

    <nav v-if="isAdmin" class="dashboard-shortcuts" aria-label="Admin shortcuts">
      <RouterLink v-for="link in shortcuts" :key="link.to" :to="link.to">
        <el-icon><component :is="link.icon" /></el-icon>
        <span>{{ link.title }}</span>
        <el-icon class="dashboard-arrow"><Right /></el-icon>
      </RouterLink>
    </nav>
  </section>
</template>

<script setup>
import { ChatDotRound, Collection, DataAnalysis, Document, Right, Search, Setting } from '@element-plus/icons-vue'

const user = JSON.parse(localStorage.getItem('xm-user') || '{}')
const isAdmin = user.role === 'ADMIN'
const documentLink = {
  to: '/manager/knowledgeDocument', icon: Document, title: 'Document Management',
  description: 'Upload, preview, and embed documents.',
}
const chatLink = {
  to: '/front/home', icon: ChatDotRound, title: 'Knowledge Q&A',
  description: 'Ask a question and inspect the sources.',
}
const primaryLinks = isAdmin ? [documentLink, chatLink] : [chatLink]
const shortcuts = [
  { to: '/manager/knowledgeBase', icon: Collection, title: 'Knowledge Bases' },
  { to: '/manager/retrievalTest', icon: Search, title: 'Retrieval Testing' },
  { to: '/manager/aiModelConfig', icon: Setting, title: 'AI Model Configuration' },
  { to: '/manager/evalTask', icon: DataAnalysis, title: 'Batch Evaluation' },
]
</script>

<style scoped>
.dashboard-header {
  margin-bottom: clamp(20px, 3vw, 32px);
}

.dashboard-header h1 {
  margin: 0;
  font-size: clamp(28px, 3.6vw, 42px);
  font-weight: 720;
  line-height: 1.15;
  letter-spacing: -.05em;
}

.dashboard-header p {
  margin: 7px 0 0;
  color: var(--ink-muted);
  font-size: clamp(14px, 1.55vw, 19px);
}

.dashboard-primary,
.dashboard-shortcuts {
  border: 1px solid var(--border-strong);
  border-radius: var(--radius);
  background: var(--surface);
}

.dashboard-primary {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 340px), 1fr));
  gap: 20px;
  padding: clamp(12px, 2vw, 26px);
}

.dashboard-feature {
  display: flex;
  align-items: center;
  gap: clamp(13px, 2vw, 25px);
  min-height: 128px;
  padding: clamp(14px, 2vw, 26px);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius);
  color: var(--accent-strong);
}

.dashboard-feature-icon {
  flex: none;
  font-size: clamp(28px, 4vw, 58px);
}

.dashboard-feature h2 {
  margin: 0;
  font-size: clamp(17px, 1.75vw, 24px);
  font-weight: 690;
  letter-spacing: -.025em;
}

.dashboard-feature h2 .el-icon {
  vertical-align: -.15em;
}

.dashboard-feature p {
  margin: 5px 0 0;
  color: var(--ink-muted);
}

.dashboard-shortcuts {
  margin-top: 21px;
}

.dashboard-shortcuts > a {
  display: flex;
  align-items: center;
  gap: 16px;
  min-height: 62px;
  padding: 10px clamp(16px, 2.5vw, 30px);
  color: var(--ink);
  font-size: clamp(15px, 1.75vw, 19px);
  font-weight: 650;
}

.dashboard-shortcuts > a:first-child {
  border-radius: var(--radius) var(--radius) 0 0;
}

.dashboard-shortcuts > a:last-child {
  border-radius: 0 0 var(--radius) var(--radius);
}

.dashboard-shortcuts > a + a {
  border-top: 1px solid var(--border);
}

.dashboard-shortcuts > a > .el-icon {
  font-size: 21px;
}

.dashboard-arrow {
  margin-left: auto;
}

.dashboard-feature:hover,
.dashboard-shortcuts > a:hover {
  background: #f6f6ff;
  color: var(--accent-strong);
}

@media (max-width: 500px) {
  .dashboard-primary {
    gap: 10px;
  }
  .dashboard-feature {
    min-height: 92px;
  }
}
</style>
