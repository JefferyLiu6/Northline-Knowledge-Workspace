<template>
  <div>
    <div class="card" style="margin-bottom: 5px">
      <el-form label-width="100px" style="padding: 10px 20px 0">
        <!-- Pick at least one knowledge base with zero in brackets. -->
        <el-form-item label="Knowledge base">
          <el-select v-model="data.kbIds" multiple style="width: 100%" placeholder="Please select a knowledge base to retrieve" @change="onKbChange">
            <el-option
                v-for="kb in data.kbOptions"
                :key="kb.id"
                :label="kb.name + '(Fragment ' + kb.chunk_count + ' items)'"
                :value="kb.id"
            ></el-option>
          </el-select>
        </el-form-item>
        <!-- Pick up a maximum of four. Run one more and get it all over again. -->
        <el-form-item label="Comparison strategy">
          <el-select v-model="data.strategyIds" multiple :multiple-limit="4" style="width: 100%" placeholder="Select up to 4 strategies for side-by-side comparison">
            <el-option
                v-for="item in data.strategyOptions"
                :key="item.id"
                :label="strategyLabel(item)"
                :value="item.id"
            ></el-option>
          </el-select>
        </el-form-item>
        <!-- Restricted access to certain documents only -->
        <el-form-item label="Limit documents">
          <el-select v-model="data.documentIds" multiple clearable style="width: 100%" placeholder="Not selecting means searching the entire knowledge base">
            <el-option v-for="doc in data.docOptions" :key="doc.id" :label="doc.name" :value="doc.id"></el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="Search query">
          <el-input v-model="data.query" type="textarea" :rows="2" placeholder="Enter a question a user might ask"></el-input>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="data.running" @click="compare">Begin Comparison</el-button>
          <!-- This library's snippet type distribution, which determines whether to open a parent block. -->
          <span v-if="data.chunkTypes.parent > 0" style="margin-left: 16px; color: #999; font-size: 12px">
            This library is parent-child chunking (parent chunk {{ data.chunkTypes.parent }} Items / child chunk {{ data.chunkTypes.child }} Items), recommend enabling parent chunk fill comparison
          </span>
        </el-form-item>
      </el-form>
    </div>

    <!-- Each set of policies is displayed in parallel rows, the number of columns equals the number of strategies selected -->
    <el-row :gutter="10" v-if="data.columns.length">
      <el-col :span="24 / data.columns.length" v-for="column in data.columns" :key="column.strategy_id">
        <div class="card" style="margin-bottom: 5px">
          <div style="font-weight: bold; padding-bottom: 6px">{{ column.strategy_name }}</div>
          <!-- This column shows the reasons for failure when a set of policies fails, and others are displayed as usual -->
          <el-alert v-if="column.error" :title="column.error" type="error" :closable="false" style="margin-bottom: 8px" />
          <div style="color: #666; font-size: 12px; padding-bottom: 6px">
            Recall {{ column.results.length }} Items · Time Consumed {{ column.cost_millis }} ms
          </div>
          <!-- Each strategy may have different final numeracy outlines, without marking it out.
               0.03 (RRF rank) in the left column is considered worse than 0.19 (rehearsal score) in the right row. -->
          <div v-if="column.score_scale" style="font-size: 12px; padding-bottom: 6px">
            <el-tag size="small" type="info">Unit of Measurement:{{ column.score_scale }}</el-tag>
          </div>
          <!-- It's a time-consuming phase to see where the strategy is slow. -->
          <el-table :data="column.stages" size="small" style="margin-bottom: 8px">
            <el-table-column prop="name" label="Stage" />
            <el-table-column prop="count" label="Number of Items" width="90" />
            <el-table-column prop="cost_millis" label="ms" width="70" />
          </el-table>
          <!-- Recall results from top to bottom by name, and the same line compares points of order. -->
          <el-table :data="column.results" size="small">
            <el-table-column type="index" label="#" width="45" />
            <!-- Show the column's order on the top of the table, and see if the two columns are the same ruler before the cross-column score. -->
            <el-table-column prop="score" :label="column.score_scale || 'Score'" width="110" />
            <el-table-column prop="content" label="Segment" show-overflow-tooltip />
          </el-table>
        </div>
      </el-col>
    </el-row>

    <div class="card" v-if="data.records.length">
      <div style="font-weight: bold; padding-bottom: 8px">History Debug Records</div>
      <!-- Each comparison will be archived, and a little look will get the results of the recall. -->
      <el-table stripe :data="data.records" size="small">
        <el-table-column prop="query" label="Question" show-overflow-tooltip />
        <el-table-column prop="strategy_ids" label="Comparison strategy" width="140" />
        <el-table-column prop="cost_millis" label="Elapsed time (ms)" width="110" />
        <el-table-column prop="create_time" label="Time" width="180" />
        <el-table-column label="Actions" width="90">
          <template #default="scope">
            <el-button type="primary" size="small" @click="viewRecord(scope.row.id)">View</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { reactive } from 'vue'
import { ElMessage } from 'element-plus'
import request from '@/utils/request.js'

const data = reactive({
  // Drop-down options for the knowledge base from /retrieval/ knowledgeBases
  kbOptions: [],
  // Draw down options for the search policy from /retrieval/strategies
  strategyOptions: [],
  // Drop-down options in documents, associated with the knowledge base
  docOptions: [],
  // Selected knowledge banks, strategies, documents
  kbIds: [],
  strategyIds: [],
  documentIds: [],
  // Search query
  query: '',
  // The spin state of the contrast buttons, several sets of tactics running in a series, which takes several times as much time as a single set.
  running: false,
  // A column for each set of strategies from /retrievalStrategy/ compare returned columns
  columns: [],
  // Distribution of the snippet types in this library
  chunkTypes: {},
  // History debug record list
  records: []
})

const loadOptions = () => {
  request.get('/retrieval/knowledgeBases').then(res => {
    if (res.code === '200') {
      data.kbOptions = res.data || []
    }
  })
  request.get('/retrieval/strategies').then(res => {
    if (res.code === '200') {
      data.strategyOptions = res.data || []
    }
  })
}

const loadRecords = () => {
  // The list interface does not return the snapshot text. Only complete snapshots can be retrieved when you click on them
  request.get('/retrievalStrategy/records', {
    params: { page_num: 1, page_size: 10 }
  }).then(res => {
    if (res.code === '200') {
      data.records = res.data?.list || []
    }
  })
}

const onKbChange = () => {
  // Changed the knowledge base. The files originally selected may not belong to these libraries anymore, emptying them.
  data.documentIds = []
  data.docOptions = []
  data.chunkTypes = {}
  if (!data.kbIds.length) {
    return
  }
  Promise.all(
      data.kbIds.map(kbId => request.get('/knowledgeDocument/selectPage', {
        params: { kb_id: kbId, page_num: 1, page_size: 200 }
      }))
  ).then(responses => {
    const merged = []
    responses.forEach(res => {
      if (res.code === '200') {
        merged.push(...(res.data?.list || []))
      }
    })
    data.docOptions = merged
  })
  // Take the snippet type distribution from the first library as a hint
  request.get('/retrievalStrategy/chunkTypes/' + data.kbIds[0]).then(res => {
    if (res.code === '200') {
      data.chunkTypes = res.data || {}
    }
  })
}

const strategyLabel = (item) => {
  // How many steps do you spell this strategy into the text of options?
  const parts = []
  if (item.vector_enabled === 'Yes') {
    parts.push('Vector')
  }
  if (item.bm25_enabled === 'Yes') {
    parts.push('BM25')
  }
  if (item.rerank_enabled === 'Yes') {
    parts.push('Rerank')
  }
  if (item.query_rewrite_enabled === 'Yes') {
    parts.push(item.rewrite_type)
  }
  if (item.parent_recall_enabled === 'Yes') {
    parts.push('Parent chunk expansion')
  }
  return item.name + '(' + parts.join('+') + ')'
}

const compare = () => {
  if (!data.kbIds.length) {
    ElMessage.warning('Select a knowledge base')
    return
  }
  if (!data.strategyIds.length) {
    ElMessage.warning('Please select at least one strategy')
    return
  }
  if (!data.query.trim()) {
    ElMessage.warning('Please enter a search problem.')
    return
  }
  data.running = true
  request.post('/retrievalStrategy/compare', {
    kb_ids: data.kbIds,
    strategy_ids: data.strategyIds,
    document_ids: data.documentIds.length ? data.documentIds : null,
    query: data.query
  }).then(res => {
    if (res.code === '200') {
      // Each one of the columns is a complete search for a strategy.
      data.columns = res.data.columns || []
      // This comparison has been archived and updated to the history list.
      loadRecords()
    } else {
      ElMessage.error(res.msg)
    }
  }).finally(() => {
    data.running = false
  })
}

const viewRecord = (id) => {
  // Draw the archived snapshots as they are, and overwrite the current comparison.
  request.get('/retrievalStrategy/records/' + id).then(res => {
    if (res.code === '200') {
      data.query = res.data.query
      data.columns = res.data.columns || []
    } else {
      ElMessage.error(res.msg)
    }
  })
}

// Remove pulling data and historical records when page loads
loadOptions()
loadRecords()
</script>
