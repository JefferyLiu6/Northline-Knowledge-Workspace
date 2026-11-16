<template>
  <div class="manager-container">
    <header class="manager-header" @keydown.esc="closeNavigation(true)">
      <div class="manager-header-left">
        <button ref="menuToggle" class="manager-menu-toggle" type="button" aria-label="Toggle navigation"
                aria-controls="manager-navigation" :aria-expanded="navigationOpen"
                @click="navigationOpen = !navigationOpen">
          <el-icon><Fold /></el-icon>
        </button>
        <RouterLink to="/manager/home" aria-label="Knowledge Workspace dashboard" @click="closeNavigation()">
          <WorkspaceBrand />
        </RouterLink>
      </div>
      <div class="manager-header-center">
        <el-breadcrumb separator="/">
          <el-breadcrumb-item :to="{ path: '/manager/home' }">Workspace</el-breadcrumb-item>
          <el-breadcrumb-item>{{ route.meta.name }}</el-breadcrumb-item>
        </el-breadcrumb>
      </div>
      <div class="manager-header-right">
        <RouterLink class="manager-chat-link" to="/front/home">
          <el-icon><ChatDotRound /></el-icon><span>Open Q&amp;A</span>
        </RouterLink>
        <el-dropdown trigger="click">
          <button class="user-box" type="button" :aria-label="'Account menu for ' + (user.name || user.username || 'user')">
            <WorkspaceAvatar :user="user" />
          </button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="router.push('/manager/person')">Profile</el-dropdown-item>
              <el-dropdown-item @click="router.push('/manager/password')">Change Password</el-dropdown-item>
              <el-dropdown-item divided @click="logout">Sign out</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </header>

    <div class="manager-main">
      <div v-if="navigationOpen" class="manager-nav-backdrop" @click="closeNavigation(true)"></div>
      <nav id="manager-navigation" class="manager-main-left" :class="{ 'is-open': navigationOpen }"
           aria-label="Admin navigation" @keydown.esc="closeNavigation(true)">
        <el-menu :default-active="route.path" :default-openeds="openGroups" router
                 @select="closeNavigation()">
          <el-menu-item index="/manager/home">
            <el-icon><House /></el-icon><span>Dashboard</span>
          </el-menu-item>
          <template v-if="user.role === 'ADMIN'">
            <el-sub-menu v-for="group in groups" :key="group.name" :index="group.name">
              <template #title>
                <el-icon><component :is="group.icon" /></el-icon><span>{{ group.name }}</span>
              </template>
              <el-menu-item v-for="[path, label, Icon] in group.items" :key="path" :index="'/manager/' + path">
                <el-icon><component :is="Icon" /></el-icon><span>{{ label }}</span>
              </el-menu-item>
            </el-sub-menu>
          </template>
        </el-menu>
      </nav>
      <main class="manager-main-right">
        <RouterView v-slot="{ Component }">
          <div class="manager-page">
            <h1 v-if="showPageHeading" class="workspace-page-title">{{ route.meta.name }}</h1>
            <component :is="Component" @update-user="refreshUser" />
          </div>
        </RouterView>
      </main>
    </div>
  </div>
</template>

<script setup>
import request from "@/utils/request.js"
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Aim, ChatDotRound, Collection, DataAnalysis, Document, Files, Fold, House, List, Operation,
  Search, Setting, Tickets, User as UserIcon, VideoPlay,
} from '@element-plus/icons-vue'
import WorkspaceAvatar from '@/components/WorkspaceAvatar.vue'
import WorkspaceBrand from '@/components/WorkspaceBrand.vue'

const groups = [
  { name: 'Knowledge Management', icon: Collection, items: [
    ['knowledgeBase', 'Knowledge Bases', Files],
    ['knowledgeDocument', 'Document Management', Document],
    ['knowledgeChunk', 'Knowledge Chunks', Tickets],
    ['chunkStrategy', 'Chunking Strategy', Operation],
    ['retrievalStrategy', 'Retrieval Strategy', Search],
    ['retrievalTest', 'Retrieval Testing', VideoPlay],
    ['retrievalDebug', 'Retrieval Debugger', Aim],
  ] },
  { name: 'AI Configuration', icon: Setting, items: [
    ['aiModelConfig', 'AI Model Configuration', Setting],
    ['promptTemplate', 'Prompt Template', Document],
    ['functionTool', 'Tool Center', Operation],
    ['toolCallLog', 'Tool Call Log', List],
    ['agentTest', 'Agent Execution', VideoPlay],
    ['agentRun', 'Agent Run History', Tickets],
  ] },
  { name: 'Q&A Apps', icon: ChatDotRound, items: [
    ['qaApp', 'Application Management', Collection],
    ['qaChat', 'Q&A Testing', ChatDotRound],
    ['chatLog', 'Chat Logs and Feedback', List],
  ] },
  { name: 'Evaluation', icon: DataAnalysis, items: [
    ['evalDataset', 'Evaluation Datasets', Files],
    ['evalTask', 'Batch Evaluation', VideoPlay],
    ['evalDashboard', 'Strategy Comparison', DataAnalysis],
  ] },
  { name: 'User Management', icon: UserIcon, items: [['user', 'User Management', UserIcon]] },
]

const route = useRoute()
const router = useRouter()
const user = ref(JSON.parse(localStorage.getItem('xm-user') || '{}'))
const navigationOpen = ref(false)
const menuToggle = ref()
const openGroups = computed(() => {
  const active = groups.find(group => group.items.some(([path]) => route.path === '/manager/' + path))
  return [active?.name || groups[0].name]
})
const showPageHeading = computed(() => !['/manager/home', '/manager/knowledgeDocument'].includes(route.path))

const closeNavigation = (restoreFocus = false) => {
  if (!navigationOpen.value) return
  navigationOpen.value = false
  if (restoreFocus) menuToggle.value?.focus()
}

const refreshUser = () => {
  user.value = JSON.parse(localStorage.getItem('xm-user') || '{}')
}

const logout = async () => {
  await request.post("/logout")
  localStorage.removeItem('xm-user')
  router.push('/login')
}
</script>

<style scoped>
@import "@/assets/css/manager.css";
</style>
