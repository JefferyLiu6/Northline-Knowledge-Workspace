<template>
  <div>
    <div class="card" style="margin-bottom: 5px">
      <!-- The entered policy name is stored in data.name, which is a blurry match for the name parameter -->
      <el-input v-model="data.name" style="width: 240px; margin-right: 10px" placeholder="Please enter the strategy name to search"></el-input>
      <el-button type="info" plain @click="load">Query</el-button>
      <el-button type="warning" plain style="margin: 0 10px" @click="reset">Reset</el-button>
    </div>
    <div class="card" style="margin-bottom: 5px">
      <!-- Open the blank window and go to add process -->
      <el-button type="primary" plain @click="handleAdd">Add new</el-button>
    </div>

    <div class="card" style="margin-bottom: 5px">
      <!-- Data.tableData from list returned by /retrievalStrategy/ selectPage -->
      <el-table stripe :data="data.tableData">
        <el-table-column prop="name" label="Strategy Name" width="220" />
        <!-- I've put seven switches together in a string of labels, and I can see at first glance how far this strategy has gone. -->
        <el-table-column label="Enabled capabilities" min-width="320">
          <template #default="scope">
            <el-tag v-if="scope.row.vector_enabled === 'Yes'" size="small" style="margin-right: 4px">Vector {{ scope.row.vector_top_k }}</el-tag>
            <el-tag v-if="scope.row.bm25_enabled === 'Yes'" type="success" size="small" style="margin-right: 4px">BM25 {{ scope.row.bm25_top_k }}</el-tag>
            <el-tag v-if="scope.row.rerank_enabled === 'Yes'" type="warning" size="small" style="margin-right: 4px">Rerank {{ scope.row.rerank_top_n }}</el-tag>
            <el-tag v-if="scope.row.query_rewrite_enabled === 'Yes'" type="danger" size="small" style="margin-right: 4px">{{ scope.row.rewrite_type }}</el-tag>
            <el-tag v-if="scope.row.parent_recall_enabled === 'Yes'" type="info" size="small" style="margin-right: 4px">Parent chunk expansion</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="rrf_k" label="RRF k" width="90" />
        <!-- The two thresholds are in two fractions, the one that's valid is green. -->
        <el-table-column label="Threshold" width="200">
          <template #default="scope">
            <el-tag :type="scope.row.score_scale === 'Cosine Similarity' ? 'success' : 'info'" size="small" style="margin-right: 4px">
              Cosine {{ scope.row.vector_score_threshold ?? '-' }}
            </el-tag>
            <el-tag :type="scope.row.score_scale === 'Recalculate Relevant Divisions' ? 'success' : 'info'" size="small">
              Rerank {{ scope.row.rerank_score_threshold ?? '-' }}
            </el-tag>
          </template>
        </el-table-column>
        <!-- Use default strategy when question-and-answer application is unmatched, with only one full table -->
        <el-table-column prop="is_default" label="Default" width="80">
          <template #default="scope">
            <el-tag v-if="scope.row.is_default === 'Yes'" type="success" size="small">Default</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="remark" label="Remarks" show-overflow-tooltip />
        <el-table-column label="Actions" width="140" fixed="right">
          <template #default="scope">
            <!-- Bring the current line data into the window and go through the editing process. -->
            <el-button type="primary" size="small" @click="handleEdit(scope.row)">Edit</el-button>
            <!-- id of current line only to delete -->
            <el-button type="danger" size="small" @click="del(scope.row.id)">Delete</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
    <!-- Data.total is 0-hour full page bar not rendered -->
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

    <!-- Add and edit this window, destroy-on-close to make sure that every opening is a brand new form -->
    <el-dialog title="Retrieval Strategy" v-model="data.formVisible" width="55%" destroy-on-close>
      <el-form ref="formRef" :model="data.form" :rules="data.rules" label-width="130px" style="padding: 10px 20px">
        <el-form-item label="Strategy Name" prop="name">
          <el-input v-model="data.form.name" placeholder="Please enter the strategy name"></el-input>
        </el-form-item>

        <el-divider content-position="left">I. Retrieval</el-divider>
        <!-- Vector searches understand semantics and do not recognize exact characters -->
        <el-form-item label="Vector search">
          <el-radio-group v-model="data.form.vector_enabled">
            <el-radio value="Yes">Enabled</el-radio>
            <el-radio value="No">Close</el-radio>
          </el-radio-group>
          <el-input-number v-if="data.form.vector_enabled === 'Yes'" v-model="data.form.vector_top_k" :min="1" :max="50" style="margin-left: 20px; width: 130px"></el-input-number>
        </el-form-item>
        <!-- BM25 Character recognition, lack of synonym expression, complementarity -->
        <el-form-item label="BM25 Search">
          <el-radio-group v-model="data.form.bm25_enabled">
            <el-radio value="Yes">Enabled</el-radio>
            <el-radio value="No">Close</el-radio>
          </el-radio-group>
          <el-input-number v-if="data.form.bm25_enabled === 'Yes'" v-model="data.form.bm25_top_k" :min="1" :max="50" style="margin-left: 20px; width: 130px"></el-input-number>
        </el-form-item>
        <!-- It's only when both roads open, k. The bigger the larger it gets, the more it turns out to be called back by multiple paths at once. -->
        <el-form-item v-if="data.form.vector_enabled === 'Yes' && data.form.bm25_enabled === 'Yes'" label="RRF Fusion Constant">
          <el-input-number v-model="data.form.rrf_k" :min="1" :max="200" style="width: 100%"></el-input-number>
        </el-form-item>

        <el-divider content-position="left">II. Re-ranking</el-divider>
        <!-- Rehearsal is a cross-coding exercise, which matches the vectors, but adjusts the model once every time. -->
        <el-form-item label="Rerank">
          <el-radio-group v-model="data.form.rerank_enabled">
            <el-radio value="Yes">Enabled</el-radio>
            <el-radio value="No">Close</el-radio>
          </el-radio-group>
          <el-input-number v-if="data.form.rerank_enabled === 'Yes'" v-model="data.form.rerank_top_n" :min="1" :max="20" style="margin-left: 20px; width: 130px"></el-input-number>
        </el-form-item>

        <el-divider content-position="left">III. Query Rewriting</el-divider>
        <!-- Three ways to rewrite it are single options, with different output patterns, and stringing will double the number of searches. -->
        <el-form-item label="Query rewrite">
          <el-radio-group v-model="data.form.query_rewrite_enabled">
            <el-radio value="Yes">Enabled</el-radio>
            <el-radio value="No">Close</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="data.form.query_rewrite_enabled === 'Yes'" label="Rewriting Method">
          <el-select v-model="data.form.rewrite_type" style="width: 100%">
            <el-option label="Multi-query expansion" value="Multi-query expansion"></el-option>
            <el-option label="Coreference resolution" value="Coreference resolution"></el-option>
            <el-option label="HyDE" value="HyDE"></el-option>
          </el-select>
        </el-form-item>
        <!-- Only extra query extensions can be used in the same number, and one of the remaining two outputs has been rewritten -->
        <el-form-item v-if="data.form.query_rewrite_enabled === 'Yes' && data.form.rewrite_type === 'Multi-query expansion'" label="Expand Number of Items">
          <el-input-number v-model="data.form.multi_query_count" :min="1" :max="5" style="width: 100%"></el-input-number>
        </el-form-item>

        <el-divider content-position="left">IV. Post-processing</el-divider>
        <!-- It makes sense to split up a store, and it doesn't work. -->
        <el-form-item label="Parent chunk expansion">
          <el-radio-group v-model="data.form.parent_recall_enabled">
            <el-radio value="Yes">Enabled</el-radio>
            <el-radio value="No">Close</el-radio>
          </el-radio-group>
        </el-form-item>
        <!-- The threshold card is the final fraction, and the final fractions are determined by the top switches.
             So tell the user which of the current combinations will go to, and then let him fill in the corresponding threshold. -->
        <el-form-item label="Current Unit of Measurement">
          <el-tag type="success" size="small">{{ data.formScale || 'Calculating' }}</el-tag>
          <span style="margin-left: 8px; color: #999; font-size: 12px">
            Determined by the combination of switches above, only the threshold of this level will take effect below
          </span>
        </el-form-item>
        <!-- It only takes effect when the vector is called back. The result below the threshold is dropped and a question-and-answer session is conducted. -->
        <el-form-item label="Cosine Similarity Threshold">
          <el-input-number v-model="data.form.vector_score_threshold" :min="0" :max="1" :step="0.05" :precision="3" style="width: 100%"></el-input-number>
          <div :style="{ fontSize: '12px', color: data.formScale === 'Cosine Similarity' ? '#67c23a' : '#999' }">
            Effective when vector single-path retrieval is enabled. Relevant fragments tested 0.46~0.77, completely irrelevant questions 0.14~0.23, recommended 0.3
          </div>
        </el-form-item>
        <!-- Effective only when rehearsing is started. Recalculations and cosine similarities are 0 to 1, but the range of extractions varies by an order of magnitude -->
        <el-form-item label="Recalculate relevant sub-threshold values">
          <el-input-number v-model="data.form.rerank_score_threshold" :min="0" :max="1" :step="0.01" :precision="3" style="width: 100%"></el-input-number>
          <div :style="{ fontSize: '12px', color: data.formScale === 'Recalculate Relevant Divisions' ? '#67c23a' : '#999' }">
            Effective when re-ranking is enabled. Relevant fragments tested 0.14~0.20, completely irrelevant questions 0.006, recommended 0.05
          </div>
        </el-form-item>
        <!-- It doesn't mean absolutely, when multiple calls to integration turn into the countdown, and neither threshold is effective. -->
        <el-form-item v-if="data.formScale === 'RRF rank'" label=" ">
          <span style="color: #e6a23c; font-size: 12px">
            The final score of the current combination is the RRF ranking score, which only indicates the order of ranking and cannot be compared with a fixed threshold, this strategy will not perform threshold filtering.
            To make the threshold effective, please enable re-ranking.
          </span>
        </el-form-item>
        <el-form-item label="Set as Default">
          <el-radio-group v-model="data.form.is_default">
            <el-radio value="Yes">Yes</el-radio>
            <el-radio value="No">No</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="Remarks">
          <el-input v-model="data.form.remark" type="textarea" :rows="2" placeholder="Explain the scenarios this strategy is suitable for"></el-input>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="data.formVisible = false">Cancel</el-button>
        <el-button type="primary" @click="save">Confirm</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/utils/request.js'

const data = reactive({
  // Control the display of a strategic window hidden, add and edit the same bullet window
  formVisible: false,
  // The objects bound by each box in the window. Id for editing, no id for adding
  form: {},
  // Under the current set of switches, the order of the final fractions is calculated from a backend interface.
  // Determine which of the next two threshold frames will be effective
  formScale: '',
  // Table data filled with list from /retrievalStrategy/ selectPage
  tableData: [],
  pageNum: 1,
  pageSize: 10,
  total: 0,
  // Value of the top policy name search box
  name: '',
  // The front end verification rules for windows, the name must be filled
  rules: {
    name: [
      { required: true, message: 'Please enter the strategy name', trigger: 'blur' }
    ]
  }
})

// FormRef bind el-form in the window, trigger whole table check when point is determined
const formRef = ref()

const load = () => {
  // Page-by-page query interface with three parameters from page numbers, number of lines per page and name search boxes
  request.get('/retrievalStrategy/selectPage', {
    params: { page_num: data.pageNum, page_size: data.pageSize, name: data.name }
  }).then(res => {
    if (res.code === '200') {
      // res. data is a backend PageInfo, List renderer table, total drive tab
      data.tableData = res.data?.list || []
      data.total = res.data?.total || 0
    } else {
      ElMessage.error(res.msg)
    }
  })
}

// When the window is turned on, ask again what the final fractions of the back end of the set are.
// The algorithms and search tube lines are the same, only one in the back end retrieval_service.pendict_score_scale
// The front side doesn't count for itself.
const loadFormScale = () => {
  request.post('/retrievalStrategy/scoreScale', data.form).then(res => {
    if (res.code === '200') {
      // Outline determines which of the next two threshold boxes will be effective and stored in formScale for template determination
      data.formScale = res.data
    }
  })
}

// It's these switches that affect the scale. Any one of them changes and retakes it.
watch(
    () => [
      data.form.vector_enabled,
      data.form.bm25_enabled,
      data.form.rerank_enabled,
      data.form.query_rewrite_enabled,
      data.form.rewrite_type,
      data.form.multi_query_count
    ],
    () => {
      // Don't ask when the window is open.
      if (data.formVisible) loadFormScale()
    }
)

const handleAdd = () => {
  // Give a baseline configuration when adding: only vector search, the equivalent of RAG as described in Chapter 13
  data.form = {
    vector_enabled: 'Yes',
    vector_top_k: 5,
    bm25_enabled: 'No',
    bm25_top_k: 5,
    rrf_k: 60,
    rerank_enabled: 'No',
    rerank_top_n: 3,
    query_rewrite_enabled: 'No',
    multi_query_count: 3,
    parent_recall_enabled: 'No',
    // The default values for the two thresholds are given between live intervals of their respective ranges:
    // The snippets under cosine resemblance 0.46~0.77, irrelevant 0.14~0.23 0.3 in the middle
    vector_score_threshold: 0.3,
    // Reorder relevant segments 0.14 - 0.20, irrelevant 0.006,0.05 in the middle
    rerank_score_threshold: 0.05,
    is_default: 'No'
  }
  data.formVisible = true
  // When the window is open, you take the schematics first and then you press the watch to follow the switch.
  loadFormScale()
}

const handleEdit = (row) => {
  // (b) Deep copy of the current line to avoid direct modification of the objects in the tabledata leading to a change in the window;
  // id, save will update the interface when a copy comes in.
  data.form = JSON.parse(JSON.stringify(row))
  data.formVisible = true
  loadFormScale()
}

const save = () => {
  formRef.value.validate(valid => {
    // Do not send a request if the name is not filled out. Enter a direct red hint below the box
    if (!valid) {
      return
    }
    // Data.form.id exists to show that the current window is editing mode, and backend updates retrieval_strategy's original log
    // Data.form.id does not exist as an explanation for adding a new mode, and the backend inserts a new strategy record
    const action = data.form.id
        ? request.put('/retrievalStrategy/update', data.form)
        : request.post('/retrievalStrategy/add', data.form)
    action.then(res => {
      if (res.code === '200') {
        ElMessage.success('Saved')
        data.formVisible = false
        load()
      } else {
        // Both roads closed, rewrite open, no choice, thresholds crossed and backends returned to the tip.
        ElMessage.error(res.msg)
      }
    })
  })
}

const del = (id) => {
  // Play confirmation boxes before deleting, do not enter then, do not request
  ElMessageBox.confirm('Data cannot be recovered after deletion. Are you sure you want to delete?', 'Confirm deletion', { type: 'warning' }).then(() => {
    request.delete('/retrievalStrategy/delete/' + id).then(res => {
      if (res.code === '200') {
        ElMessage.success('Deleted')
        load()
      } else {
        // The default policy does not allow deletion. Backend stops.
        ElMessage.error(res.msg)
      }
    })
  })
}

const reset = () => {
  // Empty search conditions and return to page one, check the full list again
  data.name = ''
  data.pageNum = 1
  load()
}

// Check the page once it is loaded. You can see the first page when you enter the page.
load()
</script>
