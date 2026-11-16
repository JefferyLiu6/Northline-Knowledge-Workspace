<template>
  <div>
    <div class="card" style="margin-bottom: 5px">
      <!-- A new session will take place. The conversation will be in the minutes. -->
      <el-select v-model="data.appId" style="width: 260px; margin-right: 10px" placeholder="Please select a Q&A application" @change="startSession">
        <el-option
            v-for="app in data.appOptions"
            :key="app.id"
            :label="app.name + (app.agent_enabled === 'Yes' ? '(Agentic)' : '')"
            :value="app.id"
        ></el-option>
      </el-select>
      <!-- Opening a new session is like clearing up the current conversation and starting again. -->
      <el-button type="warning" plain @click="startSession">Create new session</el-button>
      <span v-if="data.sessionNo" style="margin-left: 12px; color: #999; font-size: 12px">
        Current session:{{ data.sessionNo.slice(0, 8) }}
      </span>
    </div>

    <div class="card" style="margin-bottom: 5px">
      <!-- Dialogue area, fixed high-high and rolling with new messages added below -->
      <div ref="listRef" style="height: 460px; overflow: auto; padding: 10px">
        <div v-for="(message, index) in data.messages" :key="index" style="margin-bottom: 16px">
          <!-- User messages to the right, assistant messages to the left. -->
          <div :style="{ textAlign: message.role === 'user' ? 'right' : 'left' }">
            <div
                :style="{
                  display: 'inline-block',
                  maxWidth: '80%',
                  textAlign: 'left',
                  padding: '10px 14px',
                  borderRadius: '6px',
                  background: message.role === 'user' ? '#ecf5ff' : '#f7f7f7'
                }"
            >
              <!-- Question is a simple text that the user knocks on, showing as it is; answer is Markdown for model output and gives to component rendering -->
              <span v-if="message.role === 'user'" style="white-space: pre-wrap">{{ message.content }}</span>
              <template v-else>
                <!-- There's a few seconds between the search and the first word. Here's what steps are being taken.
                     When the text arrives, replace it with a real one. -->
                <div v-if="message.phase && !message.content" class="qa-phase">
                  <span class="qa-phase-dot"></span>{{ message.phase }}
                </div>
                <MarkdownText v-else :content="message.content" />
              </template>
              <span v-if="message.streaming && message.content" style="color: #999">▍</span>
            </div>
          </div>
          <!-- Retry trajectory: Every time you go back to re-entry, a single item shows why it's slow. -->
          <div v-if="message.retries && message.retries.length" class="qa-retry">
            <div v-for="(item, i) in message.retries" :key="i">↻ Retry {{ i + 1 }} · {{ item }}</div>
          </div>
          <!-- Agentic's running a few steps and searching several times. -->
          <div v-if="message.agent" style="margin-top: 6px; font-size: 12px; color: #999">
            {{ message.agent.finish_reason }} · Steps {{ message.agent.total_step }} ·
            Retrievals {{ message.agent.retrieve_count }} · Rewrites {{ message.agent.retry_count }}
            <el-button link type="primary" size="small" @click="viewRun(message.agent.run_id)">View timeline</el-button>
          </div>
          <!-- No buttons are displayed during the flow -->
          <div v-if="message.role === 'assistant' && message.messageId && !message.streaming" style="margin-top: 6px">
            <el-button
                link
                :type="message.feedback === 'Like' ? 'primary' : 'info'"
                size="small"
                @click="submitFeedback(message, 'Like')"
            >👍 Helpful</el-button>
            <el-button
                link
                :type="message.feedback === 'Dislike' ? 'danger' : 'info'"
                size="small"
                @click="submitFeedback(message, 'Dislike')"
            >👎 Not helpful</el-button>
          </div>
          <!-- The source of the quote was received before the text. It's folded here. -->
          <div v-if="message.references && message.references.length" style="margin-top: 6px">
            <el-collapse>
              <el-collapse-item :title="'Sources (' + message.references.length + ')'">
                <div v-for="reference in message.references" :key="reference.chunk_id" style="margin-bottom: 8px; font-size: 12px; color: #666">
                  <span style="margin-right: 8px">#{{ reference.rank_no }}</span>
                  <span style="margin-right: 8px">Chunk {{ reference.chunk_id }}</span>
                  <span style="margin-right: 8px">Score {{ reference.score }}</span>
                  <div>{{ reference.content }}</div>
                </div>
              </el-collapse-item>
            </el-collapse>
          </div>
        </div>
        <div v-if="!data.messages.length" style="color: #999; text-align: center; padding-top: 180px">
          Select an application to start asking questions
        </div>
      </div>
    </div>

    <div class="card">
      <el-input
          v-model="data.question"
          type="textarea"
          :rows="2"
          placeholder="Enter a question and press Enter to send"
          @keyup.enter.exact="ask"
      ></el-input>
      <div style="margin-top: 10px; text-align: right">
        <el-button type="primary" :loading="data.sending" @click="ask">Send</el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { nextTick, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import request from '@/utils/request.js'
import router from '@/router/index.js'
import { streamPost } from '@/utils/sse.js'
import MarkdownText from '@/components/MarkdownText.vue'

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

const data = reactive({
  // Apply drop-down options from /qaApp/ secretEnabled
  appOptions: [],
  appId: '',
  // Current conversation
  sessionId: 0,
  sessionNo: '',
  // Dialogue message list, each including role, content, references, agent
  messages: [],
  question: '',
  sending: false
})

const loadApps = () => {
  request.get('/qaApp/selectEnabled').then(res => {
    if (res.code === '200') {
      data.appOptions = res.data || []
      // AppId with address bar when jumping from the application management page, automatically select and speak
      const appId = router.currentRoute.value.query.appId
      if (appId) {
        data.appId = Number(appId)
        startSession()
      }
    }
  })
}

const startSession = () => {
  if (!data.appId) {
    return
  }
  // New sessions empty the current dialogue area, and previous conversations are in stock and can be found on session records.
  data.messages = []
  request.post('/qaApp/session', { app_id: data.appId, source: 'Admin portal' }).then(res => {
    if (res.code === '200') {
      data.sessionId = res.data.session_id
      data.sessionNo = res.data.session_no
    } else {
      // Apply disabled, untied knowledge banks and hanged libraries are all out. Backend returns to human voice tips
      ElMessage.error(res.msg)
    }
  })
}

const scrollToBottom = () => {
  // Get out of the bottom every time you add it, so we can keep the latest news visible.
  nextTick(() => {
    if (listRef.value) {
      listRef.value.scrollTop = listRef.value.scrollHeight
    }
  })
}

const ask = async () => {
  if (!data.sessionId) {
    ElMessage.warning('Please select a Q&A application first')
    return
  }
  const question = data.question.trim()
  if (!question) {
    return
  }
  data.sending = true
  // Put the user message in the list first, without waiting for interfaces to return
  data.messages.push({ role: 'user', content: question })
  // One more empty assistant message. The text is a little bit filled in by Delta incident.
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
        // The source of the reference arrived before the text, and it was rendered;
        // It says the search is over, and then modeling.
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
        // This is the only thing that happened in Agentic mode. It took a few steps with it.
        reply.agent = payload
      } else if (event === 'delta') {
        // Text increment. A paragraph is inserted; the first word does not need to be displayed with stage tips.
        // Text increment, one paragraph in a row.
        reply.content += payload.text
        reply.phase = ''
        scrollToBottom()
      } else if (event === 'done') {
        // I'm gonna get this answer. Id, give me a little bit of credit for the button.
        reply.messageId = payload.message_id
      } else if (event === 'error') {
        reply.content = payload.message
        reply.phase = ''
        ElMessage.error(payload.message)
      }
    })
  } finally {
    reply.streaming = false
    // When the whole stream is over and the text isn't there, phase will be cleared or it's going to turn.
    reply.phase = ''
    data.sending = false
    scrollToBottom()
  }
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

const viewRun = (runId) => {
  // Go to the running log page of chapter 23 and open this execution time line directly
  router.push('/manager/agentRun?runId=' + runId)
}

loadApps()
</script>

<style scoped>
/* Before the text arrives, wait hints: a little dot of breath + an ellipse number that will beat,
   Let the user know that the request is still running, not that the page's dead. */
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
  background-color: #2563eb;
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
</style>
