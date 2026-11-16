<template>
  <div class="front-profile">
    <h1>Profile</h1>
    <ProfileForm @update-user="emit('updateUser')" />
  </div>
</template>

<script setup>
import ProfileForm from '@/components/ProfileForm.vue'

const emit = defineEmits(['updateUser'])
</script>

<style scoped>
.front-profile {
  width: min(100% - 32px, 560px);
  margin: clamp(20px, 4vw, 44px) auto;
}

.front-profile h1 {
  margin: 0 0 16px;
  font-size: clamp(26px, 3vw, 34px);
  letter-spacing: -.045em;
}
</style>
