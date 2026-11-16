<template>
  <div>
    <div class="card" style="margin-bottom: 5px">
      <el-form :inline="true" style="padding: 10px 20px 0">
        <el-form-item label="Evaluation dataset">
          <el-select v-model="data.datasetId" style="width: 260px" placeholder="Please select an evaluation set">
            <el-option
                v-for="item in data.datasets"
                :key="item.id"
                :label="item.name + '(' + item.case_count + ' Case'"
                :value="item.id"
            ></el-option>
          </el-select>
        </el-form-item>
        <!-- One more time, you can compare effects. -->
        <el-form-item label="Retrieval Strategy">
          <el-select v-model="data.strategyId" clearable style="width: 260px" placeholder="Do not select and use the default strategy">
            <el-option v-for="item in data.strategies" :key="item.id" :label="item.name" :value="item.id"></el-option>
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="start">Start evaluation</el-button>
        </el-form-item>
      </el-form>
      <div style="padding: 0 20px 10px; color: #999; font-size: 12px">
        One use case calls the model six times, 20 use cases per round approximately hundreds of thousands of input tokens. It is recommended to first verify with 5 use cases.
      </div>
    </div>

    <div class="card" style="margin-bottom: 5px">
      <el-table stripe :data="data.tasks">
        <el-table-column prop="id" label="Task ID" width="80" />
        <!-- When the reports are put together, they tell us which lines and what strategies. -->
        <el-table-column prop="dataset_name" label="Evaluation dataset" min-width="140" show-overflow-tooltip />
        <el-table-column prop="strategy_name" label="Retrieval Strategy" min-width="150" show-overflow-tooltip />
        <el-table-column prop="task_status" label="Status" width="100">
          <template #default="scope">
            <el-tag :type="statusColor(scope.row.task_status)" size="small">{{ scope.row.task_status }}</el-tag>
          </template>
        </el-table-column>
        <!-- I'll be halfway there and I'll see the numbers up. -->
        <el-table-column label="Progress" width="130">
          <template #default="scope">
            {{ scope.row.success_count }} / {{ scope.row.total_count }}
            <span v-if="scope.row.fail_count" style="color: #f56c6c">(Failure {{ scope.row.fail_count }})</span>
          </template>
        </el-table-column>
        <el-table-column prop="error_message" label="Failure reason" show-overflow-tooltip />
        <el-table-column prop="cost_millis" label="Elapsed time (ms)" width="120" />
        <el-table-column prop="create_time" label="Time" width="180" />
        <el-table-column label="Actions" width="160" fixed="right">
          <template #default="scope">
            <el-button type="primary" size="small" @click="viewResults(scope.row.id)">View Report</el-button>
            <!-- The missing and mismatched task can be deleted before the list gets too long to tell which one is valid. -->
            <el-button type="danger" size="small" @click="delTask(scope.row.id)">Delete</el-button>
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
          @current-change="loadTasks"
      />
    </div>

    <!-- Evaluation of window reports: equal score for four indicators + breakdown of each case -->
    <el-dialog title="Evaluation Report" v-model="data.reportVisible" width="80%" destroy-on-close>
      <div v-if="data.detail.report" style="padding-bottom: 12px">
        <div style="margin-bottom: 8px">
          <!-- First place in the evaluation collection: there's no comparison between a new set of questions, first you see which one is to be evaluated -->
          <span style="margin-right: 20px">Evaluation Set:<b>{{ data.detail.report.dataset_name || '—' }}</b></span>
          <span style="margin-right: 20px">Strategy:{{ data.detail.report.strategy_name }}</span>
          <span style="margin-right: 20px">Test case {{ data.detail.report.case_count }} items</span>
          <span>Comprehensive Score {{ data.detail.report.overall_score }}</span>
        </div>
        <!-- One progress bar for each of the four indicators, automatic redification below threshold -->
        <!-- Indicator description, line of achievement, and compliance with the standards are all well-counted backends in metrics, which are shown only.
             The rules and these narratives, which determine the “low amount”, are shared with the conclusions. They're not written here. -->
        <el-row :gutter="12">
          <el-col :span="6" v-for="metric in (data.detail.report.metrics || [])" :key="metric.field">
            <div style="padding: 10px; background: #f7f7f7; border-radius: 4px; height: 100%">
              <!-- Show the metric labels and corresponding values. -->
              <div style="font-size: 13px; color: #333; font-weight: bold">
                {{ metric.label }}
                <el-tag size="small" type="info" style="margin-left: 4px">{{ metric.stage }}</el-tag>
              </div>
              <div style="font-size: 11px; color: #aaa; margin-bottom: 2px">{{ metric.en }}</div>
              <!-- Green, low red. Ashes when you don't run the score... -->
              <div
                  style="font-size: 24px; font-weight: bold; line-height: 1.4"
                  :style="{ color: metric.ok === null ? '#999' : (metric.ok ? '#67c23a' : '#f56c6c') }"
              >
                {{ metric.value ?? '—' }}
              </div>
              <!-- What exactly is this indicator going on? It's written directly on the card. -->
              <div style="font-size: 12px; color: #666; line-height: 1.6; margin-bottom: 4px">
                {{ metric.plain }}
              </div>
              <!-- When a target is reached, only how much is the line; when it's low, it suggests which ring to turn. -->
              <div style="font-size: 12px; line-height: 1.6" :style="{ color: metric.ok === false ? '#f56c6c' : '#67c23a' }">
                <template v-if="metric.ok === null">
                  <span style="color: #999">Not Participated in Statistics</span>
                </template>
                <template v-else-if="metric.ok">Meets Standard (≥ {{ metric.threshold }})</template>
                <template v-else>Below {{ metric.threshold }}:{{ metric.advice }}</template>
              </div>
            </div>
          </el-col>
        </el-row>
        <!-- The conclusion is automatically generated by the cross-check table in chapter 26, which one you're going to play with. -->
        <el-alert
            :title="data.detail.report.conclusion"
            :type="data.detail.report.conclusion === 'All four indicators are within reasonable range.' ? 'success' : 'warning'"
            :closable="false"
            style="margin-top: 12px"
        />
      </div>
      <el-table stripe :data="data.detail.results" size="small" style="margin-top: 10px" max-height="400">
        <el-table-column prop="question" label="Question" min-width="150" show-overflow-tooltip />
        <!-- Standard answers are in parallel with generating them, and it's obvious whether the answer is wrong or just different. -->
        <el-table-column prop="ground_truth" label="Standard answers" min-width="150" show-overflow-tooltip />
        <el-table-column prop="answer" label="The answer that is generated" min-width="180" show-overflow-tooltip />
        <el-table-column prop="context_recall" label="Recall" width="80" />
        <el-table-column prop="context_precision" label="Precision" width="80" />
        <el-table-column prop="faithfulness" label="Faithfulness" width="90" />
        <el-table-column prop="answer_relevancy" label="Relevance" width="90" />
        <el-table-column prop="avg_score" label="Average Score" width="80" />
        <el-table-column prop="error_message" label="Failure reason" show-overflow-tooltip />
      </el-table>
      <template #footer>
        <el-button @click="data.reportVisible = false">Close</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { reactive } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/utils/request.js'

// The display configuration of the four indicators, which is the concentration of the cross-check table in Chapter 26.
const data = reactive({
  datasets: [],
  strategies: [],
  datasetId: '',
  strategyId: '',
  tasks: [],
  pageNum: 1,
  pageSize: 10,
  total: 0,
  reportVisible: false,
  detail: {}
})

const loadOptions = () => {
  request.get('/evalDataset/selectAll').then(res => {
    if (res.code === '200') {
      data.datasets = res.data || []
    }
  })
  request.get('/retrieval/strategies').then(res => {
    if (res.code === '200') {
      data.strategies = res.data || []
    }
  })
}

const loadTasks = () => {
  request.get('/evalTask/selectPage', {
    params: { page_num: data.pageNum, page_size: data.pageSize }
  }).then(res => {
    if (res.code === '200') {
      data.tasks = res.data?.list || []
      data.total = res.data?.total || 0
    } else {
      ElMessage.error(res.msg)
    }
  })
}

const start = () => {
  if (!data.datasetId) {
    ElMessage.warning('Please select an evaluation set')
    return
  }
  request.post('/evalTask/start', {
    dataset_id: data.datasetId,
    strategy_id: data.strategyId || null
  }).then(res => {
    if (res.code === '200') {
      // The interfaces are built and returned. The real evaluation runs backstage.
      ElMessage.success(res.data)
      loadTasks()
    } else {
      // No examples enabled, no maximum number of bars exceeded, evaluation collection not linked to knowledge base, backends returned to human voice tips
      ElMessage.error(res.msg)
    }
  })
}

const delTask = (id) => {
  ElMessageBox.confirm('Deleting will remove the evaluation report and results for each use case, confirm deletion?', 'Confirm Deletion', {
    type: 'warning'
  }).then(() => {
    request.delete('/evalTask/delete/' + id).then(res => {
      if (res.code === '200') {
        ElMessage.success('Deleted')
        // Deletes the redraw list and the current page may be empty
        loadTasks()
      } else {
        // The task is still running and no deletions are allowed. Backend returns a hint.
        ElMessage.error(res.msg)
      }
    })
  }).catch(() => {})
}

const viewResults = (taskId) => {
  request.get('/evalTask/results/' + taskId).then(res => {
    if (res.code === '200') {
      data.detail = res.data
      data.reportVisible = true
    } else {
      ElMessage.error(res.msg)
    }
  })
}

const statusColor = (status) => {
  if (status === 'Completed') {
    return 'success'
  }
  if (status === 'Failed') {
    return 'danger'
  }
  return 'primary'
}

loadOptions()
loadTasks()
</script>
