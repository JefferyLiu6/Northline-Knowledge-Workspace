<template>
  <div>
    <div class="card" style="margin-bottom: 5px">
      <!-- Select the knowledge base first, and the document below frame follows only documents under this library -->
      <el-select v-model="data.kbId" clearable style="width: 180px; margin-right: 10px" placeholder="Select a knowledge base" @change="onKbChange">
        <el-option v-for="kb in data.kbOptions" :key="kb.id" :label="kb.name" :value="kb.id"></el-option>
      </el-select>
      <!-- The selected document id saved in data. documentationId as a document_id parameter to limit the query range -->
      <el-select v-model="data.documentId" clearable style="width: 200px; margin-right: 10px" placeholder="Please select a document">
        <el-option v-for="doc in data.docOptions" :key="doc.id" :label="doc.name" :value="doc.id"></el-option>
      </el-select>
      <!-- A parent-separated document can look only at a child or only at a father-sid. -->
      <el-select v-model="data.chunkType" clearable style="width: 140px; margin-right: 10px" placeholder="Chunk type">
        <el-option label="Standard chunk" value="Standard chunk"></el-option>
        <el-option label="Parent chunk" value="Parent chunk"></el-option>
        <el-option label="Child chunk" value="Child chunk"></el-option>
      </el-select>
      <!-- It's a blurry match in the text of the clip, which one of the words is cut. -->
      <el-input v-model="data.keyword" style="width: 200px; margin-right: 10px" placeholder="Search chunk text"></el-input>
      <!-- Retrieve with the current four search conditions -->
      <el-button type="info" plain @click="load">Query</el-button>
      <!-- Clear search conditions and return to page one. -->
      <el-button type="warning" plain style="margin: 0 10px" @click="reset">Reset</el-button>
    </div>
    <div class="card" style="margin-bottom: 5px">
      <!-- Remove the selected multilines from the table -->
      <el-button type="danger" plain @click="delBatch">Batch Delete</el-button>
    </div>

    <div class="card" style="margin-bottom: 5px">
      <!-- Data.tableData from list returned by /knowledgeChunk/electPage -->
      <el-table stripe :data="data.tableData" @selection-change="handleSelectionChange">
        <!-- Multiple rows, delete use with batch -->
        <el-table-column type="selection" width="55" />
        <el-table-column prop="chunk_index" label="Serial number" width="70" />
        <!-- The parent only makes context refills and does not participate in searching, distinguishing between different colours -->
        <el-table-column prop="chunk_type" label="Type" width="90">
          <template #default="scope">
            <el-tag :type="chunkTypeColor(scope.row.chunk_type)" size="small">{{ scope.row.chunk_type }}</el-tag>
          </template>
        </el-table-column>
        <!-- Snippet text, omitted for too long, and click on the button to see the full text -->
        <el-table-column prop="content" label="Fragment content" show-overflow-tooltip />
        <el-table-column prop="char_count" label="Character count" width="90" />
        <!-- Page code from the [N.N.P.] tag in parsing text, used during question-and-answer sessions to mark source locations -->
        <el-table-column prop="page_no" label="Page number" width="80">
          <template #default="scope">{{ scope.row.page_no || '-' }}</template>
        </el-table-column>
        <el-table-column prop="vector_status" label="Embedding status" width="120" />
        <el-table-column label="Actions" width="140" fixed="right">
          <template #default="scope">
            <!-- Open the edit window and manually correct the twisted clips. -->
            <el-button type="primary" size="small" @click="handleEdit(scope.row)">Edit</el-button>
            <!-- id of current line only to delete -->
            <el-button type="danger" size="small" @click="del(scope.row.id)">Delete</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
    <!-- Data.total is 0-hour full page bar not rendered -->
    <div class="card" v-if="data.total">
      <!-- Update data.pageNum when switching page numbers and trigger load re-search -->
      <el-pagination
          v-model:current-page="data.pageNum"
          background
          layout="prev, pager, next"
          :page-size="data.pageSize"
          :total="data.total"
          @current-change="load"
      />
    </div>

    <!-- Snippet edits windows, only text is allowed to be corrected -->
    <el-dialog title="Edit fragment" v-model="data.formVisible" width="55%" destroy-on-close>
      <div style="margin-bottom: 8px; color: #999; font-size: 12px">
        After modification, this fragment needs to be re-vectorized. The vectorization status of the associated document will revert to pending.
      </div>
      <!-- Enter value into data.form.content, knowledge_chunk.content -->
      <el-input v-model="data.form.content" type="textarea" :rows="12"></el-input>
      <template #footer>
        <el-button @click="data.formVisible = false">Cancel</el-button>
        <el-button type="primary" @click="save">Confirm</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { reactive } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/utils/request.js'

const data = reactive({
  // Control Snippet Edit display of window hidden
  formVisible: false,
  // Only id and content fields for the segment objects bound in the window
  form: {},
  // Table data, filled with list by /knowlegeChunk/ selectPage
  tableData: [],
  // Lower drop options from /knowledBase/SelectAll
  kbOptions: [],
  // Dropdown options from /knowledgeDocument/selectPage as the knowledge base is switched
  docOptions: [],
  pageNum: 1,
  pageSize: 10,
  total: 0,
  // The value of the top knowledge base to pull a frame
  kbId: '',
  // Value of the frame below top document
  documentId: '',
  // The value of the frame down for the top segment type
  chunkType: '',
  // Value of the top content search box
  keyword: '',
  // _Other Organiser
  ids: []
})

const loadKbOptions = () => {
  // Knowledge base returned only to normal state
  request.get('/knowledgeBase/selectAll').then(res => {
    if (res.code === '200') {
      data.kbOptions = res.data || []
    }
  })
}

const loadDocOptions = () => {
  // To avoid listing documents from all libraries when no knowledge base is selected
  if (!data.kbId) {
    data.docOptions = []
    return
  }
  // Page_size for larger, file under a library to finish at once and frame down without page break
  request.get('/knowledgeDocument/selectPage', {
    params: { kb_id: data.kbId, page_num: 1, page_size: 200 }
  }).then(res => {
    if (res.code === '200') {
      data.docOptions = res.data?.list || []
    }
  })
}

const onKbChange = () => {
  // Changed the knowledge base. The original selected document is no longer part of this library.
  data.documentId = ''
  loadDocOptions()
  load()
}

const load = () => {
  // Page-by-page query interface with six parameters from page numbers, number of lines per page, knowledge base, document, session type, content keywords
  request.get('/knowledgeChunk/selectPage', {
    params: {
      page_num: data.pageNum,
      page_size: data.pageSize,
      kb_id: data.kbId || undefined,
      document_id: data.documentId || undefined,
      chunk_type: data.chunkType,
      keyword: data.keyword
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

const handleEdit = (row) => {
  // Only id and text are brought into the window, other fields are created by staggering and pages are not allowed to change
  data.form = { id: row.id, content: row.content }
  data.formVisible = true
}

const save = () => {
  // Submits the modified body text, and backends both this paragraph and the Quantified status of the files to be quantified
  request.put('/knowledgeChunk/update', data.form).then(res => {
    if (res.code === '200') {
      ElMessage.success('Saved')
      data.formVisible = false
      load()
    } else {
      // Failed to empty a business like this, backend returns the human conversation hint in msg
      ElMessage.error(res.msg)
    }
  })
}

const del = (id) => {
  // Play confirmation boxes before deleting, do not enter then, do not request
  ElMessageBox.confirm('Data cannot be recovered after deletion. Are you sure you want to delete?', 'Confirm deletion', { type: 'warning' }).then(() => {
    request.delete('/knowledgeChunk/delete/' + id).then(res => {
      if (res.code === '200') {
        ElMessage.success('Deleted')
        // After deleting the recheck list, the number of fragments on the document and knowledge bank has been restated from backend
        load()
      } else {
        // The parent won't be allowed to delete it alone. Backends will stop.
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
    request.delete('/knowledgeChunk/deleteBatch', { data: data.ids }).then(res => {
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

const chunkTypeColor = (type) => {
  // The parent only fills in blue for context, the sub-blocks for green and the normal pieces for default ash.
  if (type === 'Parent chunk') {
    return 'primary'
  }
  if (type === 'Child chunk') {
    return 'success'
  }
  return 'info'
}

const reset = () => {
  // Clear four search conditions and return to page one, check the full list again.
  data.kbId = ''
  data.documentId = ''
  data.chunkType = ''
  data.keyword = ''
  data.docOptions = []
  data.pageNum = 1
  load()
}

// Page loads first with the knowledge base drop data and then check the first session
loadKbOptions()
load()
</script>
