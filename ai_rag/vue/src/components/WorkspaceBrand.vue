<template>
  <span class="workspace-brand">
    <img :src="markUrl" width="34" height="34" alt="">
    <span>Knowledge Workspace</span>
  </span>
</template>

<script setup>
const markUrl = import.meta.env.BASE_URL + 'workspace-mark.webp'
</script>

<style scoped>
.workspace-brand {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  color: inherit;
  font-size: 15px;
  font-weight: 680;
  letter-spacing: -.035em;
  white-space: nowrap;
}

.workspace-brand img {
  display: block;
  flex: none;
  object-fit: contain;
}
</style>
