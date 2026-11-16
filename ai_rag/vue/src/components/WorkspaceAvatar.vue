<template>
  <span class="workspace-avatar" :style="{ '--avatar-size': size + 'px' }">
    <img v-if="photo && photo !== failedPhoto" :src="photo" alt="" @error="failedPhoto = photo">
    <span v-else>{{ initials }}</span>
  </span>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  user: { type: Object, required: true },
  size: { type: Number, default: 34 },
})
const failedPhoto = ref('')
const photo = computed(() => {
  const url = props.user.avatar || ''
  const filename = url.split(/[?#]/)[0].split('/').pop()
  return filename === '1721114905635-shiba-inu.jpeg' ? '' : url
})
const initials = computed(() => (props.user.name || props.user.username || '')
  .trim().split(/\s+/).slice(0, 2).map(word => Array.from(word)[0] || '').join('').toLocaleUpperCase() || '•')
</script>

<style scoped>
.workspace-avatar {
  display: inline-grid;
  place-items: center;
  overflow: hidden;
  flex: none;
  width: var(--avatar-size);
  height: var(--avatar-size);
  border-radius: 50%;
  color: var(--accent-strong);
  background: #e7e8ff;
  font-size: calc(var(--avatar-size) * .36);
  font-weight: 700;
  line-height: 1;
}

.workspace-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
</style>
