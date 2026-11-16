<template>
  <section class="documents">
    <header class="documents-header">
      <div>
        <h1>Document Management</h1>
        <p>Upload, preview, and index files in your knowledge bases.</p>
      </div>
      <el-button type="primary" :icon="Upload" @click="handleAdd">Upload document</el-button>
    </header>

    <div class="documents-panel">
      <form class="documents-filters" @submit.prevent="search">
        <el-input v-model="data.name" aria-label="Document name" placeholder="Search documents" :prefix-icon="Search" clearable />
        <el-select v-model="data.kbId" aria-label="Knowledge base" placeholder="All knowledge bases" clearable>
          <el-option v-for="kb in data.kbOptions" :key="kb.id" :label="kb.name" :value="kb.id" />
        </el-select>
        <el-select v-model="data.parseStatus" aria-label="Parsing status" placeholder="All parsing statuses" clearable>
          <el-option v-for="status in parseStatuses" :key="status" :label="status" :value="status" />
        </el-select>
        <div class="filter-buttons">
          <el-button native-type="submit" type="primary">Search</el-button>
          <el-button @click="reset">Reset</el-button>
        </div>
      </form>

      <div class="documents-toolbar">
        <span aria-live="polite">{{ data.total }} {{ data.total === 1 ? 'document' : 'documents' }}</span>
        <el-button v-if="data.ids.length" type="danger" plain size="small" @click="delBatch">
          Delete selected ({{ data.ids.length }})
        </el-button>
      </div>

      <el-table class="documents-table" :data="data.tableData" @selection-change="handleSelectionChange"
                scrollbar-always-on empty-text="No documents found">
        <el-table-column type="selection" width="44" />
        <el-table-column label="Document" :min-width="compactTable ? 140 : 270">
          <template #default="{ row }">
            <div class="document-entry">
              <el-icon class="document-icon" :class="'file-' + row.file_type?.toLowerCase()"><Document /></el-icon>
              <div>
                <button v-if="row.parse_status === 'Parsed'" type="button" class="document-title document-link"
                        @click="viewText(row.id)">{{ row.name }}</button>
                <span v-else class="document-title">{{ row.name }}</span>
                <span class="document-meta">{{ row.file_type }} · {{ formatSize(row.file_size) }}</span>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column v-if="!compactTable" prop="kb_name" label="Knowledge base" min-width="165" />
        <el-table-column v-if="!compactTable" label="Parsing" width="122">
          <template #default="{ row }">
            <span class="document-status" :class="'status-' + parseStatusType(row.parse_status)">
              <el-icon v-if="row.parse_status === 'Parsed'"><CircleCheck /></el-icon>
              {{ row.parse_status || 'Pending' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column v-if="!compactTable" label="Embedding" width="136">
          <template #default="{ row }">
            <span class="document-status" :class="'status-' + embeddingStatusTypes[row.vector_status]">
              <el-icon v-if="row.vector_status === 'Completed'"><CircleCheck /></el-icon>
              {{ row.vector_status || 'Pending' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="Actions" :width="compactTable ? 78 : 104" class-name="documents-actions">
          <template #default="{ row }">
            <el-dropdown trigger="click">
              <el-button text size="small" :aria-label="'Actions for ' + row.name">
                More<el-icon class="el-icon--right"><ArrowDown /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item :icon="InfoFilled" @click="details = row">Document details</el-dropdown-item>
                  <el-dropdown-item :icon="InfoFilled" @click="openHistory(row)">Processing history</el-dropdown-item>
                  <el-dropdown-item v-if="row.parse_status === 'Parsed'" :icon="View" @click="viewText(row.id)">View parsed text</el-dropdown-item>
                  <el-dropdown-item :icon="Download" @click="download(row.file_url)">Download file</el-dropdown-item>
                  <el-dropdown-item :icon="Edit" @click="handleEdit(row)">Edit document</el-dropdown-item>
                  <el-dropdown-item divided :icon="MagicStick" :disabled="row.parse_status === 'Parsing'" @click="parseDoc(row.id)">Parse document</el-dropdown-item>
                  <el-dropdown-item v-if="row.parse_status === 'Parsed'" :icon="Scissor" @click="openSplit(row)">Split into chunks</el-dropdown-item>
                  <el-dropdown-item v-if="row.chunk_count > 0" :icon="Cpu" :disabled="row.vector_status === 'Embedding in progress'" @click="vectorize(row)">Embed chunks</el-dropdown-item>
                  <el-dropdown-item v-if="['Completed', 'Failed'].includes(row.vector_status)" :icon="Brush" @click="clearVectors(row)">Clear embeddings</el-dropdown-item>
                  <el-dropdown-item divided :icon="Delete" class="document-delete" @click="del(row.id)">Delete document</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
        </el-table-column>
      </el-table>
      <div v-if="data.total > data.pageSize" class="documents-pagination">
        <el-pagination v-model:current-page="data.pageNum" background layout="prev, pager, next"
                       :page-size="data.pageSize" :total="data.total" @current-change="load" />
      </div>
    </div>

    <el-dialog :model-value="!!details" title="Document details" width="min(520px, calc(100vw - 28px))"
               @close="details = null">
      <dl v-if="details" class="document-details">
        <dt>Document</dt><dd>{{ details.name }}</dd>
        <dt>Knowledge base</dt><dd>{{ details.kb_name || '—' }}</dd>
        <dt>Parsing</dt><dd>{{ details.parse_status || 'Pending' }}</dd>
        <dt>Embedding</dt><dd>{{ details.vector_status || 'Pending' }}</dd>
        <dt>Characters</dt><dd>{{ details.char_count ?? '—' }}</dd>
        <dt>Chunks</dt><dd>{{ details.chunk_count ?? '—' }}</dd>
        <dt>Uploaded</dt><dd>{{ details.create_time || '—' }}</dd>
        <dt>Includes tables</dt><dd>{{ details.has_table || '—' }}</dd>
        <dt>Processed with OCR</dt><dd>{{ details.has_ocr || '—' }}</dd>
      </dl>
    </el-dialog>

    <!-- Upload and edit this window, destroy-on-close. Make sure it's a brand new form every time it opens. -->
    <el-dialog title="Knowledge document" v-model="data.formVisible" width="min(640px, calc(100vw - 28px))" destroy-on-close>
      <el-form ref="formRef" :model="data.form" :rules="data.rules" label-width="100px" style="padding: 20px">
        <!-- id of the selected knowledge bank to store in data.form. kb_id, determining which library this document will be hung while saving -->
        <el-form-item label="Knowledge base" prop="kb_id">
          <el-select :disabled="!!data.form.id" v-model="data.form.kb_id" style="width: 100%" placeholder="Select a knowledge base">
            <el-option v-for="kb in data.kbOptions" :key="kb.id" :label="kb.name" :value="kb.id"></el-option>
          </el-select>
        </el-form-item>
        <!-- Trigger handlefileupload after uploading successfully, refill the address, file name, size into form -->
        <el-form-item label="Document file" prop="file_url">
          <el-upload
              :action="baseUrl + '/files/upload'" :headers="uploadHeaders"
              :on-success="handleFileUpload"
              :limit="1"
              accept=".pdf,.docx,.xlsx,.md,.txt"
          >
            <el-button type="primary">Choose file</el-button>
            <template #tip>
              <div style="color: #999; font-size: 12px">Supports PDF, Word, Excel, Markdown, TXT</div>
            </template>
          </el-upload>
        </el-form-item>
        <!-- Filename selected, shown after uploading successfully, allowing users to confirm that the file is correctly transmitted -->
        <el-form-item label="Selected file" v-if="data.form.file_name">
          <span>{{ data.form.file_name }}</span>
        </el-form-item>
        <!-- Keeps the empty backend on top of the uploaded filename. -->
        <el-form-item label="Document name">
          <el-input v-model="data.form.name" placeholder="Defaults to the uploaded file name"></el-input>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="data.formVisible = false">Cancel</el-button>
        <el-button type="primary" @click="save">Confirm</el-button>
      </template>
    </el-dialog>

    <!-- Cut the window and let the manager pick a strategy before cutting it. -->
    <el-dialog title="Split document" v-model="data.splitVisible" width="min(520px, calc(100vw - 28px))" destroy-on-close>
      <el-form label-width="100px" style="padding: 10px 20px">
        <el-form-item label="Document">
          <span>{{ data.splitDoc.name }}</span>
        </el-form-item>
        <!-- When not selected backends are rounded in the order of "Knowledge-bound policy > global default strategy" -->
        <el-form-item label="Chunking Strategy">
          <el-select v-model="data.splitStrategyId" clearable style="width: 100%" placeholder="Do not select and use the default strategy">
              <el-option
                v-for="item in data.strategyOptions"
                :key="item.id"
                :label="`${item.name} (${item.strategy_type}, ${item.chunk_size} characters)`"
                :value="item.id"
            ></el-option>
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="data.splitVisible = false">Cancel</el-button>
        <el-button type="primary" @click="doSplit">Start splitting</el-button>
      </template>
    </el-dialog>

    <el-dialog title="Processing history" v-model="data.historyVisible" width="min(900px, calc(100vw - 28px))">
      <p>{{ data.historyDoc?.name }}</p>
      <p v-if="data.historyUnavailable" role="status">Cannot reach processing history. Reconnecting automatically…</p>
      <p v-if="data.tasks[0]?.task_status === 'Processing'" role="status">Processing is in progress. This view refreshes automatically.</p>
      <el-alert v-if="data.tasks[0]?.task_status === 'Failed'" type="error" :closable="false"
                :title="data.tasks[0].error_message || 'Processing failed. Review the error and retry this step.'" />
      <el-table :data="data.tasks" max-height="420" scrollbar-always-on style="margin-top: 16px">
        <el-table-column prop="task_type" label="Step" min-width="130" />
        <el-table-column prop="task_status" label="Status" width="110" />
        <el-table-column label="Progress" width="110">
          <template #default="{ row }">{{ row.success_count }} / {{ row.total_count }}</template>
        </el-table-column>
        <el-table-column prop="error_message" label="Details" min-width="220" />
      </el-table>
      <p v-if="!data.tasks.length">No processing attempts yet.</p>
      <template #footer>
        <el-button @click="refreshHistory">Refresh</el-button>
        <el-button v-if="data.tasks[0]?.can_retry" type="primary" :loading="data.retrying" @click="retryTask">Retry failed step</el-button>
        <el-button @click="data.historyVisible = false">Close</el-button>
      </template>
    </el-dialog>

    <!-- View the parsing text window from /knowledgeDocument/parsedText/{id} -->
    <el-dialog title="Parsing results" v-model="data.textVisible" width="min(900px, calc(100vw - 28px))" destroy-on-close>
      <div style="margin-bottom: 10px">
        <span style="margin-right: 20px">Characters {{ data.textDetail.char_count }}</span>
        <el-tag v-if="data.textDetail.has_table === 'Yes'" type="warning" size="small">Includes tables</el-tag>
        <el-tag v-if="data.textDetail.has_ocr === 'Yes'" type="danger" size="small" style="margin-left: 6px">Passed OCR</el-tag>
      </div>
      <!-- Parsing text may be long, fixed height with scrollbar; white-space save wrapping of lines and tables -->
      <div style="max-height: 500px; overflow: auto; background: #f7f7f7; padding: 12px; white-space: pre-wrap; font-size: 13px">{{ data.textDetail.parsed_text }}</div>
      <template #footer>
        <el-button @click="data.textVisible = false">Close</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup>
const uploadHeaders = { token: JSON.parse(localStorage.getItem("xm-user") || "{}").token }
import { onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ArrowDown, Brush, CircleCheck, Cpu, Delete, Document, Download, Edit, InfoFilled, MagicStick, Scissor, Search, Upload, View } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/utils/request.js'

// File Uploading Component Sends its own request and does not leave
const baseUrl = import.meta.env.VITE_BASE_URL

const data = reactive({
  // Control the display of document windows to hide, upload and edit the same window
  formVisible: false,
  historyVisible: false,
  historyUnavailable: false,
  historyDoc: null,
  tasks: [],
  retrying: false,
  // The objects tied to the field in the window. Id for editing, no id for adding
  form: {},
  // Table data, filled with list from /knowledgeDocument/selectPage
  tableData: [],
  // Underloading options for the knowledge base from /knowledgeBase/selectAll, shared with window
  kbOptions: [],
  pageNum: 1,
  pageSize: 10,
  total: 0,
  // The value of the top knowledge base to frame as a kb_id parameter to limit the query range
  kbId: '',
  // The value of the top document name search box
  name: '',
  // The value to pull the frame under a top resolution state
  parseStatus: '',
  // _Other Organiser
  ids: [],
  // Control to view display hidden from parsing text windows
  textVisible: false,
  // ParsedText/ {id} fills the results with details
  textDetail: {},
  // Controls display and hiding of split window
  splitVisible: false,
  // The current line of documents to cut, display names on the window
  splitDoc: {},
  // Cut the selected policy id in the window, leaving backend with default policy for empty expression
  splitStrategyId: '',
  // Pull options from /chunkStrategy/selectAll
  strategyOptions: [],
  // The front-end verification rules, knowledge base and files are selected
  rules: {
    kb_id: [
      { required: true, message: 'Select the knowledge base to which you belong', trigger: 'change' }
    ],
    file_url: [
      { required: true, message: 'Please upload the file first.', trigger: 'change' }
    ]
  }
})

// FormRef bind el-form in the window, trigger whole table check when point is determined
const formRef = ref()
const details = ref(null)
const narrowTable = window.matchMedia('(max-width: 760px)')
const compactTable = ref(narrowTable.matches)
const updateTableLayout = (event) => { compactTable.value = event.matches }
onMounted(() => narrowTable.addEventListener('change', updateTableLayout))
onBeforeUnmount(() => narrowTable.removeEventListener('change', updateTableLayout))
const parseStatuses = ['Pending parsing', 'Parsing', 'Parsed', 'Parsing failed']
const embeddingStatusTypes = { Completed: 'success', Failed: 'danger', 'Embedding in progress': 'primary' }

const loadKbOptions = () => {
  // Only return to normal knowledge base. Disabled library does not appear in the bottom frame
  request.get('/knowledgeBase/selectAll').then(res => {
    if (res.code === '200') {
      data.kbOptions = res.data || []
    }
  })
}

const load = () => {
  // Page-by-page query interface, with five parameters from page numbers, number of lines per page, knowledge base frame, name search box, parsing status
  request.get('/knowledgeDocument/selectPage', {
    params: {
      page_num: data.pageNum,
      page_size: data.pageSize,
      kb_id: data.kbId || undefined,
      name: data.name,
      parse_status: data.parseStatus
    }
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

let historyTimer
const refreshHistory = async (quiet = false) => {
  if (!data.historyDoc) return false
  const docId = data.historyDoc.id
  try {
    const res = await request.get('/knowledgeDocument/tasks/' + docId, { quiet: quiet === true })
    if (data.historyDoc?.id !== docId) return false
    if (res.code !== '200') return false
    data.tasks = res.data || []
    data.historyUnavailable = false
    return true
  } catch {
    if (data.historyDoc?.id === docId) data.historyUnavailable = true
    return false
  }
}
const openHistory = async (row) => {
  data.historyDoc = row
  data.historyUnavailable = false
  data.tasks = []
  data.historyVisible = true
  await refreshHistory()
}
const retryTask = async () => {
  data.retrying = true
  try {
    const res = await request.post('/knowledgeDocument/retry/' + data.historyDoc.id)
    if (res.code === '200') {
      ElMessage.success('Retry started')
      await refreshHistory()
      load()
    } else ElMessage.error(res.msg)
  } catch {
    await refreshHistory(true)
  } finally { data.retrying = false }
}
onMounted(() => {
  historyTimer = setInterval(() => {
    if (data.historyVisible && (data.historyUnavailable || data.tasks.some(task => task.task_status === 'Processing'))) {
      refreshHistory(true).then(updated => { if (updated) load() })
    }
  }, 3000)
})
onBeforeUnmount(() => clearInterval(historyTimer))

const handleAdd = () => {
  // Add a clean form when adding it, and no id, save will use the new interface;
  // If the top has selected a knowledge base, the window will be taped by default, save one choice.
  data.form = { kb_id: data.kbId || undefined }
  data.formVisible = true
}

const handleEdit = (row) => {
  // (b) Deep copy of the current line to avoid direct modification of the objects in the tabledata leading to a change in the window;
  // id, save will update the interface when a copy comes in.
  data.form = JSON.parse(JSON.stringify(row))
  data.formVisible = true
}

const handleFileUpload = (res, file) => {
  if (res.code !== '200') {
    ElMessage.error(res.msg)
    return
  }
  // rs.data is the download address returned from backend, written when saved in form
  data.form.file_url = res.data
  // Original filename, backend extrapolate file_type by its suffix to determine which solver chapter 07 will use
  data.form.file_name = file.name
  // File bytes, turn to KB / MB when the list page is displayed
  data.form.file_size = file.size
  // If the document name is not filled out, use the file name on top of it. The user can change it again.
  if (!data.form.name) {
    data.form.name = file.name
  }
}

const save = () => {
  formRef.value.validate(valid => {
    // The knowledge base does not select or file is not requested. Direct red word hint under form
    if (!valid) {
      return
    }
    // Data.form.id exists to show that the current window is editing mode, backend updating the original record of the matrix with id update
    // Data.form.id does not exist as an explanation for the new mode, and backends insert a new document to record and refresh the number of documents in the knowledge base
    const action = data.form.id
        ? request.put('/knowledgeDocument/update', data.form)
        : request.post('/knowledgeDocument/add', data.form)
    action.then(res => {
      if (res.code === '200') {
        ElMessage.success('Saved')
        // Close the window and recheck the list so that the table shows the latest data
        data.formVisible = false
        load()
      } else {
        // The knowledge base is disabled, file type does not support these business failures and backend returns the human voice tips in msg
        ElMessage.error(res.msg)
      }
    })
  })
}

const del = (id) => {
  // Play confirmation boxes before deleting, do not enter then, do not request
  ElMessageBox.confirm('Data cannot be recovered after deletion. Are you sure you want to delete?', 'Confirm deletion', { type: 'warning' }).then(() => {
    request.delete('/knowledgeDocument/delete/' + id).then(res => {
      if (res.code === '200') {
        ElMessage.success('Deleted')
        // Deletes the recheck list, and the number of files on the knowledge bank has been cut off from the backend.
        load()
      } else {
        ElMessage.error(res.msg)
      }
    })
  })
}

const delBatch = () => {
  // If you don't get a line, just take the lot off.
  if (!data.ids.length) {
    ElMessage.warning('Please select data')
    return
  }
  ElMessageBox.confirm('Data cannot be recovered after deletion. Are you sure you want to delete?', 'Confirm deletion', { type: 'warning' }).then(() => {
    // The request for delete requests is written in config.data, and the backends are accepted by JSON array
    request.delete('/knowledgeDocument/deleteBatch', { data: data.ids }).then(res => {
      if (res.code === '200') {
        ElMessage.success('Deleted')
        load()
      } else {
        ElMessage.error(res.msg)
      }
    })
  })
}

const handleSelectionChange = (rows) => {
  // ids of the selected row are pumped into data.ids for batch deletion when table ticking changes
  data.ids = rows.map(item => item.id)
}

const parseDoc = (id) => {
  // The interface only changes the state to "solved" and returns.
  request.post('/knowledgeDocument/parse/' + id).then(res => {
    if (res.code === '200') {
      ElMessage.success('Parsing has started, refresh later to view results')
      // Update this line to blue "solvering"
      load()
    } else {
      // The file does not exist, the operations are being parsed for failure, and backend returns a human message in msg
      ElMessage.error(res.msg)
    }
  })
}

const viewText = (id) => {
  // Parsed_text column, which is separated by an interface,
  // Do not put in the list interface to avoid a list returning too big
  request.get('/knowledgeDocument/parsedText/' + id).then(res => {
    if (res.code === '200') {
      data.textDetail = res.data
      data.textVisible = true
    } else {
      ElMessage.error(res.msg)
    }
  })
}

const loadStrategyOptions = () => {
  // Cut down data from the strategy in the window and take it once when you enter the page
  request.get('/chunkStrategy/selectAll').then(res => {
    if (res.code === '200') {
      data.strategyOptions = res.data || []
    }
  })
}

const openSplit = (row) => {
  // Write down which line to cut, the policy pulls down by default and leaves it in the back end with the default strategy
  data.splitDoc = row
  data.splitStrategyId = ''
  data.splitVisible = true
}

const doSplit = () => {
  // Strategy_id does not transmit backends in order of "knowledge base binding policy > global default strategy"
  request.post('/knowledgeChunk/split/' + data.splitDoc.id, null, {
    params: { strategy_id: data.splitStrategyId || undefined }
  }).then(res => {
    if (res.code === '200') {
      ElMessage.success('Splitting has started, refresh later to view fragment count')
      data.splitVisible = false
      load()
    } else {
      // Unsolved, default strategy failed. Backend returns a human voice tip in msg
      ElMessage.error(res.msg)
    }
  })
}

const vectorize = (row) => {
  // The interface returns only by changing the status to "quantified" and the real model calls for batches in backstage tasks.
  request.post('/vectorize/document/' + row.id).then(res => {
    if (res.code === '200') {
      ElMessage.success('Vectorization has started, refresh later to view vectorization status')
      // Update it immediately. The Quantified status of this line in the table becomes "in quantitative mode."
      load()
    } else {
      // No vector model, no fill, no cut, no vector model. Backends go back to the human voice.
      ElMessage.error(res.msg)
    }
  })
}

const clearVectors = (row) => {
  // The clear vector is for remodeling or redecorating, first confirm.
  ElMessageBox.confirm('After clearing, this document needs to be re-vectorized. Confirm to continue?', 'Clear confirmation', { type: 'warning' }).then(() => {
    request.delete('/vectorize/document/' + row.id).then(res => {
      if (res.code === '200') {
        // Res.data has cleared out a few vectors.
        ElMessage.success(res.data)
        load()
      } else {
        // When the library is not connected, the backend gives a clear hint.
        ElMessage.error(res.msg)
      }
    })
  })
}

const download = (url) => {
  // The browser downloads the file from file_url in a new tab.
  window.open(url)
}

const formatSize = (size) => {
  // File_size records bytes, converted into better read units by size
  if (!size) {
    return '-'
  }
  if (size < 1024) {
    return size + ' B'
  }
  if (size < 1024 * 1024) {
    return (size / 1024).toFixed(1) + ' KB'
  }
  return (size / 1024 / 1024).toFixed(1) + ' MB'
}

const parseStatusType = (status) => {
  // Parsing green, parsing failed red, parsing blue, to parse grey
  if (status === 'Parsed') {
    return 'success'
  }
  if (status === 'Parsing failed') {
    return 'danger'
  }
  if (status === 'Parsing') {
    return 'primary'
  }
  return 'info'
}

const search = () => {
  data.pageNum = 1
  load()
}

const reset = () => {
  // Clear three search conditions and go back to page one, check the full list again.
  data.kbId = ''
  data.name = ''
  data.parseStatus = ''
  data.pageNum = 1
  load()
}

// Page loads first two drop-down data from the knowledge base and cut policy, then check the first page document
// Page loads first with the knowledge base drop data and then check the first page document
loadKbOptions()
loadStrategyOptions()
load()
</script>

<style scoped>
.documents {
  max-width: 1440px;
  margin: 0 auto;
}

.documents-header,
.documents-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.documents-header {
  margin-bottom: 22px;
}

.documents-header h1 {
  margin: 0;
  font-size: clamp(25px, 2.65vw, 37px);
  line-height: 1.2;
  font-weight: 720;
  letter-spacing: -.045em;
}

.documents-header p {
  margin: 4px 0 0;
  color: var(--ink-muted);
}

.documents-panel {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}

.documents-filters {
  display: grid;
  grid-template-columns: minmax(155px, 1.1fr) minmax(175px, 1fr) minmax(150px, .8fr) auto;
  gap: 10px;
  padding: 16px;
}

.filter-buttons {
  display: flex;
}

.documents-toolbar {
  min-height: 42px;
  padding: 6px 16px;
  color: var(--ink-muted);
  font-size: 13px;
}

.documents :deep(.el-table__cell) {
  padding: 9px 0;
}

.documents :deep(.documents-actions .cell) {
  text-overflow: clip;
}

.document-entry {
  display: flex;
  align-items: center;
  gap: 10px;
}

.document-icon {
  flex: none;
  color: var(--accent);
  font-size: 19px;
}

.file-pdf {
  color: #bf3547;
}

.file-excel {
  color: #17834c;
}

.document-title {
  display: block;
  text-align: left;
  font-weight: 600;
  line-height: 1.4;
  overflow-wrap: break-word;
}

.document-link {
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--ink);
  font-size: inherit;
  cursor: pointer;
}

.document-link:hover {
  text-decoration: underline;
}

.document-meta {
  display: block;
  margin-top: 3px;
  color: var(--ink-muted);
  font-size: 12px;
  line-height: 1.35;
}

.document-status {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border-radius: 6px;
  background: #eef1f5;
  color: #415066;
  font-size: 12px;
  font-weight: 600;
  line-height: 1.3;
}

.status-success {
  background: #e5f5ec;
  color: #14633c;
}

.status-danger,
.document-delete {
  color: #a11b1b;
}

.status-danger {
  background: #fcebec;
}

.status-primary {
  background: var(--accent-soft);
  color: var(--accent-strong);
}

.documents-pagination {
  display: flex;
  justify-content: flex-end;
  padding: 14px 16px;
}

.document-details {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 8px 16px;
  margin: 0;
}

.document-details dt {
  color: var(--ink-muted);
}

.document-details dd {
  margin: 0;
  overflow-wrap: anywhere;
}

@media (max-width: 1020px) {
  .documents-filters {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 500px) {
  .documents-header {
    align-items: flex-start;
    flex-direction: column;
    margin-bottom: 16px;
  }

  .documents-filters {
    grid-template-columns: 1fr;
  }

  .document-icon {
    display: none;
  }
}
</style>
