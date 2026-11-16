<template>
  <div>
    <div class="card" style="margin-bottom: 5px">
      <!-- The report under the same evaluation is comparable, first selected. -->
      <el-select v-model="data.datasetId" clearable style="width: 260px; margin-right: 10px" placeholder="Filter by evaluation set" @change="loadReports">
        <el-option
            v-for="item in data.datasets"
            :key="item.id"
            :label="item.name"
            :value="item.id"
        ></el-option>
      </el-select>
      <el-button type="primary" @click="compare">Compare selected reports</el-button>
      <span style="margin-left: 12px; color: #999; font-size: 12px">Check at least two reports in the table</span>
    </div>

    <div class="card" style="margin-bottom: 5px">
      <!-- Check two or more and compare. -->
      <el-table stripe :data="data.reports" @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="55" />
        <el-table-column prop="strategy_name" label="Strategy" width="220" />
        <!-- How many steps did this strategy take? -->
        <el-table-column label="Enabled capabilities" min-width="220">
          <template #default="scope">
            <el-tag v-for="item in scope.row.abilities" :key="item" size="small" style="margin-right: 4px">{{ item }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="case_count" label="Test case" width="80" />
        <el-table-column prop="context_recall_avg" label="Recall" width="90" />
        <el-table-column prop="context_precision_avg" label="Precision" width="90" />
        <el-table-column prop="faithfulness_avg" label="Faithfulness" width="90" />
        <el-table-column prop="answer_relevancy_avg" label="Relevance" width="90" />
        <el-table-column prop="overall_score" label="Comprehensive" width="90" />
        <!-- Chapter 26 states that the comparison table must be time-consuming, otherwise there is no choice. -->
        <el-table-column prop="avg_cost_millis" label="Per-item time (ms)" width="130">
          <template #default="scope">{{ scope.row.avg_cost_millis ?? '—' }}</template>
        </el-table-column>
        <el-table-column prop="create_time" label="Time" width="180" />
      </el-table>
    </div>

    <!-- Comparison results: Cluster column charts + schedules -->
    <div class="card" v-if="data.compare.columns">
      <div style="font-weight: bold; padding-bottom: 10px">
        {{ data.compare.dataset_name }} · {{ data.compare.columns.length }} Strategy comparison
      </div>
      <div ref="chartRef" style="height: 340px"></div>
      <el-table stripe :data="tableRows" size="small" style="margin-top: 10px">
        <el-table-column prop="metric" label="Metric" width="140" />
        <el-table-column
            v-for="(column, index) in data.compare.columns"
            :key="column.report_id"
            :label="column.strategy_name"
        >
          <template #default="scope">{{ scope.row.values[index] ?? '—' }}</template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, reactive, ref } from 'vue'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import request from '@/utils/request.js'

const chartRef = ref()

const data = reactive({
  datasets: [],
  datasetId: '',
  reports: [],
  // List of selected reports
  selectedIds: [],
  // Comparison results, including columns and services
  compare: {},

})

// Table of details below the chart: rows for each indicator and scores for each strategy in a row
const tableRows = computed(() => {
  if (!data.compare.series) {
    return []
  }
  return data.compare.series.map(item => ({ metric: item.metric, values: item.values }))
})

const loadDatasets = () => {
  request.get('/evalDataset/selectAll').then(res => {
    if (res.code === '200') {
      data.datasets = res.data || []
    }
  })
}

const loadReports = () => {
  request.get('/evalReport/selectAll', {
    params: { dataset_id: data.datasetId || undefined }
  }).then(res => {
    if (res.code === '200') {
      data.reports = res.data || []
    } else {
      ElMessage.error(res.msg)
    }
  })
}

const handleSelectionChange = (rows) => {
  data.selectedIds = rows.map(item => item.id)
}

const compare = () => {
  if (data.selectedIds.length < 2) {
    ElMessage.warning('Please select at least two reports')
    return
  }
  request.post('/evalReport/compare', { report_ids: data.selectedIds }).then(res => {
    if (res.code === '200') {
      data.compare = res.data
      // When the table and the container are rendered, draw again. Otherwise the chart won't get any heights.
      nextTick(renderChart)
    } else {
      // Select only one cross-assessment set comparison, and backend returns the human voice tip.
      ElMessage.error(res.msg)
    }
  })
}

const renderChart = () => {
  if (!chartRef.value || !data.compare.series) {
    return
  }
  // Destroy the previous example before the same container repeats the drawing, otherwise it will be stacked.
  const existing = echarts.getInstanceByDom(chartRef.value)
  if (existing) {
    existing.dispose()
  }
  const chart = echarts.init(chartRef.value, null, { locale: 'EN' })
  chart.setOption({
    color: ['#4f55d9', '#198776', '#a55729', '#8849aa', '#3775ac'],
    textStyle: { fontFamily: getComputedStyle(chartRef.value).fontFamily, color: '#526078' },
    tooltip: { trigger: 'axis' },
    legend: { data: data.compare.columns.map(item => item.strategy_name) },
    grid: { left: 50, right: 20, top: 50, bottom: 30 },
    // Four indicators classified as horizontal axes, with a set of columns for each set of strategies
    xAxis: { type: 'category', data: data.compare.series.map(item => item.metric) },
    // All four indicators are 0 to 1, the vertical axis is fixed, and visual comparisons can be made between sub-comparisons.
    yAxis: { type: 'value', min: 0, max: 1 },
    series: data.compare.columns.map((column, index) => ({
      name: column.strategy_name,
      type: 'bar',
      itemStyle: { borderRadius: [4, 4, 0, 0] },
      data: data.compare.series.map(item => item.values[index])
    }))
  })
}

loadDatasets()
loadReports()
</script>
