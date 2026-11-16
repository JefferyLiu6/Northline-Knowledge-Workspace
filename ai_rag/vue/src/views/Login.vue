<template>
  <AccountLayout title="Sign in" description="Access your knowledge workspace.">
    <el-form ref="formRef" :model="form" :rules="rules" label-position="top" hide-required-asterisk @submit.prevent="login">
      <el-form-item label="Username" prop="username">
        <el-input v-model="form.username" autocomplete="username" size="large" />
      </el-form-item>
      <el-form-item label="Password" prop="password">
        <el-input v-model="form.password" type="password" show-password autocomplete="current-password" size="large" />
      </el-form-item>
      <el-button class="account-submit" size="large" type="primary" native-type="submit" :loading="submitting">
        Sign in
      </el-button>
      <p class="account-alternate"><RouterLink to="/register">Create an account</RouterLink></p>
    </el-form>
  </AccountLayout>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import AccountLayout from '@/components/AccountLayout.vue'
import request from '@/utils/request.js'

const router = useRouter()
const formRef = ref()
const form = reactive({ username: '', password: '' })
const submitting = ref(false)
const rules = {
  username: [{ required: true, message: 'Enter your username', trigger: 'blur' }],
  password: [{ required: true, message: 'Enter your password', trigger: 'blur' }],
}

const login = async () => {
  if (submitting.value) return
  submitting.value = true
  try {
    await formRef.value.validate()
    const result = await request.post('/login', form)
    if (result.code !== '200') {
      ElMessage.error(result.msg)
      return
    }
    localStorage.setItem('xm-user', JSON.stringify(result.data))
    router.push(result.data.role === 'ADMIN' ? '/manager/home' : '/front/home')
  } catch {
    // Field validation and the request interceptor display their own messages.
  } finally {
    submitting.value = false
  }
}
</script>
