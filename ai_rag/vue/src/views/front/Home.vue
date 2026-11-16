<template>
  <div class="qa-workbench">
    <!-- Left: Select application + your own history dialogue -->
    <div class="qa-side">
      <div class="side-block">
        <div class="side-label">Application</div>
        <!-- Only the application enabled by a column manager is not visible to the disabled user; after selection, change events start directly with a new session -->
        <el-select v-model="data.appId" aria-label="Q&A application" placeholder="Choose an application"
                   :disabled="data.sending || data.starting || !data.appOptions.length" @change="startSession">
          <template #prefix><el-icon><Files /></el-icon></template>
          <el-option
              v-for="app in data.appOptions"
              :key="app.id"
              :label="app.name"
              :value="app.id"
          ></el-option>
        </el-select>
        <el-button class="new-conversation" type="primary" :icon="Plus" :disabled="!data.appId || data.sending || data.starting"
                   @click="startSession">New conversation</el-button>
      </div>

      <div class="side-block side-history">
        <div class="side-label">My conversations</div>
        <div class="history-list">
          <!-- Dot any history to load this session, the one currently opened is-current -->
          <div
              v-for="session in data.sessions"
              :key="session.id"
              :class="['history-item', session.id === data.sessionId ? 'is-current' : '']"
          >
            <button type="button" class="history-open" :disabled="data.sending || data.starting"
                    @click="openSession(session)">
              <el-icon><ChatDotRound /></el-icon>
              <span class="history-copy">
                <span class="history-title">{{ session.title || 'New conversation' }}</span>
                <span class="history-time">{{ formatSessionDate(session.create_time) }}</span>
              </span>
            </button>
            <button type="button" class="history-del" aria-label="Delete conversation"
                    :disabled="data.sending || data.starting" @click="removeSession(session)">
              <el-icon><Delete /></el-icon>
            </button>
          </div>
          <div v-if="!data.sessions.length" class="history-empty">No conversation history</div>
        </div>
      </div>
    </div>

    <!-- Right: dialogue area -->
    <div class="qa-main">
      <div ref="listRef" class="chat-list">
        <div v-for="(message, index) in data.messages" :key="index" class="chat-row">
          <div :class="['bubble-line', message.role === 'user' ? 'is-user' : 'is-assistant']">
            <div class="bubble">
              <!-- Question shows as it is, and the answer is Markdown, give it to component rendering. -->
              <span v-if="message.role === 'user'" class="plain-text">{{ message.content }}</span>
              <template v-else>
                <!-- There's a few seconds between the search and the first word. Here's what steps are being taken.
                     When the text arrives, replace it with a real one. -->
                <div v-if="message.phase && !message.content" class="qa-phase">
                  <span class="qa-phase-dot"></span>{{ message.phase }}
                </div>
                <MarkdownText v-else :content="message.content" />
              </template>
              <span v-if="message.streaming && message.content" class="caret">▍</span>
            </div>
          </div>

          <!-- Retry trajectory: Every time you go back to re-entry, a single item shows why it's slow. -->
          <div v-if="message.retries && message.retries.length" class="qa-retry">
            <div v-for="(item, i) in message.retries" :key="i">↻ Retry {{ i + 1 }} · {{ item }}</div>
          </div>
          <!-- Agentic's the only one who can do this, which means he's been running a few steps. -->
          <div v-if="message.agent" class="agent-line">
            {{ message.agent.finish_reason }} · Steps {{ message.agent.total_step }} ·
            Retrievals {{ message.agent.retrieve_count }} · Rewrites {{ message.agent.retry_count }}
          </div>

          <!-- The source arrived before the text, folded to check where it came from and then started. -->
          <div v-if="message.references && message.references.length" class="reference-box">
            <el-collapse>
              <el-collapse-item :title="'Sources (' + message.references.length + ')'">
                <div v-for="reference in message.references" :key="reference.chunk_id" class="reference-item">
                  <div class="reference-meta">
                    <span>#{{ reference.rank_no }}</span>
                    <span>Chunk {{ reference.chunk_id }}</span>
                    <span v-if="reference.score !== null">Relevance {{ reference.score }}</span>
                  </div>
                  <div class="reference-text">{{ reference.content }}</div>
                </div>
              </el-collapse-item>
            </el-collapse>
          </div>

          <!-- The answer is generated before the score is split. No buttons are displayed during the flow -->
          <div v-if="message.role === 'assistant' && message.messageId && !message.streaming" class="feedback-line">
            <el-button
                link
                :type="message.feedback === 'Like' ? 'primary' : 'info'"
                size="small"
                @click="submitFeedback(message, 'Like')"
             :icon="CircleCheck">Helpful</el-button>
            <el-button
                link
                :type="message.feedback === 'Dislike' ? 'danger' : 'info'"
                size="small"
                @click="submitFeedback(message, 'Dislike')"
             :icon="CircleClose">Not helpful</el-button>
          </div>
        </div>

        <div v-if="!data.messages.length" class="chat-empty">
          <el-icon class="empty-icon"><ChatLineRound /></el-icon>
          <h1 class="empty-title">Ask your knowledge base</h1>
          <RouterLink v-if="!data.user.id" class="empty-sign-in" to="/login">Sign in to start a conversation</RouterLink>
          <p v-else class="empty-tip">{{ data.appId ? 'Ask a question to get an answer with sources.' : 'Choose a Q&A application to get started.' }}</p>
        </div>
      </div>

      <form class="chat-input" @submit.prevent="ask">
        <el-icon class="composer-icon"><ChatDotRound /></el-icon>
        <el-input
            v-model="data.question"
            type="textarea"
            :autosize="{ minRows: 1, maxRows: 5 }"
            resize="none"
            aria-label="Your question"
            placeholder="Type your question"
            :disabled="!data.appId || data.starting"
            @keydown.enter.exact.prevent="ask"
        ></el-input>
        <div class="input-bar">
          <span class="input-hint">Shift + Enter for a new line</span>
          <el-button native-type="submit" type="primary" :icon="Promotion" :loading="data.sending"
                     :disabled="!data.appId || !data.question.trim() || data.starting">Send</el-button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { nextTick, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/utils/request.js'
import { streamPost } from '@/utils/sse.js'
import MarkdownText from '@/components/MarkdownText.vue'
import { ChatDotRound, ChatLineRound, CircleCheck, CircleClose, Delete, Files, Plus, Promotion } from '@element-plus/icons-vue'

// The Agentic link sends a press event every node after running.
// Now, here's the word "run-down node" for "what to do next," as a reminder of waiting.
const AGENT_PHASE = {
  rewrite: 'Searching the knowledge base',
  retrieve: 'Judging the relevance of the retrieved materials',
  grade: 'Generating the answer',
  generate: 'Verifying if the answer has supporting materials',
  check: 'Organizing the output',
  fallback: 'Organizing the output'
}

/** Map agent progress events to the phase and retry messages shown in the chat. */
const readProgress = (payload) => {
  const detail = payload.detail || {}
  if (payload.node === 'grade' && detail.relevant === false) {
    return { phase: 'The retrieved materials are not relevant, rewriting the question for re-search', retry: 'The retrieved materials are not relevant, rewriting the question for re-search' }
  }
  if (payload.node === 'check' && detail.grounded === false) {
    return { phase: 'The answer lacks supporting materials, regenerating', retry: 'The answer lacks supporting materials, regenerating' }
  }
  // Rewrite node when retrying step_name itself is "N-rew query" and it's more accurate.
  if (payload.node === 'rewrite' && payload.name?.startsWith('Rewrite query')) {
    return { phase: 'Query rewritten. Searching again…', retry: '' }
  }
  return { phase: AGENT_PHASE[payload.node] || payload.name, retry: '' }
}

const listRef = ref()
const sessionDate = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' })
const formatSessionDate = (value) => {
  if (!value) return ''
  const date = new Date(value.replace(' ', 'T'))
  return Number.isNaN(date.valueOf()) ? value : sessionDate.format(date)
}

const data = reactive({
  user: JSON.parse(localStorage.getItem('xm-user') || '{}'),
  // A question and answer application enabled from /qaApp/selectEnabled
  appOptions: [],
  appId: '',
  // Historic Session from /qaApp/mysessions
  sessions: [],
  // Current conversation
  sessionId: 0,
  // The current session is held under which application.
  // You compare it to the appId, and you don't ask new questions into an application session.
  sessionAppId: 0,
  // Dialogue message, each including role, content, references, agent
  messages: [],
  question: '',
  starting: false,
  sending: false
})

const loadApps = () => {
  request.get('/qaApp/selectEnabled').then(res => {
    if (res.code === '200') {
      data.appOptions = res.data || []
      // Only one application is selected directly, saves a click.
      if (data.appOptions.length === 1) {
        data.appId = data.appOptions[0].id
      }
    }
  })
}

const loadSessions = () => {
  // Take your own session. Backends take from token user_id, the front ends don't pass it on.
  request.get('/qaApp/mySessions', { params: { page_num: 1, page_size: 20 } }).then(res => {
    if (res.code === '200') {
      data.sessions = res.data.list || []
    }
  })
}

const startSession = () => {
  if (!data.appId) {
    ElMessage.warning('Please select a Q&A application first')
    return
  }
  // The current session had just been built, had not been asked a single word and had never been replaced by an article.
  // If you don't stop it, a couple of new conversations will pile up an empty set of "new talks" on the left.
  if (data.sessionId && !data.messages.length && data.sessionAppId === data.appId) {
    ElMessage.info('The current session is already a new conversation, just ask directly')
    return
  }
  // New sessions are empty dialogue areas. Previous conversations have been stored and found on the left list.
  data.messages = []
  data.sessionId = 0
  data.starting = true
  request.post('/qaApp/session', { app_id: data.appId, source: 'User portal' }).then(res => {
    if (res.code === '200') {
      data.sessionId = res.data.session_id
      data.sessionAppId = data.appId
      // The new conversation will appear on top of the list and be highlighted as a current session.
      // Users can see that it's built. It doesn't go around without feedback.
      loadSessions()
    } else {
      // Apply disabled, untied knowledge banks and hanged libraries are all out. Backend returns to human voice tips
      ElMessage.error(res.msg)
    }
  }).finally(() => { data.starting = false })
}

const removeSession = (session) => {
  ElMessageBox.confirm(
    `Delete “${session.title || 'New conversation'}” and all its messages and feedback?`,
    'Confirm deletion',
    { type: 'warning' }
  ).then(() => {
    request.delete('/qaApp/session/' + session.id).then(res => {
      if (res.code !== '200') {
        ElMessage.error(res.msg)
        return
      }
      ElMessage.success('Deleted')
      // This is the one that's now open. The dialogue area needs to be empty together.
      // Otherwise, there's a conversation on the page that doesn't exist.
      if (session.id === data.sessionId) {
        data.messages = []
        data.sessionId = 0
        data.sessionAppId = 0
      }
      loadSessions()
    })
  }).catch(() => {})
}

const openSession = (session) => {
  // Let's have a little historical conversation and bring back all the information about this session.
  data.sessionId = session.id
  data.appId = session.app_id
  data.sessionAppId = session.app_id
  request.get('/qaApp/messages/' + session.id).then(res => {
    if (res.code !== '200') {
      ElMessage.error(res.msg)
      return
    }
    const list = res.data || []
    data.messages = list.map(item => ({
      role: item.role,
      content: item.content,
      references: item.references || [],
      agent: null,
      streaming: false,
      messageId: item.id,
      feedback: ''
    }))
    scrollToBottom()
    loadFeedback(list)
  })
}

const loadFeedback = (list) => {
  // You're going to have to put your past on the buttons, or you're going back to history and think you haven't.
  const ids = list.filter(item => item.role === 'assistant').map(item => item.id)
  if (!ids.length) {
    return
  }
  request.post('/feedback/byMessages', { message_ids: ids }).then(res => {
    if (res.code === '200') {
      const grouped = res.data || {}
      data.messages.forEach(message => {
        const stats = grouped[message.messageId]
        if (stats) {
          message.feedback = stats.mine || ''
        }
      })
    }
  })
}

const scrollToBottom = () => {
  // Every time you add it up, you get to the bottom of it and keep your latest news visible.
  nextTick(() => {
    if (listRef.value) {
      listRef.value.scrollTop = listRef.value.scrollHeight
    }
  })
}

const ask = async () => {
  if (data.sending || data.starting) {
    return
  }
  const question = data.question.trim()
  if (!question) {
    return
  }
  if (!data.sessionId) {
    // If you don't order a "new conversation" you ask.
    if (!data.appId) {
      ElMessage.warning('Please select a Q&A application first')
      return
    }
    data.starting = true
    try {
      await openSessionSilently()
    } finally {
      data.starting = false
    }
    if (!data.sessionId) {
      return
    }
  }
  data.sending = true
  // Put the questions in the list first, and don't wait for the interface to return.
  data.messages.push({ role: 'user', content: question })
  // One more empty answer, the text is a little bit filled in by Delta events.
  const reply = reactive({
    role: 'assistant',
    content: '',
    references: [],
    agent: null,
    streaming: true,
    // When you get the first Delta, you empty it.
    phase: 'Searching the knowledge base',
    // A new one is added to each retweeting of the Agentic links and remains after answers.
    retries: [],
    // Doe, doe, get back from the incident.
    messageId: 0,
    feedback: ''
  })
  data.messages.push(reply)
  data.question = ''
  scrollToBottom()

  try {
    await streamPost('/qaApp/ask', { session_id: data.sessionId, question }, (event, payload) => {
      if (event === 'reference') {
        // The reference source indicates that the search is over. Next, model production.
        // The source arrived before the text.
        reply.references = payload.references || []
        reply.phase = 'Documents have been retrieved, generating answer'
      } else if (event === 'progress') {
        // Agentic, it's a special event. The straight link won't be received.
        const step = readProgress(payload)
        reply.phase = step.phase
        // The retesting tracks remain below the bubble, and they don't get out when you answer.
        // It explains why we're going around this time. Where are the slows?
        if (step.retry) {
          reply.retries.push(step.retry)
        }
      } else if (event === 'agent') {
        reply.agent = payload
      } else if (event === 'delta') {
        // When the first word arrives, you don't have to show stage tips.
        // Text increment, one paragraph in a row.
        reply.content += payload.text
        reply.phase = ''
        scrollToBottom()
      } else if (event === 'done') {
        reply.messageId = payload.message_id
      } else if (event === 'error') {
        reply.content = payload.message
        reply.phase = ''
        ElMessage.error(payload.message)
      }
    })
  } finally {
    reply.streaming = false
    // When the whole stream ends before it gets to the text, phase will be cleared.
    reply.phase = ''
    data.sending = false
    scrollToBottom()
    // The first round of questions will write the title of the session into this phrase, and then refresh the left list to see it.
    loadSessions()
  }
}

const openSessionSilently = () => {
  return request.post('/qaApp/session', { app_id: data.appId, source: 'User portal' }).then(res => {
    if (res.code === '200') {
      data.sessionId = res.data.session_id
      data.sessionAppId = data.appId
    } else {
      ElMessage.error(res.msg)
    }
  })
}

const submitFeedback = (message, type) => {
  // The same answer will be repeated to cover the last one, with only final results retained at the back end
  request.post('/feedback/submit', {
    message_id: message.messageId,
    feedback_type: type
  }).then(res => {
    if (res.code === '200') {
      message.feedback = type
      ElMessage.success(type === 'Like' ? 'Thank you for the feedback' : 'Recorded, this question will be added to the optimization list')
    } else {
      ElMessage.error(res.msg)
    }
  })
}

if (!data.user.id) {
  ElMessage.warning('Please log in before using the Q&A')
} else {
  loadApps()
  loadSessions()
}
</script>

<style scoped>
.qa-workbench {
  display: grid;
  grid-template-columns: 265px minmax(0, 1fr);
  height: calc(100dvh - var(--workspace-header, 65px));
  min-height: 510px;
  background: var(--canvas);
}

.qa-side {
  display: flex;
  flex-direction: column;
  gap: 25px;
  min-height: 0;
  padding: 20px 17px;
  border-right: 1px solid var(--border);
  background: var(--surface);
}

.side-block :deep(.el-select) {
  width: 100%;
}

.side-block :deep(.el-select__wrapper) {
  min-height: 40px;
}

.side-label {
  margin-bottom: 8px;
  color: var(--ink-muted);
  font-size: 13px;
  font-weight: 650;
}

.new-conversation {
  width: 100%;
  min-height: 40px;
  margin-top: 14px;
}

.side-history {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-height: 0;
}

.history-list {
  flex: 1;
  min-height: 0;
  overflow: auto;
  margin: 0 -5px;
}

.history-item {
  display: flex;
  align-items: center;
  margin: 2px 4px;
  border-radius: 8px;
}

.history-open,
.history-del {
  border: 0;
  background: transparent;
  cursor: pointer;
}

.history-open {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  flex: 1;
  min-width: 0;
  padding: 10px 0 10px 7px;
  text-align: left;
  color: var(--ink-muted);
}

.history-open .el-icon {
  flex: none;
  margin-top: 2px;
  font-size: 16px;
}

.history-copy {
  min-width: 0;
}

.history-del {
  display: grid;
  place-items: center;
  flex: none;
  align-self: stretch;
  width: 29px;
  color: var(--ink-muted);
}

.history-del:hover {
  color: var(--el-color-danger);
}

.history-item:hover {
  background: #f4f6fb;
}

.history-item.is-current {
  background: var(--accent-soft);
}

.history-title {
  display: block;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  font-weight: 520;
  color: var(--ink);
}

.history-time {
  display: block;
  margin-top: 3px;
  color: var(--ink-muted);
  font-size: 11px;
}

.history-empty {
  padding: 12px 8px;
  font-size: 13px;
  color: var(--ink-muted);
}

.qa-main {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
}

.chat-list {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 22px clamp(24px, 4vw, 56px);
  scrollbar-gutter: stable;
}

.chat-row {
  margin-bottom: 18px;
}

.bubble-line {
  display: flex;
}

.bubble-line.is-user {
  justify-content: flex-end;
}

.bubble {
  max-width: 78%;
  padding: 11px 15px;
  border-radius: 10px;
  font-size: 14px;
  line-height: 1.75;
  word-break: break-word;
}

/* Question by user to stay on markdown rendering, line change as is */
.plain-text {
  white-space: pre-wrap;
}

/* Waiting hint before the text arrives: a little dot of breath + an ellipsis number that will beat */
.qa-phase {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #9096a3;
}

.qa-phase::after {
  content: '';
  animation: qa-dots 1.2s steps(1, end) infinite;
}

.qa-retry {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.9;
  color: #d97706;
}

.qa-phase-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--accent-strong);
  animation: qa-pulse 1s ease-in-out infinite;
}

@keyframes qa-pulse {
  0%, 100% { opacity: .25; transform: scale(.8); }
  50% { opacity: 1; transform: scale(1.15); }
}

@keyframes qa-dots {
  0% { content: ''; }
  25% { content: '.'; }
  50% { content: '..'; }
  75% { content: '...'; }
}

.is-user .bubble {
  color: #fff;
  background: var(--accent-strong);
  border-bottom-right-radius: 3px;
}

.is-assistant .bubble {
  color: #1f2937;
  background: var(--surface);
  border: 1px solid var(--border);
  border-bottom-left-radius: 3px;
}

.caret {
  color: #9096a3;
}

.agent-line {
  margin-top: 6px;
  font-size: 12px;
  color: #9096a3;
}

.reference-box {
  margin-top: 6px;
  max-width: 78%;
}

.reference-item {
  margin-bottom: 10px;
}

.reference-meta {
  display: flex;
  gap: 10px;
  font-size: 12px;
  color: #9096a3;
}

.reference-text {
  margin-top: 3px;
  font-size: 12px;
  line-height: 1.7;
  color: var(--ink-muted);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.feedback-line {
  margin-top: 4px;
}

.chat-empty {
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding: 12px;
  text-align: center;
}

.empty-icon {
  width: clamp(58px, 8vw, 112px);
  height: clamp(58px, 8vw, 112px);
  border-radius: 23%;
  background: #e3e5ff;
  color: var(--accent);
  font-size: clamp(29px, 4vw, 58px);
}

.empty-title {
  margin: 23px 0 0;
  font-size: clamp(24px, 3vw, 44px);
  line-height: 1.15;
  font-weight: 720;
  color: var(--ink);
  letter-spacing: -.045em;
}

.empty-tip,
.empty-sign-in {
  margin-top: 11px;
  margin-bottom: 0;
  color: var(--ink-muted);
  font-size: clamp(14px, 1.5vw, 21px);
}

.empty-sign-in {
  color: var(--accent-strong);
}

.chat-input {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  min-width: 0;
  margin: 0 clamp(12px, 2vw, 28px) clamp(12px, 2vw, 28px);
  padding: 9px 10px 9px 14px;
  border: 1px solid var(--border-strong);
  border-radius: 12px;
  background: var(--surface);
}

.chat-input:focus-within {
  border-color: var(--accent);
}

.composer-icon {
  flex: none;
  align-self: flex-end;
  margin-bottom: 9px;
  color: var(--ink-muted);
  font-size: 20px;
}

.input-bar {
  display: flex;
  flex: none;
  align-items: center;
  gap: 12px;
}

.input-hint {
  font-size: 12px;
  color: var(--ink-muted);
}

.chat-input :deep(.el-textarea__inner) {
  min-height: 35px !important;
  padding: 8px 4px;
  background: transparent;
  box-shadow: none;
}

.chat-input :deep(.el-textarea__inner:focus) {
  box-shadow: none;
  outline: 0;
}

@media (max-width: 720px) {
  .qa-workbench {
    grid-template-columns: minmax(0, 1fr);
    grid-template-rows: auto minmax(300px, 1fr);
    min-height: max(550px, calc(100dvh - var(--workspace-header, 65px)));
  }

  .qa-side {
    gap: 10px;
    padding: 12px;
    border-right: 0;
    border-bottom: 1px solid var(--border);
  }

  .new-conversation {
    width: auto;
    min-height: 34px;
    margin-top: 8px;
    padding-inline: 9px;
    border-color: #c9ccf6;
    background: var(--surface);
    color: var(--accent-strong);
  }

  .new-conversation:not(.is-disabled):hover {
    background: var(--accent-soft);
  }

  .new-conversation.is-disabled {
    color: var(--ink-muted);
    opacity: .72;
  }

  .side-history .side-label {
    margin-bottom: 3px;
  }

  .side-history .history-list {
    max-height: 51px;
  }

  .history-empty {
    padding: 4px 6px;
  }

  .chat-list {
    padding: 13px;
    scrollbar-gutter: auto;
  }

  .bubble,
  .reference-box {
    max-width: 100%;
  }

  .input-hint {
    display: none;
  }
}

</style>
