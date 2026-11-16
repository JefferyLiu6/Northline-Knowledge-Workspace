<template>
  <div>
    <div class="card" style="margin-bottom: 5px">
      <el-form label-width="90px" style="padding: 10px 20px 0">
        <!-- Pick at least one knowledge base with 0 in brackets. -->
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
        <!-- Limits the search to a few documents. When there are both old and new versions in the library, it is used to shrink the scope to the new version. -->
        <el-form-item label="Limit documents">
          <el-select v-model="data.documentIds" multiple clearable style="width: 100%" placeholder="Not selecting means searching the entire knowledge base">
            <el-option v-for="doc in data.docOptions" :key="doc.id" :label="doc.name" :value="doc.id"></el-option>
          </el-select>
        </el-form-item>
        <!-- Use default policy when not selecting backends. Which way does option text lead to this strategy? -->
        <el-form-item label="Retrieval Strategy">
          <el-select v-model="data.strategyId" clearable style="width: 100%" placeholder="Do not select and use the default strategy">
            <el-option
                v-for="item in data.strategyOptions"
                :key="item.id"
                :label="strategyLabel(item)"
                :value="item.id"
            ></el-option>
          </el-select>
        </el-form-item>
        <!-- Questions entered are stored in data.query, which is sent to the search interface as a query parameter -->
        <el-form-item label="Search query">
          <el-input v-model="data.query" type="textarea" :rows="2" placeholder="Enter a question a user might ask"></el-input>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="data.searching" @click="search">Start Retrieval</el-button>
        </el-form-item>
      </el-form>
    </div>

    <!-- It's only shown when you have the results. The page is empty. -->
    <div class="card" style="margin-bottom: 5px" v-if="data.outcome.strategy_name">
      <div style="padding: 10px 0">
        <span style="margin-right: 20px">Use Strategy:{{ data.outcome.strategy_name }}</span>
        <span style="margin-right: 20px">Recall {{ data.outcome.results.length }} items</span>
        <span style="margin-right: 20px">Total Time Consumed {{ data.outcome.cost_millis }} ms</span>
        <!-- The fractional order is given backend by end of line, and the same column numbers have different meanings in different strategies -->
        <span v-if="data.outcome.score_scale">Unit of Measurement:{{ data.outcome.score_scale }}</span>
      </div>
      <!-- How many times a road has been recalled, how long it took to judge where the bottlenecks were. -->
      <el-table stripe :data="data.outcome.stages" size="small" style="margin-bottom: 10px">
        <el-table-column prop="name" label="Stage" width="200" />
        <el-table-column prop="count" label="Number of Items" width="120" />
        <el-table-column prop="cost_millis" label="Elapsed time (ms)" width="120" />
        <!-- The query rewrite will place the redacted query in detail -->
        <el-table-column label="Details">
          <template #default="scope">
            <div v-for="(line, index) in scope.row.detail" :key="index">{{ line }}</div>
          </template>
        </el-table-column>
      </el-table>
      <!-- When you rewrite it, the question is actually searched differently from the user input. -->
      <div v-if="data.outcome.queries && data.outcome.queries.length > 1" style="padding-bottom: 10px">
        <div style="margin-bottom: 4px">Actual questions used for retrieval (total {{ data.outcome.queries.length }} Items):</div>
        <el-tag v-for="(one, index) in data.outcome.queries" :key="index" size="small" style="margin: 0 6px 6px 0">{{ one }}</el-tag>
      </div>
    </div>

    <div class="card" v-if="data.outcome.results && data.outcome.results.length">
      <!-- Recall results are displayed from top to bottom in final ranking -->
      <el-table stripe :data="data.outcome.results">
        <!-- The title is the line number. Chapter 13 says, "The paragraph you should see is in fourth place." -->
        <el-table-column type="index" label="Ranking" width="70" />
        <!-- The result of both calls back will show "BM25 Retrieval + Vector Search." -->
        <el-table-column prop="source" label="Recall Source" width="160" />
        <!-- Summary of table: vector single path is cosine similarity, then blended to RRF ranking, and re-allocated associated fractions -->
        <el-table-column prop="score" :label="data.outcome.score_scale || 'Score'" width="120" />
        <el-table-column prop="document_name" label="Source Document" width="180" show-overflow-tooltip />
        <el-table-column prop="chunk_type" label="Type" width="90" />
        <!-- When the parent piece is filled back, this column shows which sub-block of the actual target can be traced back to the matching section. -->
        <el-table-column prop="matched_chunk_id" label="Matched Child Chunk" width="100">
          <template #default="scope">{{ scope.row.matched_chunk_id || '-' }}</template>
        </el-table-column>
        <el-table-column prop="content" label="Fragment content" show-overflow-tooltip />
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { reactive } from 'vue'
import { ElMessage } from 'element-plus'
import request from '@/utils/request.js'

const data = reactive({
  // Drop-down options from /retrieval/ knowledgeBases, with clips
  kbOptions: [],
  // Draw down options for the search policy from /retrieval/strategies
  strategyOptions: [],
  // Selected knowledge library id arrays, multiple selection and cross-configuring
  kbIds: [],
  // Drop-down options in the document, changing with the selected knowledge base
  docOptions: [],
  // The selected document id array is empty for open documents
  documentIds: [],
  // Selected policy id, empty for backends with default policy
  strategyId: '',
  // Search query
  query: '',
  // Retrieval buttons are rounded, vector searches need to adjust models. Hundreds of milliseconds slow.
  searching: false,
  // Search results, including results, pages, cost_millis
  outcome: {}
})

const loadOptions = () => {
  // The knowledge base pulls down the clips, and the zero library can't retrieve anything. You can see it before you choose.
  request.get('/retrieval/knowledgeBases').then(res => {
    if (res.code === '200') {
      data.kbOptions = res.data || []
    }
  })
  // The policy pulls down, the text of the option writes about the switch and does not cut the page to see the configuration
  request.get('/retrieval/strategies').then(res => {
    if (res.code === '200') {
      data.strategyOptions = res.data || []
    }
  })
}

const onKbChange = () => {
  // Changed the knowledge base. The files originally selected may not belong to these libraries anymore, emptying them.
  data.documentIds = []
  data.docOptions = []
  if (!data.kbIds.length) {
    return
  }
  // Each library takes a list of documents and merges them into one drop down data
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
}

const strategyLabel = (item) => {
  // How many ways do you spell this strategy into the text of options, such as "full-mixed search plus rewrite" (vector + BM25)?
  const parts = []
  if (item.vector_enabled === 'Yes') {
    parts.push('Vector')
  }
  if (item.bm25_enabled === 'Yes') {
    parts.push('BM25')
  }
  return item.name + '(' + parts.join('+') + ')'
}

const emptyReason = (outcome) => {
  // There are two completely different reasons for the outcome, and the reminder must be separated or lead people to the wrong place.
  // Threshold filtering of that step is like "4 ~0", not 0 before the arrow, which means the clip is called back.
  // It's a cut off by the threshold, and it's time to adjust the thresholds in the strategy, not to see if there are cuts in the knowledge base.
  const filtered = (outcome.stages || []).find(
      stage => stage.name.toLowerCase().startsWith('threshold filter') && / → 0$/.test(String(stage.count)) && !/^0 →/.test(String(stage.count))
  )
  if (filtered) {
    // The backend wrote down the fraction intervals and thresholds in detail to give a hint of the last sentence.
    const lines = filtered.detail || []
    return lines[lines.length - 1] || 'All recalled fragments are below the threshold, please lower the threshold of this strategy'
  }
  return 'No fragments were recalled, check if this library has been vectorized or split'
}

const search = () => {
  // The front end stopped without a single knowledge base. No request.
  if (!data.kbIds.length) {
    ElMessage.warning('Select a knowledge base')
    return
  }
  if (!data.query.trim()) {
    ElMessage.warning('Please enter a search problem.')
    return
  }
  data.searching = true
  request.post('/retrieval/search', {
    kb_ids: data.kbIds,
    strategy_id: data.strategyId || null,
    // Open-time null, backend to open document
    document_ids: data.documentIds.length ? data.documentIds : null,
    query: data.query
  }).then(res => {
    if (res.code === '200') {
      // Recall results, score_scale fractions, Cost_millis
      // Recall results, stages are time-consuming and cost_millis is time-consuming.
      data.outcome = res.data
      if (!res.data.results.length) {
        ElMessage.warning(emptyReason(res.data))
      }
    } else {
      // No vector model, no vector library, no strategy open. Backends back to people's tip.
      ElMessage.error(res.msg)
    }
  }).finally(() => {
    data.searching = false
  })
}

// Take two drops on page load
loadOptions()
</script>
