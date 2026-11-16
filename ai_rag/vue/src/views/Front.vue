<template>
  <div class="front-layout">
    <header class="front-header">
      <RouterLink class="front-brand" to="/front/home" aria-label="Knowledge Workspace Q&A">
        <WorkspaceBrand />
      </RouterLink>
      <nav class="front-header-right" aria-label="Account">
        <RouterLink v-if="user.role === 'ADMIN'" to="/manager/home" class="front-nav-link">
          <el-icon><Setting /></el-icon>Admin
        </RouterLink>
        <template v-if="!user.id">
          <RouterLink to="/login" class="front-nav-link">Sign in</RouterLink>
          <RouterLink to="/register" class="front-nav-link">Register</RouterLink>
        </template>
        <el-dropdown v-else trigger="click">
          <button type="button" class="front-account" :aria-label="'Account menu for ' + (user.name || user.username || 'user')">
            <WorkspaceAvatar :user="user" />
          </button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="router.push('/front/person')">Profile</el-dropdown-item>
              <el-dropdown-item divided @click="logout">Sign out</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </nav>
    </header>
    <main class="front-body">
      <RouterView @update-user="refreshUser" />
    </main>
  </div>
</template>

<script setup>
import request from "@/utils/request.js"
import { Setting } from '@element-plus/icons-vue'
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import WorkspaceAvatar from '@/components/WorkspaceAvatar.vue'
import WorkspaceBrand from '@/components/WorkspaceBrand.vue'

const router = useRouter()
const user = ref(JSON.parse(localStorage.getItem('xm-user') || '{}'))

const logout = async () => {
  await request.post("/logout")
  localStorage.removeItem('xm-user')
  router.push('/login')
}

const refreshUser = () => {
  user.value = JSON.parse(localStorage.getItem('xm-user') || '{}')
}
</script>

<style scoped>
@import "@/assets/css/front.css";
</style>
