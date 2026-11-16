<template>
  <AccountLayout title="Create an account" description="Set up access to your knowledge workspace.">
    <el-form ref="formRef" :model="form" :rules="rules" label-position="top" hide-required-asterisk @submit.prevent="register">
      <el-form-item label="Username" prop="username">
        <el-input v-model="form.username" autocomplete="username" size="large" />
      </el-form-item>
      <el-form-item label="Password" prop="password">
        <el-input v-model="form.password" type="password" show-password autocomplete="new-password" size="large" />
      </el-form-item>
      <el-form-item label="Confirm password" prop="confirmPassword">
        <el-input v-model="form.confirmPassword" type="password" show-password autocomplete="new-password" size="large" />
      </el-form-item>
      <el-button class="account-submit" type="primary" size="large" native-type="submit" :loading="submitting">
        Create account
      </el-button>
      <p class="account-alternate"><RouterLink to="/login">Sign in</RouterLink></p>
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
const form = reactive({ username: '', password: '', confirmPassword: '' })
const submitting = ref(false)

const validateConfirmation = (_rule, value, callback) => {
  if (!value) return callback(new Error('Confirm your password'))
  if (value !== form.password) return callback(new Error('Passwords must match'))
  callback()
}

const rules = {
  username: [{ required: true, message: 'Enter your username', trigger: 'blur' }],
  password: [{ required: true, message: 'Enter a password', trigger: 'blur' }],
  confirmPassword: [{ validator: validateConfirmation, trigger: 'blur' }],
}

const register = async () => {
  if (submitting.value) return
  submitting.value = true
  try {
    await formRef.value.validate()
    const result = await request.post('/register', form)
    if (result.code !== '200') {
      ElMessage.error(result.msg)
      return
    }
    ElMessage.success('Account created')
    router.push('/login')
  } catch {
    // Field validation and the request interceptor display their own messages.
  } finally {
    submitting.value = false
  }
}
</script>
