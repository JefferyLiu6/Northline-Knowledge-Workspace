<template>
  <ProfileForm @update-user="emit('updateUser')" />
</template>

<script setup>
import ProfileForm from '@/components/ProfileForm.vue'
const emit = defineEmits(['updateUser'])
</script>
