<template>
  <div>
    <div class="card" style="margin-bottom: 5px">
      <el-form label-width="90px" style="padding: 10px 20px 0">
        <!-- Agent only runs in one knowledge base at a time, and the access to the search tool is a kb_id -->
        <el-form-item label="Knowledge base">
          <el-select v-model="data.kbId" style="width: 100%" placeholder="Select a knowledge base">
            <el-option
                v-for="kb in data.kbOptions"
                :key="kb.id"
                :label="kb.name + '(Fragment ' + kb.chunk_count + ' items)'"
                :value="kb.id"
            ></el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="Question">
          <el-input v-model="data.query" type="textarea" :rows="2" placeholder="Input a question to see how the Agent finds the answer step by step"></el-input>
        </el-form-item>
        <el-form-item>
          <!-- Agent's going to run several rounds of model calls, slow for more than a dozen seconds and do not repeat the buttons during the spin. -->
          <el-button type="primary" :loading="data.running" @click="run">Start execution</el-button>
          <span style="margin-left: 16px; color: #999; font-size: 12px">
            Rewriting, retrieving, judging relevance, generating, validating, running several rounds based on the model's judgment
          </span>
        </el-form-item>
      </el-form>
    </div>

    <!-- The results show that the page was empty when it came in. -->
    <div class="card" style="margin-bottom: 5px" v-if="data.outcome.run_no">
      <div style="padding-bottom: 8px">
        <!-- The normal answer is green, and he's walking in orange. -->
        <el-tag :type="data.outcome.finish_reason === 'Answered' ? 'success' : 'warning'" style="margin-right: 12px">
          {{ data.outcome.finish_reason }}
        </el-tag>
        <span style="margin-right: 16px">Total {{ data.outcome.total_step }} Step</span>
        <span style="margin-right: 16px">Retrieval {{ data.outcome.retrieve_count }} the</span>
        <span style="margin-right: 16px">Rewrite and retry {{ data.outcome.retry_count }} the</span>
        <span style="margin-right: 16px">Elapsed time {{ data.outcome.cost_millis }} ms</span>
        <!-- Take running IDs to the time line page and see every step of detail. -->
        <el-button type="primary" size="small" @click="viewTimeline">View execution time line</el-button>
      </div>
      <!-- Agent the final answer is also Markdown text -->
      <div style="background: #f7f7f7; padding: 12px">
        <MarkdownText :content="data.outcome.answer" />
      </div>
    </div>

    <div class="card" v-if="data.outcome.references && data.outcome.references.length">
      <div style="font-weight: bold; padding-bottom: 8px">Reference source ({{ data.outcome.references.length }} items)</div>
      <!-- All of this stuff is based on chunk_id and back to the database, not by the model. -->
      <el-table stripe :data="data.outcome.references" size="small">
        <el-table-column prop="rank_no" label="Serial number" width="70" />
        <el-table-column prop="chunk_id" label="Fragment ID" width="90" />
        <el-table-column prop="page_no" label="Page number" width="80">
          <template #default="scope">{{ scope.row.page_no || '-' }}</template>
        </el-table-column>
        <el-table-column prop="score" label="Score" width="100" />
        <el-table-column prop="content" label="Fragment content" show-overflow-tooltip />
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { reactive } from 'vue'
import { ElMessage } from 'element-plus'
import request from '@/utils/request.js'
import router from '@/router/index.js'
import MarkdownText from '@/components/MarkdownText.vue'

const data = reactive({
  // Drop-down options for the knowledge base from /retrieval/ knowledgeBases
  kbOptions: [],
  // Selected knowledge base id
  kbId: '',
  // Question
  query: '',
  // Rounding status for executing buttons
  running: false,
  // Results of implementation, including answer, references, finish_reason, various counts
  outcome: {}
})

const loadOptions = () => {
  request.get('/retrieval/knowledgeBases').then(res => {
    if (res.code === '200') {
      data.kbOptions = res.data || []
    }
  })
}

const run = () => {
  if (!data.kbId) {
    ElMessage.warning('Select a knowledge base')
    return
  }
  if (!data.query.trim()) {
    ElMessage.warning('Please enter a question')
    return
  }
  data.running = true
  request.post('/agent/run', {
    kb_ids: [data.kbId],
    query: data.query
  }).then(res => {
    if (res.code === '200') {
      // There's answers, references, steps and searches.
      data.outcome = res.data
    } else {
      // No search, no model, no tool used and backends returned to the people.
      ElMessage.error(res.msg)
    }
  }).finally(() => {
    data.running = false
  })
}

const viewTimeline = () => {
  // Jump with running ID to the time line page, see every step of entry and return
  router.push('/manager/agentRun?runId=' + data.outcome.run_id)
}

// Draw the knowledge base down when a page is loaded
loadOptions()
</script>
