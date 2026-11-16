<template>
  <div>
    <div class="card" style="margin-bottom: 5px">
      <!-- Three numbers for overall satisfaction, the point-to-deposition amount is the stock to be dealt with in chapter 27. -->
      <span style="margin-right: 20px">Like {{ data.summary.liked }}</span>
      <span style="margin-right: 20px">Dislike {{ data.summary.disliked }}</span>
      <span style="margin-right: 20px">Satisfaction {{ data.summary.satisfaction ?? '—' }}%</span>
      <el-tag v-if="data.summary.pending_convert" type="warning" size="small">
        {{ data.summary.pending_convert }} Dots to sedimentation as an assessment.
      </el-tag>
    </div>

    <div class="card" style="margin-bottom: 5px">
      <el-radio-group v-model="data.tab" @change="switchTab">
        <el-radio-button value="session">Conversation Log</el-radio-button>
        <el-radio-button value="feedback">User Feedback</el-radio-button>
      </el-radio-group>
    </div>

    <!-- Dialogue log: One session line with priority for more-stamped sessions -->
    <div class="card" style="margin-bottom: 5px" v-if="data.tab === 'session'">
      <div style="margin-bottom: 10px">
        <el-input v-model="data.keyword" style="width: 240px; margin-right: 10px" placeholder="Search by conversation title"></el-input>
        <el-button type="info" plain @click="load">Query</el-button>
      </div>
      <el-table stripe :data="data.tableData">
        <el-table-column prop="id" label="Conversation ID" width="90" />
        <el-table-column prop="app_name" label="Associated Application" width="180" />
        <el-table-column prop="title" label="Conversation Title" show-overflow-tooltip />
        <el-table-column prop="message_count" label="Message Count" width="90" />
        <el-table-column prop="source" label="Source" width="100" />
        <!-- I'll show you. I won't take part in the screening, I'll use green. -->
        <el-table-column prop="like_count" label="Like" width="80">
          <template #default="scope">
            <el-tag v-if="scope.row.like_count" type="success" size="small">{{ scope.row.like_count }}</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <!-- The number of hits is not a 0 sign red. -->
        <el-table-column prop="dislike_count" label="Dislike" width="80">
          <template #default="scope">
            <el-tag v-if="scope.row.dislike_count" type="danger" size="small">{{ scope.row.dislike_count }}</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="create_time" label="Time" width="180" />
        <el-table-column label="Actions" width="100" fixed="right">
          <template #default="scope">
            <el-button type="primary" size="small" @click="viewMessages(scope.row)">View</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- User feedback: one line of feedback with questions and answers at the time -->
    <div class="card" style="margin-bottom: 5px" v-if="data.tab === 'feedback'">
      <div style="margin-bottom: 10px">
        <el-select v-model="data.feedbackType" clearable style="width: 140px; margin-right: 10px" placeholder="Feedback Type">
          <el-option label="Like" value="Like"></el-option>
          <el-option label="Dislike" value="Dislike"></el-option>
        </el-select>
        <el-select v-model="data.converted" clearable style="width: 180px; margin-right: 10px" placeholder="Has Been Deposited">
          <el-option label="Deposited Test Cases" value="Yes"></el-option>
          <el-option label="Pending Deposit" value="No"></el-option>
        </el-select>
        <el-button type="info" plain @click="load">Query</el-button>
      </div>
      <el-table stripe :data="data.tableData">
        <el-table-column prop="feedback_type" label="Type" width="90">
          <template #default="scope">
            <el-tag :type="scope.row.feedback_type === 'Like' ? 'success' : 'danger'" size="small">{{ scope.row.feedback_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="question" label="Question" show-overflow-tooltip />
        <el-table-column prop="answer" label="Response" show-overflow-tooltip />
        <el-table-column prop="reason" label="Feedback Reason" width="180" show-overflow-tooltip />
        <!-- Chapter 27 turns the point to be deposited into an assessment. -->
        <el-table-column prop="converted" label="Accumulated" width="90">
          <template #default="scope">
            <el-tag :type="scope.row.converted === 'Yes' ? 'success' : 'info'" size="small">{{ scope.row.converted }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="create_time" label="Time" width="180" />
      </el-table>
    </div>

    <div class="card" v-if="data.total">
      <el-pagination
          v-model:current-page="data.pageNum"
          background
          layout="prev, pager, next"
          :page-size="data.pageSize"
          :total="data.total"
          @current-change="load"
      />
    </div>

    <!-- Details of sessions pop windows: full question and answer with reference source -->
    <el-dialog title="Conversation Details" v-model="data.detailVisible" width="65%" destroy-on-close>
      <div style="max-height: 500px; overflow: auto">
        <div v-for="message in data.messages" :key="message.id" style="margin-bottom: 14px">
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
              <!-- Question as it is, answer with Markdown rendering and consistent with the question-and-answer page -->
              <span v-if="message.role === 'user'" style="white-space: pre-wrap">{{ message.content }}</span>
              <MarkdownText v-else :content="message.content" />
            </div>
          </div>
          <!-- Look at this line of recall: what was actually in it for? -->
          <div v-if="message.rewritten_query" style="font-size: 12px; color: #999; margin-top: 4px">
            Actual Retrieval Question:{{ message.rewritten_query }}
          </div>
          <div v-if="message.references && message.references.length" style="margin-top: 6px">
            <el-collapse>
              <el-collapse-item :title="'Reference source (' + message.references.length + ' items)'">
                <div v-for="reference in message.references" :key="reference.chunk_id" style="margin-bottom: 8px; font-size: 12px; color: #666">
                  <span style="margin-right: 8px">#{{ reference.rank_no }}</span>
                  <span style="margin-right: 8px">Segment {{ reference.chunk_id }}</span>
                  <div>{{ reference.content }}</div>
                </div>
              </el-collapse-item>
            </el-collapse>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="data.detailVisible = false">Close</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { reactive } from 'vue'
import { ElMessage } from 'element-plus'
import request from '@/utils/request.js'
import MarkdownText from '@/components/MarkdownText.vue'

const data = reactive({
  // Two pagemarks with one form, and by tab, we'll find out which interface.
  tab: 'session',
  tableData: [],
  pageNum: 1,
  pageSize: 10,
  total: 0,
  keyword: '',
  feedbackType: '',
  converted: '',
  // Overview of top feedback
  summary: {},
  // Snip windows for session details
  detailVisible: false,
  messages: []
})

const loadSummary = () => {
  request.get('/feedback/summary').then(res => {
    if (res.code === '200') {
      data.summary = res.data || {}
    }
  })
}

const load = () => {
  // Sessions sign-off session list interface, keyword for session title entered in top search box
  if (data.tab === 'session') {
    request.get('/feedback/sessions', {
      params: { page_num: data.pageNum, page_size: data.pageSize, keyword: data.keyword }
    }).then(res => {
      if (res.code === '200') {
        // The total number of sessions and pages is written in the common tabledata and total, with pagebars rendered accordingly
        data.tableData = res.data?.list || []
        data.total = res.data?.total || 0
      } else {
        ElMessage.error(res.msg)
      }
    })
    // The request for a session page has been sent, and there is no further way down to the feedback page.
    return
  }
  // The feedback page signes the feedback Type interface, and it's a little bit of praise to step down.
  request.get('/feedback/selectPage', {
    params: {
      page_num: data.pageNum,
      page_size: data.pageSize,
      feedback_type: data.feedbackType,
      converted: data.converted
    }
  }).then(res => {
    if (res.code === '200') {
      // The same tableData is used for two pages, so the page must be empty when you cut it.
      data.tableData = res.data?.list || []
      data.total = res.data?.total || 0
    } else {
      ElMessage.error(res.msg)
    }
  })
}

const switchTab = () => {
  // Empty terms and page numbers when signing new pages, the filter conditions for two pages are not common
  data.pageNum = 1
  data.tableData = []
  data.total = 0
  load()
}

const viewMessages = (row) => {
  // Full message for this session, with reference to each answer
  request.get('/qaApp/messages/' + row.id).then(res => {
    if (res.code === '200') {
      data.messages = res.data || []
      data.detailVisible = true
    } else {
      ElMessage.error(res.msg)
    }
  })
}

loadSummary()
load()
</script>
