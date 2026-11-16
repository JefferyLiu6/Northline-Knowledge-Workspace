<template>
  <div>
    <div class="card" style="margin-bottom: 5px">
      <!-- It's just a failed run, the most common thing to check. -->
      <el-select v-model="data.runStatus" clearable style="width: 160px; margin-right: 10px" placeholder="Runtime status">
        <el-option label="Completed" value="Completed"></el-option>
        <el-option label="Run failed" value="Run failed"></el-option>
        <el-option label="Running" value="Running"></el-option>
      </el-select>
      <el-button type="info" plain @click="load">Query</el-button>
      <el-button type="warning" plain style="margin: 0 10px" @click="reset">Reset</el-button>
    </div>

    <div class="card" style="margin-bottom: 5px">
      <!-- Data.tableData from /agent/ rans returned list -->
      <el-table stripe :data="data.tableData">
        <el-table-column prop="id" label="Runtime ID" width="90" />
        <el-table-column prop="run_type" label="Type" width="120" />
        <el-table-column prop="run_status" label="Status" width="100">
          <template #default="scope">
            <el-tag :type="statusColor(scope.row.run_status)" size="small">{{ scope.row.run_status }}</el-tag>
          </template>
        </el-table-column>
        <!-- The number of steps, the number of searches, the number of rewrites and the shape of this operation -->
        <el-table-column prop="total_step" label="Steps" width="80" />
        <el-table-column prop="retrieve_count" label="Retrieval" width="80" />
        <el-table-column prop="rewrite_count" label="Rewrite" width="80" />
        <el-table-column prop="output_summary" label="Final conclusion" show-overflow-tooltip />
        <el-table-column prop="error_message" label="Failure reason" show-overflow-tooltip />
        <el-table-column prop="cost_millis" label="Elapsed time (ms)" width="110" />
        <el-table-column prop="create_time" label="Time" width="180" />
        <el-table-column label="Actions" width="110" fixed="right">
          <template #default="scope">
            <el-button type="primary" size="small" @click="viewTimeline(scope.row.id)">Time line</el-button>
          </template>
        </el-table-column>
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

    <!-- Implementation time line window: what was done at each step of this operation and what the result was -->
    <el-dialog title="Execution time line" v-model="data.timelineVisible" width="70%" destroy-on-close>
      <div v-if="data.timeline.run" style="padding-bottom: 12px">
        <el-tag :type="statusColor(data.timeline.run.run_status)" style="margin-right: 12px">{{ data.timeline.run.run_status }}</el-tag>
        <span style="margin-right: 16px">Total {{ data.timeline.run.total_step }} Step</span>
        <span style="margin-right: 16px">Retrieval {{ data.timeline.run.retrieve_count }} the</span>
        <span style="margin-right: 16px">Rewrite {{ data.timeline.run.rewrite_count }} the</span>
        <span>Elapsed time {{ data.timeline.run.cost_millis }} ms</span>
      </div>
      <!-- Nodes per step, nouns corresponding to the nodes in the status map -->
      <el-timeline style="max-height: 460px; overflow: auto; padding-left: 6px">
        <el-timeline-item
            v-for="step in data.timeline.steps"
            :key="step.id"
            :type="nodeColor(step.node_name)"
            :timestamp="'Step ' + step.step_index + ' · ' + step.node_name"
        >
          <div style="font-weight: bold; margin-bottom: 4px">{{ step.step_name }}</div>
          <!-- Enter and return to the original display, see what the model determines at each step. -->
          <div style="font-size: 12px; color: #666">Input parameters:{{ step.request_params }}</div>
          <div style="font-size: 12px; color: #666">Output:{{ step.response_result }}</div>
          <div v-if="step.error_message" style="font-size: 12px; color: #f56c6c">Failure:{{ step.error_message }}</div>
        </el-timeline-item>
      </el-timeline>
      <template #footer>
        <el-button @click="data.timelineVisible = false">Close</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { reactive } from 'vue'
import { ElMessage } from 'element-plus'
import request from '@/utils/request.js'
import router from '@/router/index.js'

const data = reactive({
  tableData: [],
  pageNum: 1,
  pageSize: 10,
  total: 0,
  // Value of the frame drawn under top active status
  runStatus: '',
  // Control the time line window
  timelineVisible: false,
  timeline: {}
})

const load = () => {
  request.get('/agent/runs', {
    params: { page_num: data.pageNum, page_size: data.pageSize, run_status: data.runStatus }
  }).then(res => {
    if (res.code === '200') {
      data.tableData = res.data?.list || []
      data.total = res.data?.total || 0
    } else {
      ElMessage.error(res.msg)
    }
  })
}

const viewTimeline = (runId) => {
  // Take the full step of this run and render it into a time line in step_index order
  request.get('/agent/steps/' + runId).then(res => {
    if (res.code === '200') {
      data.timeline = res.data
      data.timelineVisible = true
    } else {
      ElMessage.error(res.msg)
    }
  })
}

const statusColor = (status) => {
  // Green finished, red failed, blue running
  if (status === 'Completed') {
    return 'success'
  }
  if (status === 'Run failed') {
    return 'danger'
  }
  return 'primary'
}

const nodeColor = (node) => {
  // We'll search the green, we'll judge oranges, we'll find out which way to go.
  if (node === 'retrieve') {
    return 'success'
  }
  if (node === 'grade' || node === 'check') {
    return 'warning'
  }
  if (node === 'fallback') {
    return 'danger'
  }
  return 'primary'
}

const reset = () => {
  data.runStatus = ''
  data.pageNum = 1
  load()
}

// The address bar with runId when jumping from the Agent executable opens that time line directly.
const runId = router.currentRoute.value.query.runId
load()
if (runId) {
  viewTimeline(runId)
}
</script>
