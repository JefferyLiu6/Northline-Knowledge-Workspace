<template>
  <div>
    <div class="card" style="margin-bottom: 5px">
      <!-- The name entered is stored in data.name, and the name is passed back to the back as a nebula for point queries -->
      <el-input v-model="data.name" style="width: 240px; margin-right: 10px" placeholder="Please enter knowledge base name to query"></el-input>
      <!-- The selected state is stored in data. status as an accurate match for the status parameter to the backend -->
      <el-select v-model="data.status" clearable style="width: 180px; margin-right: 10px" placeholder="Please select status">
        <el-option label="Active" value="Active"></el-option>
        <el-option label="Disabled" value="Disabled"></el-option>
      </el-select>
      <!-- Retrieve with two current search conditions -->
      <el-button type="info" plain @click="load">Query</el-button>
      <!-- Clear search conditions and return to page one. -->
      <el-button type="warning" plain style="margin: 0 10px" @click="reset">Reset</el-button>
    </div>
    <div class="card" style="margin-bottom: 5px">
      <!-- Open the blank window and go to add process -->
      <el-button type="primary" plain @click="handleAdd">Add new</el-button>
      <!-- Remove the selected multilines from the table -->
      <el-button type="danger" plain @click="delBatch">Batch Delete</el-button>
    </div>

    <div class="card" style="margin-bottom: 5px">
      <!-- data.tableData from a list returned by /knowledgeBase/ selectPage; save the selected line id in data.ids when ticking changes -->
      <el-table stripe :data="data.tableData" @selection-change="handleSelectionChange">
        <!-- Multiple rows, delete use with batch -->
        <el-table-column type="selection" width="55" />
        <el-table-column prop="name" label="Knowledge Base Name" width="200" />
        <!-- Show-overlow-tooltip to leave too long a description omitted and the mouse hovered over the full text -->
        <el-table-column prop="description" label="Description" show-overflow-tooltip />
        <!-- Document_count to add and delete from the document in chapter 06, here only read displays -->
        <el-table-column prop="document_count" label="Document Count" width="90" />
        <!-- Chunk_count is maintained by a snippet cut in chapter 09, where only displays are read -->
        <el-table-column prop="chunk_count" label="Chunk count" width="90" />
        <!-- Normal display of green tabs, deactivate display of grey tags -->
        <el-table-column prop="status" label="Status" width="90">
          <template #default="scope">
            <el-tag :type="scope.row.status === 'Active' ? 'success' : 'info'">{{ scope.row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="create_time" label="Creation Time" width="180" />
        <el-table-column label="Actions" width="220" fixed="right">
          <template #default="scope">
            <!-- Let's see if this library can start with a question and answer. -->
            <el-button type="success" size="small" @click="viewVectorStatus(scope.row)">Vector Status</el-button>
            <!-- Bring the current line data into the window and go through the editing process. -->
            <el-button type="primary" circle :icon="Edit" @click="handleEdit(scope.row)"></el-button>
            <!-- id of current line only to delete -->
            <el-button type="danger" circle :icon="Delete" @click="del(scope.row.id)"></el-button>
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

    <!-- Add and edit this window, destroy-on-close to make sure that every opening is a brand new form -->
    <el-dialog title="Knowledge Base Information" v-model="data.formVisible" width="40%" destroy-on-close>
      <el-form ref="formRef" :model="data.form" :rules="data.rules" label-width="100px" style="padding: 20px">
        <!-- Enter the value into data.form.name, which will be checked on backend when saving -->
        <el-form-item label="Knowledge Base Name" prop="name">
          <el-input v-model="data.form.name" placeholder="Please enter the name of the knowledge base"></el-input>
        </el-form-item>
        <!-- Multi-line text that shows what's in this library. Showing is not part of the search. -->
        <el-form-item label="Description">
          <el-input v-model="data.form.description" type="textarea" :rows="3" placeholder="Enter knowledge base description"></el-input>
        </el-form-item>
        <!-- This library does not participate in question-and-answer search after deactivated, adding by default to normal -->
        <el-form-item label="Status">
          <el-radio-group v-model="data.form.status">
            <el-radio value="Active">Active</el-radio>
            <el-radio value="Disabled">Disabled</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="data.formVisible = false">Cancel</el-button>
        <el-button type="primary" @click="save">Confirm</el-button>
      </template>
    </el-dialog>

    <!-- Vector status window, data from /vectorize/status/{kb_id} -->
    <el-dialog title="Embedding status" v-model="data.vectorVisible" width="40%" destroy-on-close>
      <el-form label-width="140px" style="padding: 10px 20px">
        <el-form-item label="Knowledge base">
          <span>{{ data.vectorStatus.kb_name }}</span>
        </el-form-item>
        <!-- No direct change of model is permitted after the tie. -->
        <el-form-item label="Bound vector model">
          <span>{{ data.vectorStatus.embedding_model || 'Not bound yet' }}</span>
        </el-form-item>
        <!-- There should be a number of fragments in vectors, not the parent block. -->
        <el-form-item label="Pending retrieval fragment count">
          <span>{{ data.vectorStatus.searchable_count }}</span>
        </el-form-item>
        <!-- Snippet table marked as number of completed -->
        <el-form-item label="Completed vectorization">
          <span>{{ data.vectorStatus.done_count }}</span>
        </el-form-item>
        <!-- The actual number of bars in the vector library, which does not match the above suggests that there is no synchronization between the two sides. -->
        <el-form-item label="Actual number of entries in vector database">
          <span>{{ data.vectorStatus.vector_count }}</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <!-- Clearing and untying of library vectors to replace vector models -->
        <el-button type="danger" plain @click="clearKbVectors">Clear vector and unbind model</el-button>
        <el-button @click="data.vectorVisible = false">Close</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { Delete, Edit } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/utils/request.js'

const data = reactive({
  // Control the display of the knowledge base information window hidden, add and edit the same window for reuse
  formVisible: false,
  // The objects bound by each box in the window. Id for editing, no id for adding
  form: {},
  // Table data, filled with list by /knowledgeBase/ selectPage
  tableData: [],
  // Current page number, update and retrace the page code when the component is changed
  pageNum: 1,
  // Number of articles per page, fixed at 10
  pageSize: 10,
  // Total bar number, decide to show pages by page line, 0 hours the whole strip is not rendered
  total: 0,
  // The value of the top name search box to send to backends as query parameter
  name: '',
  // The value of the frame under top state, which is accurately matched as a query parameter to the back end
  status: '',
  // _Other Organiser
  ids: [],
  // Hide display of vector-based windows
  vectorVisible: false,
  // Quantified profile filled by /vectorize/status/{kb_id}
  vectorStatus: {},
  // The front end verification rules for windows, the name must be filled
  rules: {
    name: [
      { required: true, message: 'Please enter the name of the knowledge base', trigger: 'blur' }
    ]
  }
})

// FormRef bind el-form in the window, trigger whole table check when point is determined
const formRef = ref()

const load = () => {
  // Page-by-page query interface with four parameters from page numbers, number of lines per page, name search box, status pull
  request.get('/knowledgeBase/selectPage', {
    params: {
      page_num: data.pageNum,
      page_size: data.pageSize,
      name: data.name,
      status: data.status
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

const handleAdd = () => {
  // Gives a clean default value when adding, and the new interface is used when no id, save;
  // The status default is normal and the default values for backend add are consistent
  data.form = { status: 'Active' }
  data.formVisible = true
}

const handleEdit = (row) => {
  // (b) Deep copy of the current line to avoid direct modification of the objects in the tabledata leading to a change in the window;
  // id, save will update the interface when a copy comes in.
  data.form = JSON.parse(JSON.stringify(row))
  data.formVisible = true
}

const save = () => {
  formRef.value.validate(valid => {
    // Do not send a request if the name is not filled out. Enter a direct red hint below the box
    if (!valid) {
      return
    }
    // Data.form.id exists to explain that the current window is editing mode, and backend updates the original records of the statement by pressing id
    // Data.form.id There is no indication that it is a new mode, and the backend will insert a new knowledge base record
    const action = data.form.id
        ? request.put('/knowledgeBase/update', data.form)
        : request.post('/knowledgeBase/add', data.form)
    action.then(res => {
      if (res.code === '200') {
        ElMessage.success('Saved')
        // Close the window and recheck the list so that the table shows the latest data
        data.formVisible = false
        load()
      } else {
        // Repeat name, state parameter error failed. Backend returns human message hint in msg
        ElMessage.error(res.msg)
      }
    })
  })
}

const del = (id) => {
  // Play confirmation boxes before deleting, do not enter then, do not request
  ElMessageBox.confirm('Data cannot be recovered after deletion. Are you sure you want to delete?', 'Confirm deletion', { type: 'warning' }).then(() => {
    // id is embedded on the path, and backends receive with path parameters
    request.delete('/knowledgeBase/delete/' + id).then(res => {
      if (res.code === '200') {
        ElMessage.success('Deleted')
        // Delete recheck list and remove deleted lines from table
        load()
      } else {
        // Backend stops when there's a document under the library. Hint in msg
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
    request.delete('/knowledgeBase/deleteBatch', { data: data.ids }).then(res => {
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

const viewVectorStatus = (row) => {
  // Three figures taken together: how many should be marked, how much the tags have been done and what's actually in the vector library
  request.get('/vectorize/status/' + row.id).then(res => {
    if (res.code === '200') {
      data.vectorStatus = res.data
      data.vectorVisible = true
    } else {
      // When the library is not connected, the backend gives a clear hint.
      ElMessage.error(res.msg)
    }
  })
}

const clearKbVectors = () => {
  // Clearing the entire library vector will untie the vector model and can then be redone with another model.
  ElMessageBox.confirm('Clearing will require the entire knowledge base to be re-vectorized. Confirm to continue?', 'Clear confirmation', { type: 'warning' }).then(() => {
    request.delete('/vectorize/knowledgeBase/' + data.vectorStatus.kb_id).then(res => {
      if (res.code === '200') {
        // Res.data has cleared out a few vectors.
        ElMessage.success(res.data)
        data.vectorVisible = false
        load()
      } else {
        ElMessage.error(res.msg)
      }
    })
  })
}

const reset = () => {
  // Clear two search conditions and return to page one, check the full list again
  data.name = ''
  data.status = ''
  data.pageNum = 1
  load()
}

// Check the page once it is loaded. You can see the first page when you enter the page.
load()
</script>
