<template>
  <div>
    <div class="card" style="margin-bottom: 5px">
      <!-- Select the evaluation first, and the list of cases below changes. -->
      <el-select v-model="data.datasetId" style="width: 280px; margin-right: 10px" placeholder="Please select an evaluation set" @change="loadCases">
        <el-option
            v-for="item in data.datasets"
            :key="item.id"
            :label="item.name + '(' + item.case_count + ' Case'"
            :value="item.id"
        ></el-option>
      </el-select>
      <el-button type="primary" plain @click="handleAddDataset">Create evaluation set</el-button>
      <el-button type="danger" plain :disabled="!data.datasetId" @click="delDataset">Delete evaluation set</el-button>
    </div>

    <div class="card" style="margin-bottom: 5px" v-if="data.datasetId">
      <!-- Three sources for three entrances. -->
      <el-button type="primary" plain @click="handleAddCase">Manual entry</el-button>
      <el-button type="success" plain @click="data.generateVisible = true">Generate from document</el-button>
      <el-button type="warning" plain @click="convertFeedback">Extract from point-by-point feedback</el-button>
      <el-select v-model="data.source" clearable style="width: 160px; margin: 0 10px" placeholder="Filter by source" @change="loadCases">
        <el-option label="Manual entry" value="Manual entry"></el-option>
        <el-option label="Generated from document" value="Generated from document"></el-option>
        <el-option label="From feedback" value="From feedback"></el-option>
      </el-select>
      <el-input v-model="data.keyword" style="width: 200px; margin-right: 10px" placeholder="Search by issue"></el-input>
      <el-button type="info" plain @click="loadCases">Query</el-button>
    </div>

    <div class="card" style="margin-bottom: 5px" v-if="data.datasetId">
      <el-table stripe :data="data.cases">
        <el-table-column prop="question" label="Question" min-width="200" show-overflow-tooltip />
        <!-- The example of the feedback is empty and needs to be filled by hand. -->
        <el-table-column prop="ground_truth" label="Standard answers" min-width="200" show-overflow-tooltip>
          <template #default="scope">
            <span v-if="scope.row.ground_truth">{{ scope.row.ground_truth }}</span>
            <el-tag v-else type="warning" size="small">Pending</el-tag>
          </template>
        </el-table-column>
        <!-- The three sources are different colours. -->
        <el-table-column prop="source" label="Source" width="110">
          <template #default="scope">
            <el-tag :type="sourceColor(scope.row.source)" size="small">{{ scope.row.source }}</el-tag>
          </template>
        </el-table-column>
        <!-- The default that the standard answer has not been completed is to disable. -->
        <el-table-column prop="enabled" label="Participate in evaluation" width="100">
          <template #default="scope">
            <el-tag :type="scope.row.enabled === 'Yes' ? 'success' : 'info'" size="small">{{ scope.row.enabled }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="remark" label="Remarks" width="200" show-overflow-tooltip />
        <el-table-column label="Actions" width="210" fixed="right">
          <template #default="scope">
            <!-- The standard answer is that the model is created from a fragment, which may be wrong or open.
                 If you can get the originals out, then you'll be able to decide if this standard answer is a benchmark. -->
            <el-button
                type="success" size="small"
                :disabled="!scope.row.reference_chunk_ids"
                @click="viewChunks(scope.row)"
            >View original text</el-button>
            <el-button type="primary" size="small" @click="handleEditCase(scope.row)">Edit</el-button>
            <el-button type="danger" size="small" @click="delCase(scope.row.id)">Delete</el-button>
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
          @current-change="loadCases"
      />
    </div>

    <!-- New Evaluative Pool Window -->
    <el-dialog title="Create evaluation set" v-model="data.datasetVisible" width="40%" destroy-on-close>
      <el-form :model="data.datasetForm" label-width="100px" style="padding: 10px 20px">
        <el-form-item label="Evaluation set name">
          <el-input v-model="data.datasetForm.name" placeholder="Example: Product Manual Library - Baseline Evaluation Set"></el-input>
        </el-form-item>
        <el-form-item label="Link to knowledge base">
          <el-select v-model="data.datasetForm.kb_id" clearable style="width: 100%" placeholder="Which knowledge base is this evaluation set targeting">
            <el-option v-for="kb in data.kbOptions" :key="kb.id" :label="kb.name" :value="kb.id"></el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="Description">
          <el-input v-model="data.datasetForm.description" type="textarea" :rows="2"></el-input>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="data.datasetVisible = false">Cancel</el-button>
        <el-button type="primary" @click="saveDataset">Confirm</el-button>
      </template>
    </el-dialog>

    <!-- Use the usual window, manually enter and edit. -->
    <el-dialog title="Evaluation cases" v-model="data.caseVisible" width="50%" destroy-on-close>
      <el-form :model="data.caseForm" label-width="100px" style="padding: 10px 20px">
        <el-form-item label="Question">
          <el-input v-model="data.caseForm.question" type="textarea" :rows="2" placeholder="Users may ask"></el-input>
        </el-form-item>
        <!-- Without a standard answer, you can't recall context. Backend stops. -->
        <el-form-item label="Standard answers">
          <el-input v-model="data.caseForm.ground_truth" type="textarea" :rows="4" placeholder="What is the correct answer to this question"></el-input>
        </el-form-item>
        <el-form-item label="Participate in evaluation">
          <el-radio-group v-model="data.caseForm.enabled">
            <el-radio value="Yes">Yes</el-radio>
            <el-radio value="No">No</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="Remarks">
          <el-input v-model="data.caseForm.remark"></el-input>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="data.caseVisible = false">Cancel</el-button>
        <el-button type="primary" @click="saveCase">Confirm</el-button>
      </template>
    </el-dialog>

    <!-- Auto Generate Window -->
    <el-dialog title="Generate test cases from document" v-model="data.generateVisible" width="45%" destroy-on-close>
      <el-form label-width="100px" style="padding: 10px 20px">
        <el-form-item label="Knowledge base">
          <el-select v-model="data.genKbId" style="width: 100%" placeholder="Select a knowledge base" @change="loadDocs">
            <el-option v-for="kb in data.kbOptions" :key="kb.id" :label="kb.name" :value="kb.id"></el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="Document">
          <el-select v-model="data.genDocId" style="width: 100%" placeholder="The model will read a fragment of this document to generate a question-answer pair">
            <el-option v-for="doc in data.docOptions" :key="doc.id" :label="doc.name" :value="doc.id"></el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="Number of generated cases">
          <el-input-number v-model="data.genCount" :min="1" :max="20" style="width: 100%"></el-input-number>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="data.generateVisible = false">Cancel</el-button>
        <el-button type="primary" :loading="data.generating" @click="generate">Start generation</el-button>
      </template>
    </el-dialog>

    <!-- Source: Questions, standard answers, originals, right at first glance. -->
    <el-dialog title="Verify standard answer" v-model="data.chunkVisible" width="60%" destroy-on-close>
      <div style="margin-bottom: 12px">
        <div style="color: #666; font-size: 13px; margin-bottom: 4px">Question</div>
        <div>{{ data.chunkCase.question }}</div>
      </div>
      <div style="margin-bottom: 12px">
        <div style="color: #666; font-size: 13px; margin-bottom: 4px">Standard answers</div>
        <div style="font-weight: bold">{{ data.chunkCase.ground_truth || '(Not filled)' }}</div>
      </div>
      <div style="color: #666; font-size: 13px; margin-bottom: 4px">
        Source fragment original text (the model uses this segment to create the question; if it doesn't match, this standard answer is invalid)
      </div>
      <div v-if="!data.chunks.length" style="color: #999">This test case has no recorded source fragment</div>
      <div
          v-for="chunk in data.chunks" :key="chunk.chunk_id"
          style="background: #f7f7f7; border-radius: 4px; padding: 10px; margin-bottom: 8px"
      >
        <div style="color: #999; font-size: 12px; margin-bottom: 6px">
          Fragment #{{ chunk.chunk_id }} · The {{ chunk.chunk_index }} Section
          <span v-if="chunk.page_no">· The {{ chunk.page_no }} Page</span>
        </div>
        <div style="white-space: pre-wrap; line-height: 1.7">{{ chunk.content }}</div>
      </div>
      <template #footer>
        <el-button @click="data.chunkVisible = false">Close</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { reactive } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/utils/request.js'

const data = reactive({
  // Checks the window of the standard answer: which example is it currently looking at, its original source piece
  chunkVisible: false,
  chunkCase: {},
  chunks: [],
  datasets: [],
  datasetId: '',
  cases: [],
  pageNum: 1,
  pageSize: 10,
  total: 0,
  source: '',
  keyword: '',
  // Two drop-down data for the knowledge base and document
  kbOptions: [],
  docOptions: [],
  // Three pop windows.
  datasetVisible: false,
  datasetForm: {},
  caseVisible: false,
  caseForm: {},
  generateVisible: false,
  genKbId: '',
  genDocId: '',
  genCount: 5,
  generating: false
})

const loadDatasets = () => {
  request.get('/evalDataset/selectAll').then(res => {
    if (res.code === '200') {
      data.datasets = res.data || []
      // The first one was selected by default when no evaluation was chosen.
      if (!data.datasetId && data.datasets.length) {
        data.datasetId = data.datasets[0].id
        loadCases()
      }
    }
  })
}

const loadKbs = () => {
  request.get('/knowledgeBase/selectAll').then(res => {
    if (res.code === '200') {
      data.kbOptions = res.data || []
    }
  })
}

const loadDocs = () => {
  data.genDocId = ''
  if (!data.genKbId) {
    data.docOptions = []
    return
  }
  request.get('/knowledgeDocument/selectPage', {
    params: { kb_id: data.genKbId, page_num: 1, page_size: 200 }
  }).then(res => {
    if (res.code === '200') {
      data.docOptions = res.data?.list || []
    }
  })
}

const loadCases = () => {
  if (!data.datasetId) {
    return
  }
  request.get('/evalDataset/case/selectPage', {
    params: {
      dataset_id: data.datasetId,
      source: data.source,
      keyword: data.keyword,
      page_num: data.pageNum,
      page_size: data.pageSize
    }
  }).then(res => {
    if (res.code === '200') {
      data.cases = res.data?.list || []
      data.total = res.data?.total || 0
    } else {
      ElMessage.error(res.msg)
    }
  })
}

const handleAddDataset = () => {
  data.datasetForm = {}
  data.datasetVisible = true
}

const saveDataset = () => {
  request.post('/evalDataset/add', data.datasetForm).then(res => {
    if (res.code === '200') {
      ElMessage.success('Saved')
      data.datasetVisible = false
      loadDatasets()
    } else {
      ElMessage.error(res.msg)
    }
  })
}

const delDataset = () => {
  ElMessageBox.confirm('Deleting an evaluation set will also delete its test cases. Are you sure?', 'Confirm deletion', { type: 'warning' }).then(() => {
    request.delete('/evalDataset/delete/' + data.datasetId).then(res => {
      if (res.code === '200') {
        ElMessage.success('Deleted')
        data.datasetId = ''
        data.cases = []
        data.total = 0
        loadDatasets()
      } else {
        ElMessage.error(res.msg)
      }
    })
  })
}

const handleAddCase = () => {
  // The manual entry is enabled by default, and the standard answers are filled in on site.
  data.caseForm = { dataset_id: data.datasetId, source: 'Manual entry', enabled: 'Yes' }
  data.caseVisible = true
}

const viewChunks = (row) => {
  // Put this example on itself and get the original from it.
  data.chunkCase = row
  data.chunks = []
  data.chunkVisible = true
  request.get('/evalDataset/case/referenceChunks/' + row.id).then(res => {
    if (res.code === '200') {
      data.chunks = res.data
    } else {
      ElMessage.error(res.msg)
    }
  })
}

const handleEditCase = (row) => {
  data.caseForm = JSON.parse(JSON.stringify(row))
  data.caseVisible = true
}

const saveCase = () => {
  const action = data.caseForm.id
      ? request.put('/evalDataset/case/update', data.caseForm)
      : request.post('/evalDataset/case/add', data.caseForm)
  action.then(res => {
    if (res.code === '200') {
      ElMessage.success('Saved')
      data.caseVisible = false
      loadCases()
      loadDatasets()
    } else {
      // If you don't fill out a standard answer, the back end stops.
      ElMessage.error(res.msg)
    }
  })
}

const delCase = (id) => {
  ElMessageBox.confirm('Data cannot be recovered after deletion. Are you sure you want to delete?', 'Confirm deletion', { type: 'warning' }).then(() => {
    request.delete('/evalDataset/case/delete/' + id).then(res => {
      if (res.code === '200') {
        ElMessage.success('Deleted')
        loadCases()
        loadDatasets()
      } else {
        ElMessage.error(res.msg)
      }
    })
  })
}

const generate = () => {
  if (!data.genDocId) {
    ElMessage.warning('Please select a document')
    return
  }
  data.generating = true
  request.post('/evalDataset/generate', {
    dataset_id: data.datasetId,
    document_id: data.genDocId,
    count: data.genCount
  }).then(res => {
    if (res.code === '200') {
      // How many of them were produced with it?
      ElMessage.success(res.data)
      data.generateVisible = false
      loadCases()
      loadDatasets()
    } else {
      // The document has no cut, the model is not returned to active JSON and backends are returned with human voice tips
      ElMessage.error(res.msg)
    }
  }).finally(() => {
    data.generating = false
  })
}

const convertFeedback = () => {
  ElMessageBox.confirm('It will convert all pending point-by-point feedback into test cases. The standard answers need to be manually filled in. Continue?', 'Confirmation of extraction', { type: 'warning' }).then(() => {
    request.post('/evalDataset/convert', { dataset_id: data.datasetId }).then(res => {
      if (res.code === '200') {
        ElMessage.success(res.data)
        loadCases()
        loadDatasets()
      } else {
        ElMessage.error(res.msg)
      }
    })
  })
}

const sourceColor = (source) => {
  // Manually recorded blue, document generated green, feedback deposited orange
  if (source === 'Manual entry') {
    return 'primary'
  }
  if (source === 'Generated from document') {
    return 'success'
  }
  return 'warning'
}

loadDatasets()
loadKbs()
</script>
