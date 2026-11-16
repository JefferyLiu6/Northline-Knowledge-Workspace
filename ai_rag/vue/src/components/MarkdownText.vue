<template>
  <!-- The answer returned from the model is Markdown text, which is rendered as HTML again;
       html recalculates when content changes so you can also read and render during flow output -->
  <div class="md-body" v-html="html"></div>
</template>

<script setup>
import { computed } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

const props = defineProps({
  // Original Markdown to render, answer from question and answer interface
  content: {
    type: String,
    default: ''
  }
})

// gfm Opens tables, delete lines and syntax extensions;
// Breaks make the single line break <br>, and often the answer to model output is in one line break.
marked.setOptions({ gfm: true, breaks: true })

const html = computed(() => {
  if (!props.content) {
    return ''
  }
  // The answer is produced by a large model, which is uncontrollable and converted to HTML.
  // Remove dangerous elements like script, on events and avoid v-html bringing XSS
  return DOMPurify.sanitize(marked.parse(props.content))
})
</script>

<style scoped>
.md-body {
  font-size: 14px;
  line-height: 1.75;
  word-break: break-word;
}

/* Content is inserted by v-html, without data-v properties for scoped, style to write in:deep() */
.md-body :deep(p) {
  margin: 0 0 8px;
}

.md-body :deep(p:last-child) {
  margin-bottom: 0;
}

.md-body :deep(h1),
.md-body :deep(h2),
.md-body :deep(h3),
.md-body :deep(h4) {
  margin: 12px 0 8px;
  font-size: 15px;
  font-weight: 600;
}

.md-body :deep(h1:first-child),
.md-body :deep(h2:first-child),
.md-body :deep(h3:first-child) {
  margin-top: 0;
}

.md-body :deep(ul),
.md-body :deep(ol) {
  margin: 0 0 8px;
  padding-left: 22px;
}

.md-body :deep(li) {
  margin-bottom: 4px;
}

.md-body :deep(li:last-child) {
  margin-bottom: 0;
}

/* Inner line codes and code blocks, the answer will be used when there is an interface name or error number. */
.md-body :deep(code) {
  padding: 1px 5px;
  border-radius: 4px;
  font-size: 13px;
  font-family: Consolas, Monaco, monospace;
  background-color: rgba(125, 135, 155, .14);
}

.md-body :deep(pre) {
  margin: 0 0 8px;
  padding: 10px 12px;
  border-radius: 6px;
  overflow-x: auto;
  background-color: rgba(125, 135, 155, .14);
}

.md-body :deep(pre code) {
  padding: 0;
  background: none;
}

/* The answer is often to add a frame to the table that refers to the rules of the system. */
.md-body :deep(table) {
  margin: 0 0 8px;
  border-collapse: collapse;
  font-size: 13px;
}

.md-body :deep(th),
.md-body :deep(td) {
  padding: 5px 10px;
  border: 1px solid #dfe3ea;
}

.md-body :deep(th) {
  background-color: rgba(125, 135, 155, .1);
  font-weight: 600;
}

.md-body :deep(blockquote) {
  margin: 0 0 8px;
  padding: 2px 0 2px 10px;
  border-left: 3px solid #c7cedb;
  color: #6b7280;
}

.md-body :deep(a) {
  color: #2563eb;
}

.md-body :deep(hr) {
  margin: 10px 0;
  border: none;
  border-top: 1px solid #e6e9f0;
}

.md-body :deep(img) {
  max-width: 100%;
}
</style>
