<template>
  <div>
    <div class="card" style="margin-bottom: 5px">
      <!-- Filter by tool encoding, see the history of a tool call -->
      <el-select v-model="data.toolCode" clearable style="width: 200px; margin-right: 10px" placeholder="Please select a tool">
        <el-option v-for="item in data.toolOptions" :key="item.tool_code" :label="item.tool_name" :value="item.tool_code"></el-option>
      </el-select>
      <!-- It's a failed call. It's the most common thing to check. -->
      <el-select v-model="data.callStatus" clearable style="width: 140px; margin-right: 10px" placeholder="Call Result">
        <el-option label="Succeeded" value="Succeeded"></el-option>
        <el-option label="Failed" value="Failed"></el-option>
      </el-select>
      <!-- Sift by running number to see which tools Agent runs a given time -->
      <el-input v-model="data.runId" style="width: 160px; margin-right: 10px" placeholder="Filter by Run ID"></el-input>
      <el-button type="info" plain @click="load">Query</el-button>
      <el-button type="warning" plain style="margin: 0 10px" @click="reset">Reset</el-button>
    </div>

    <div class="card" style="margin-bottom: 5px">
      <!-- Data.tableData from list returned by /actionTool/logs -->
      <el-table stripe :data="data.tableData">
        <el-table-column prop="id" label="Log ID" width="90" />
        <el-table-column prop="run_id" label="Runtime ID" width="90">
          <template #default="scope">{{ scope.row.run_id || '-' }}</template>
        </el-table-column>
        <el-table-column prop="tool_name" label="Tool" width="150" />
        <!-- Green success, red failure, clear out which calls are wrong. -->
        <el-table-column prop="call_status" label="Result" width="90">
          <template #default="scope">
            <el-tag :type="scope.row.call_status === 'Succeeded' ? 'success' : 'danger'" size="small">{{ scope.row.call_status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="request_params" label="Input Parameters" show-overflow-tooltip />
        <el-table-column prop="error_message" label="Failure reason" show-overflow-tooltip />
        <el-table-column prop="cost_millis" label="Elapsed time (ms)" width="110" />
        <el-table-column prop="create_time" label="Time" width="180" />
        <el-table-column label="Actions" width="90" fixed="right">
          <template #default="scope">
            <el-button type="primary" size="small" @click="viewDetail(scope.row)">Details</el-button>
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

    <!-- Details pop windows: Full access and return, see here when checking tool implementation issues -->
    <el-dialog title="Call Details" v-model="data.detailVisible" width="60%" destroy-on-close>
      <div style="margin-bottom: 6px; font-weight: bold">Input Parameters</div>
      <div style="background: #f7f7f7; padding: 10px; white-space: pre-wrap; font-size: 13px; margin-bottom: 12px">{{ data.detail.request_params || 'None' }}</div>
      <div style="margin-bottom: 6px; font-weight: bold">Return</div>
      <div style="max-height: 320px; overflow: auto; background: #f7f7f7; padding: 10px; white-space: pre-wrap; font-size: 13px">{{ data.detail.response_result || data.detail.error_message || 'None' }}</div>
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

const data = reactive({
  tableData: [],
  // Drop-down options from /actionTool/logSummary
  toolOptions: [],
  pageNum: 1,
  pageSize: 10,
  total: 0,
  // Three screening conditions
  toolCode: '',
  callStatus: '',
  runId: '',
  // Control the details of a window.
  detailVisible: false,
  detail: {}
})

const loadTools = () => {
  // The statistical interface returns the list of tools by its way.
  request.get('/functionTool/logSummary').then(res => {
    if (res.code === '200') {
      data.toolOptions = res.data || []
    }
  })
}

const load = () => {
  request.get('/functionTool/logs', {
    params: {
      page_num: data.pageNum,
      page_size: data.pageSize,
      tool_code: data.toolCode,
      call_status: data.callStatus,
      run_id: data.runId || undefined
    }
  }).then(res => {
    if (res.code === '200') {
      data.tableData = res.data?.list || []
      data.total = res.data?.total || 0
    } else {
      ElMessage.error(res.msg)
    }
  })
}

const viewDetail = (row) => {
  // All entries and returns in the list are cut off, details of which are full.
  data.detail = row
  data.detailVisible = true
}

const reset = () => {
  data.toolCode = ''
  data.callStatus = ''
  data.runId = ''
  data.pageNum = 1
  load()
}

// Take the tool drops when a page is loaded and check the first page log
loadTools()
load()
</script>
