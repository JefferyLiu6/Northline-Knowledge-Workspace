<template>
  <section class="card profile-panel">
    <el-form :model="data.user" label-position="top" @submit.prevent="update">
      <div class="profile-photo">
        <WorkspaceAvatar :user="data.user" :size="58" />
        <el-upload :action="baseUrl + '/files/upload'" :headers="uploadHeaders" :on-success="handleFileUpload"
                   :show-file-list="false" accept="image/*">
          <el-button>Change photo</el-button>
        </el-upload>
      </div>
      <el-form-item label="Username">
        <el-input v-model="data.user.username" disabled />
      </el-form-item>
      <el-form-item label="Name">
        <el-input v-model="data.user.name" autocomplete="name" />
      </el-form-item>
      <el-form-item label="Phone">
        <el-input v-model="data.user.phone" type="tel" autocomplete="tel" />
      </el-form-item>
      <el-form-item label="Email">
        <el-input v-model="data.user.email" type="email" autocomplete="email" />
      </el-form-item>
      <el-button type="primary" native-type="submit">Save changes</el-button>
    </el-form>
  </section>
</template>

<script setup>
const uploadHeaders = { token: JSON.parse(localStorage.getItem("xm-user") || "{}").token }
import WorkspaceAvatar from "@/components/WorkspaceAvatar.vue";
import { reactive } from "vue";
import request from "@/utils/request.js";
import {ElMessage} from "element-plus";

// The header uploads its own request and does not leave. request.js, action requires full address
const baseUrl = import.meta.env.VITE_BASE_URL

const data = reactive({
  // Take user information from login to localStorage as the initial form value.
  // id, username, name, phone, email, avatar already in there. You don't have to check the interface again on the page.
  user: JSON.parse(localStorage.getItem('xm-user') || '{}')
})

const handleFileUpload = (res) => {
  if (res.code !== "200") {
    ElMessage.error(res.msg || "Upload failed")
    return
  }
  // The res.data returned from the backend after uploading success is a file download address written into data.user.avatar,
  // Img in the template displays a new header immediately, and the dot is saved before actually writing into the user table
  data.user.avatar = res.data
}

// After saving success, you must notify the outer layout to refresh the top right corner of your head and name.
// Outer floor, Manager.vu overheard the incident on RouterView.
const emit = defineEmits(['updateUser'])

const update = () => {
  // Data.user with id and backend to update the user log by pressing id;
  // The username and password will be removed from the back end without changing account numbers or passwords.
  request.put('/user/update', data.user).then(res => {
    if (res.code === '200') {
      ElMessage.success('Saved')
      // The database has been modified and the local cache is synchronized, otherwise the new page becomes old.
      localStorage.setItem('xm-user', JSON.stringify(data.user))
      // Trigger reread the user from the outer layer of localStorage and update the name of the top right corner immediately
      emit('updateUser')
    } else {
      ElMessage.error(res.msg)
    }
  })
}
</script>

<style scoped>
.profile-panel {
  width: min(100%, 560px);
  padding: clamp(16px, 3vw, 28px);
}

.profile-photo {
  display: flex;
  align-items: center;
  gap: 15px;
  padding-bottom: 18px;
  margin-bottom: 18px;
  border-bottom: 1px solid var(--border);
}
</style>
