<template>
  <div>
    <div class="card" style="margin-bottom: 5px">
      <!-- The template name entered is stored in data.keyword as a keyword parameter -->
      <el-input v-model="data.keyword" style="width: 220px; margin-right: 10px" placeholder="Please enter template name to query"></el-input>
      <!-- The selected scene is stored in data.screen, matching precisely as scene parameters -->
      <el-select v-model="data.scene" clearable style="width: 180px; margin-right: 10px" placeholder="Please select use case">
        <el-option label="Answer generation" value="Answer generation"></el-option>
        <el-option label="Query rewrite" value="Query rewrite"></el-option>
        <el-option label="Agentic RAG" value="Agentic RAG"></el-option>
        <el-option label="Dataset construction" value="Dataset construction"></el-option>
      </el-select>
      <!-- Retrieve with two current search conditions -->
      <el-button type="info" plain @click="load">Query</el-button>
      <!-- Clear search conditions and return to page one. -->
      <el-button type="warning" plain style="margin: 0 10px" @click="reset">Reset</el-button>
    </div>
    <div class="card" style="margin-bottom: 5px">
      <!-- Open the blank window and go to add process -->
      <el-button type="primary" plain @click="handleAdd">Add new</el-button>
    </div>

    <div class="card" style="margin-bottom: 5px">
      <!-- data.tableData from /promptTemplate/ secretPage returned list -->
      <el-table stripe :data="data.tableData">
        <!-- Code click code to take template, full table only -->
        <el-table-column prop="code" label="Template code" width="200" />
        <el-table-column prop="name" label="Template name" width="160" />
        <el-table-column prop="scene" label="Use case" width="130" />
        <!-- variables automatically extracted from content by backend without manual maintenance -->
        <el-table-column prop="variables" label="Variable" width="160" show-overflow-tooltip />
        <el-table-column prop="content" label="Template content" show-overflow-tooltip />
        <!-- The deactivated template can't get it. The link will just make a mistake, not sneak up on the old one. -->
        <el-table-column prop="enabled" label="Enabled" width="80">
          <template #default="scope">
            <el-tag :type="scope.row.enabled === 'Yes' ? 'success' : 'info'" size="small">{{ scope.row.enabled }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="Actions" width="200" fixed="right">
          <template #default="scope">
            <!-- Fill in variable values to see the full text of the true distribution model -->
            <el-button type="success" size="small" @click="openPreview(scope.row)">Preview</el-button>
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
    <el-dialog title="Prompt Template" v-model="data.formVisible" width="55%" destroy-on-close>
      <el-form ref="formRef" :model="data.form" :rules="data.rules" label-width="100px" style="padding: 20px">
        <!-- Encoding is the basis for a code extraction template, which will be modified when you edit an existing template to make it impossible for the corresponding function to take the template. -->
        <el-form-item label="Template code" prop="code">
          <el-input v-model="data.form.code" placeholder="Example: RAG_ANSWER"></el-input>
        </el-form-item>
        <el-form-item label="Template name" prop="name">
          <el-input v-model="data.form.name" placeholder="Please enter a template name"></el-input>
        </el-form-item>
        <el-form-item label="Use case">
          <el-select v-model="data.form.scene" clearable style="width: 100%" placeholder="Please select use case">
            <el-option label="Answer generation" value="Answer generation"></el-option>
            <el-option label="Query rewrite" value="Query rewrite"></el-option>
            <el-option label="Agentic RAG" value="Agentic RAG"></el-option>
            <el-option label="Dataset construction" value="Dataset construction"></el-option>
          </el-select>
        </el-form-item>
        <!-- Positioning variables in big brackets, automatically extracts a list of variables from the backend when saving -->
        <el-form-item label="Template content" prop="content">
          <el-input v-model="data.form.content" type="textarea" :rows="10" placeholder="Write variable with curly braces, example: Materials: {context}"></el-input>
        </el-form-item>
        <el-form-item label="Enabled">
          <el-radio-group v-model="data.form.enabled">
            <el-radio value="Yes">Yes</el-radio>
            <el-radio value="No">No</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="Remarks">
          <el-input v-model="data.form.remark" type="textarea" :rows="2" placeholder="Explain which stage this template is used for"></el-input>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="data.formVisible = false">Cancel</el-button>
        <el-button type="primary" @click="save">Confirm</el-button>
      </template>
    </el-dialog>

    <!-- Preview window: fill out a value for each variable in the template to see the full text after rendering -->
    <el-dialog title="Preview Prompt" v-model="data.previewVisible" width="55%" destroy-on-close>
      <el-form label-width="100px" style="padding: 0 20px">
        <!-- The list of variables is derived from the template's variables column, generating one input box each -->
        <el-form-item v-for="name in data.previewNames" :key="name" :label="name">
          <el-input v-model="data.previewValues[name]" :placeholder="'Please enter ' + name + ' value'"></el-input>
        </el-form-item>
      </el-form>
      <el-button type="primary" style="margin: 0 20px 10px" @click="doPreview">Generate preview</el-button>
      <!-- White-space keep the line break in the template. Seeing the layout is the typesetting to be sent to the model. -->
      <div v-if="data.previewText" style="margin: 0 20px; max-height: 360px; overflow: auto; background: #f7f7f7; padding: 12px; white-space: pre-wrap; font-size: 13px">{{ data.previewText }}</div>
      <template #footer>
        <el-button @click="data.previewVisible = false">Close</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/utils/request.js'

const data = reactive({
  // Controls the display of template windows hidden, adds and edits the same window
  formVisible: false,
  // The objects bound by each box in the window. Id for editing, no id for adding
  form: {},
  // Table data, filled by list returned /promptTemplate/ selectPage
  tableData: [],
  pageNum: 1,
  pageSize: 10,
  total: 0,
  // Value of the top template name search box
  keyword: '',
  // The value of the frame from top to bottom
  scene: '',
  // Controls the display and hiding of preview windows
  previewVisible: false,
  // Template id for the current preview
  previewId: 0,
  // The list of variables required by the current template, from the variables column
  previewNames: [],
  // Values filled in by variable with variable name
  previewValues: {},
  // Full text after rendering
  previewText: '',
  // Frontend verification rules for window popping
  rules: {
    code: [
      { required: true, message: 'Please enter the template encoding.', trigger: 'blur' }
    ],
    name: [
      { required: true, message: 'Please enter a template name', trigger: 'blur' }
    ],
    content: [
      { required: true, message: 'Please enter the template contents', trigger: 'blur' }
    ]
  }
})

// FormRef bind el-form in the window, trigger whole table check when point is determined
const formRef = ref()

const load = () => {
  // Page-by-page query interface with four parameters from page numbers, number of lines per page, name search box, scene pull
  request.get('/promptTemplate/selectPage', {
    params: {
      page_num: data.pageNum,
      page_size: data.pageSize,
      keyword: data.keyword,
      scene: data.scene
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
  // Enable by default when adding, no id, save will walk the new interface
  data.form = { enabled: 'Yes' }
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
    // Do not request to fill in if you do not. Direct red word hint under form
    if (!valid) {
      return
    }
    // Data.form.id exists to explain that the current window is edit mode, and backend updates the original log of the prompt_temlate table by pressing id
    // Data.form.id There is no indication that this is a new mode, and a new template record will be inserted at the back end
    const action = data.form.id
        ? request.put('/promptTemplate/update', data.form)
        : request.post('/promptTemplate/add', data.form)
    action.then(res => {
      if (res.code === '200') {
        ElMessage.success('Saved')
        // Close the window and recheck the list. The variable bar shows a list of variables that have just been extracted from the back end
        data.formVisible = false
        load()
      } else {
        // Failed to encode duplicates, empty contents and backend returns human voice tips in msg
        ElMessage.error(res.msg)
      }
    })
  })
}

const openPreview = (row) => {
  // The list of variables exists in the variables column, comma separated, and then separates it into an input box for each variable
  data.previewId = row.id
  data.previewNames = row.variables ? row.variables.split(',').filter(item => item) : []
  data.previewValues = {}
  data.previewText = ''
  data.previewVisible = true
}

const doPreview = () => {
  // Backend encodes content by template, replaces variable values and returns the text that really sends to the model
  request.post('/promptTemplate/preview', { id: data.previewId, values: data.previewValues }).then(res => {
    if (res.code === '200') {
      data.previewText = res.data
    } else {
      // The variable does not have a full-time backend that clearly indicates which is missing.
      ElMessage.error(res.msg)
    }
  })
}

const del = (id) => {
  // Play confirmation boxes before deleting, do not enter then, do not request
  ElMessageBox.confirm('Data cannot be recovered after deletion. Are you sure you want to delete?', 'Confirm deletion', { type: 'warning' }).then(() => {
    request.delete('/promptTemplate/delete/' + id).then(res => {
      if (res.code === '200') {
        ElMessage.success('Deleted')
        load()
      } else {
        ElMessage.error(res.msg)
      }
    })
  })
}

const reset = () => {
  // Clear two search conditions and return to page one, check the full list again
  data.keyword = ''
  data.scene = ''
  data.pageNum = 1
  load()
}

// Check the page once it is loaded. You can see the first page when you enter the page.
load()
</script>
