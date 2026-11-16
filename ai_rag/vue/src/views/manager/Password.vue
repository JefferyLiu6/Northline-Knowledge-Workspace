<template>
  <div class="card password-panel">
    <el-form ref="formRef" :rules="data.rules" :model="data.user" label-position="top" @submit.prevent="updatePassword">
      <!-- Enter the value into data.user.password, which is matched to the old password in the database on the backend -->
      <el-form-item label="Current password" prop="password">
        <el-input v-model="data.user.password" placeholder="Please enter original password" show-password></el-input>
      </el-form-item>
      <!-- Enter value into data.user. newpassword, check the password column that was written to the user table -->
      <el-form-item label="New password" prop="newPassword">
        <el-input v-model="data.user.newPassword" placeholder="Please enter a new password" show-password></el-input>
      </el-form-item>
      <!-- Only check consistency at front end and not send backend to participate in business judgement -->
      <el-form-item label="Confirm password" prop="confirmPassword">
        <el-input v-model="data.user.confirmPassword" placeholder="Please confirm new password" show-password></el-input>
      </el-form-item>
      <el-button type="primary" native-type="submit">Save password</el-button>
    </el-form>
  </div>
</template>

<script setup>
import {reactive, ref} from "vue";
import request from "@/utils/request.js";
import {ElMessage} from "element-plus";
import router from "@/router/index.js";

const formRef = ref()

// Confirm passwords to match new passwords with custom verification functions,
// Send Error to callback for no pass and not for reference
const validatePass = (rule, value, callback) => {
  if (!value) {
    callback(new Error('Please confirm password'))
    return
  }
  // Data.user.newPassword is the value of the new password box above, and two input inconsistencies are just a red hint below the frame
  if (value !== data.user.newPassword) {
    callback(new Error('Confirm password does not match new password!'))
    return
  }
  callback()
}

const data = reactive({
  // Take the current user from the login cache, followed by password, new Password, contactpassword
  // The values of three input boxes are hung up on this same object and submitted as a request.
  user: JSON.parse(localStorage.getItem('xm-user') || '{}'),
  // All three must be filled in, confirming password consistency by custom function
  rules: {
    password: [
      { required: true, message: 'Please enter original password', trigger: 'blur' },
    ],
    newPassword: [
      { required: true, message: 'Please enter a new password', trigger: 'blur' },
    ],
    confirmPassword: [
      { validator: validatePass, trigger: 'blur' }
    ]
  }
})

const updatePassword = () => {
  formRef.value.validate(valid => {
    // valid for true indicates that all three boxes are filled out and two new passwords are identical
    if (valid) {
      // Current login user parsing from token. The interface does not need to send the user id
      request.put('/updatePassword', data.user).then(res => {
        if (res.code === '200') {
          ElMessage.success('Saved')
          // The password changed. This token in your hand corresponds to the login status of the old code period.
          // Clear cache back to login and re-log with a new password
          logout()
        } else {
          // The original password error, the new password and the same password failed. Backend returns a human message in msg
          ElMessage.error(res.msg)
        }
      })
    }
  })
}

const logout = async () => {
  await request.post("/logout")
  // Clear local login caches and then not get token, go back to un-logged status
  localStorage.removeItem('xm-user')
  router.push('/login')
}
</script>

<style scoped>
.password-panel {
  width: min(100%, 560px);
  padding: clamp(16px, 3vw, 28px);
}
</style>