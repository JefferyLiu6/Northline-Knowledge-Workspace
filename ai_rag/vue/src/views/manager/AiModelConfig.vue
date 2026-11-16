<template>
  <div>
    <div class="card" style="margin-bottom: 5px">
      <!-- The profile name entered is stored in data.name as a blurry match for the name parameter -->
      <el-input v-model="data.name" style="width: 220px; margin-right: 10px" placeholder="Please enter configuration name to query"></el-input>
      <!-- The selected model type is stored in data. modelType as a precise match to the model_type parameter -->
      <el-select v-model="data.modelType" clearable style="width: 160px; margin-right: 10px" placeholder="Please select model type">
        <el-option label="Chat model" value="Chat model"></el-option>
        <el-option label="Embedding model" value="Embedding model"></el-option>
        <el-option label="Reranking model" value="Reranking model"></el-option>
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
      <!-- Data.tableData from a list returned by /aiModelConfig/ secretPage -->
      <el-table stripe :data="data.tableData">
        <el-table-column prop="name" label="Configuration name" width="180" />
        <!-- The three models are different colours, and you can see at first sight which ones are all configured. -->
        <el-table-column prop="model_type" label="Model type" width="110">
          <template #default="scope">
            <el-tag :type="modelTypeColor(scope.row.model_type)" size="small">{{ scope.row.model_type }}</el-tag>
          </template>
        </el-table-column>
        <!-- The protocol determines the code to be taken OpenAI compatible or DashScope original call path -->
        <el-table-column prop="protocol" label="Interface Protocol" width="130" />
        <el-table-column prop="model_name" label="Model Name" width="170" />
        <el-table-column prop="base_url" label="API Endpoint" show-overflow-tooltip />
        <!-- Key de-esensitize from backend, return only 4 bits to end of header -->
        <el-table-column prop="api_key" label="API Key" width="170">
          <template #default="scope">{{ scope.row.api_key || 'Not Filled' }}</template>
        </el-table-column>
        <!-- Vector dimensions only have value in vector models and must match PGVector's scale dimensions -->
        <el-table-column prop="dimension" label="Dimension" width="80">
          <template #default="scope">{{ scope.row.dimension || '-' }}</template>
        </el-table-column>
        <!-- Only one is enabled under the same type, only the code is valid. -->
        <el-table-column prop="enabled" label="Enabled" width="80">
          <template #default="scope">
            <el-tag :type="scope.row.enabled === 'Yes' ? 'success' : 'info'" size="small">{{ scope.row.enabled }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="Actions" width="200" fixed="right">
          <template #default="scope">
            <!-- A true simulation model of the configurations saved in the library, confirming that addresses, keys, model names are correct. -->
            <el-button type="success" size="small" :loading="data.testingId === scope.row.id" @click="testConnection(scope.row)">Test</el-button>
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
    <el-dialog title="AI Model Configuration" v-model="data.formVisible" width="50%" destroy-on-close>
      <el-form ref="formRef" :model="data.form" :rules="data.rules" label-width="110px" style="padding: 20px">
        <el-form-item label="Configuration name" prop="name">
          <el-input v-model="data.form.name" placeholder="Please enter the configuration name"></el-input>
        </el-form-item>
        <!-- When you select a vector model, there's an extra vector dimension below. -->
        <el-form-item label="Model type" prop="model_type">
          <el-select v-model="data.form.model_type" style="width: 100%" @change="onModelTypeChange">
            <el-option label="Chat model" value="Chat model"></el-option>
            <el-option label="Embedding model" value="Embedding model"></el-option>
            <el-option label="Reranking model" value="Reranking model"></el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="Interface Protocol" prop="protocol">
          <el-select v-model="data.form.protocol" style="width: 100%">
            <el-option v-if="data.form.model_type === 'Reranking model'" label="Ollama chat reranking" value="Ollama chat reranking"></el-option>
            <el-option label="OpenAI compatible" value="OpenAI compatible"></el-option>
            <el-option label="Native DashScope" value="Native DashScope"></el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="Service Provider">
          <el-input v-model="data.form.provider" placeholder="Example: Ollama"></el-input>
        </el-form-item>
        <el-form-item label="API Endpoint" prop="base_url">
          <el-input v-model="data.form.base_url" placeholder="Example: http://127.0.0.1:11434/v1"></el-input>
        </el-form-item>
        <!-- This displays desensitivity at the time of editing. If you do not re-enter, leave the original key unchanged.
             Show-password allows the key to be displayed at all times as a dot, and the new key that is pasted will not be exposed explicitly on the screen.
             Toggles the small eye to the right side of the box when checking -->
        <el-form-item label="API Key">
          <el-input show-password v-model="data.form.api_key" placeholder="Leave blank to keep the original API key unchanged"></el-input>
        </el-form-item>
        <el-form-item label="Model Name" prop="model_name">
          <el-input v-model="data.form.model_name" placeholder="Example: llama3.1:8b"></el-input>
        </el-form-item>
        <!-- Only vector models need dimensions and must be consistent with the Vector(N) when PGVector is set -->
        <el-form-item v-if="data.form.model_type === 'Embedding model'" label="Vector Dimension" prop="dimension">
          <el-input-number v-model="data.form.dimension" :min="64" :max="4096" :step="64" style="width: 100%"></el-input-number>
        </el-form-item>
        <!-- Set as enabled, other configurations of the same type will be automatically disabled from backend -->
        <el-form-item label="Enabled">
          <el-radio-group v-model="data.form.enabled">
            <el-radio value="Yes">Yes</el-radio>
            <el-radio value="No">No</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="Remarks">
          <el-input v-model="data.form.remark" type="textarea" :rows="2" placeholder="Description of where this configuration is used"></el-input>
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
import { reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/utils/request.js'

const data = reactive({
  // Controls the display of the configured window, adds and edits the same window
  formVisible: false,
  // The objects bound by each box in the window. Id for editing, no id for adding
  form: {},
  // Table data, filled with list from /aiModelConfig/ selextPage
  tableData: [],
  pageNum: 1,
  pageSize: 10,
  total: 0,
  // Value of top configuration name search box
  name: '',
  // The value to pull the frame down of the top model type
  modelType: '',
  // id, which is used to spin the corresponding buttons.
  testingId: 0,
  // Frontend verification rules for window popping
  rules: {
    name: [
      { required: true, message: 'Please enter the configuration name', trigger: 'blur' }
    ],
    model_type: [
      { required: true, message: 'Please select model type', trigger: 'change' }
    ],
    protocol: [
      { required: true, message: 'Please select an interface protocol', trigger: 'change' }
    ],
    base_url: [
      { required: true, message: 'Please enter the interface address', trigger: 'blur' }
    ],
    model_name: [
      { required: true, message: 'Please enter the model name', trigger: 'blur' }
    ]
  }
})

// FormRef bind el-form in the window, trigger whole table check when point is determined
const formRef = ref()

const load = () => {
  // Page-by-page query interface with four parameters from page numbers, number of lines per page, name search box, type drop frame
  request.get('/aiModelConfig/selectPage', {
    params: {
      page_num: data.pageNum,
      page_size: data.pageSize,
      name: data.name,
      model_type: data.modelType
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
  // Adds a template to be configured by default according to the dialogue model, and changes the name of the model can be used
  data.form = {
    model_type: 'Chat model',
    protocol: 'OpenAI compatible',
    provider: 'Ollama',
    base_url: 'http://127.0.0.1:11434/v1',
    enabled: 'No'
  }
  data.formVisible = true
}

const handleEdit = (row) => {
  // (b) Deep copy of the current line to avoid direct modification of the objects in the tabledata leading to a change in the window;
  // The key field is brought in a de-sensitivity string, and if you don't re-enter it the back end will keep the original key.
  data.form = JSON.parse(JSON.stringify(row))
  data.formVisible = true
}

const onModelTypeChange = (type) => {
  data.form.protocol = type === 'Reranking model' ? 'Ollama chat reranking' : 'OpenAI compatible'
  data.form.base_url = 'http://127.0.0.1:11434/v1'
}

const save = () => {
  formRef.value.validate(valid => {
    // Do not request to fill in if you do not. Direct red word hint under form
    if (!valid) {
      return
    }
    // Data.form.id exists to show that the current window is editing mode, and backend updates the original records of ai_model_config
    // Data.form.id does not exist as an explanation for adding a new mode, and the backend inserts a new configuration record
    const action = data.form.id
        ? request.put('/aiModelConfig/update', data.form)
        : request.post('/aiModelConfig/add', data.form)
    action.then(res => {
      if (res.code === '200') {
        ElMessage.success('Saved')
        // Close the window and recheck the list so that the table shows the latest data
        data.formVisible = false
        load()
      } else {
        // Repeat name, vector model not filled dimensions failed, backend returns human voice tips in msg
        ElMessage.error(res.msg)
      }
    })
  })
}

const testConnection = (row) => {
  // Write down which line you're testing. Do not repeat the point during the spin of the button.
  data.testingId = row.id
  request.post('/aiModelConfig/test/' + row.id).then(res => {
    if (res.code === '200') {
      // Res.data is a success story of backend return, for example, " vector model connection normal, output 1024 dimensions."
      ElMessage.success(res.data)
    } else {
      // The key is invalid, the model name does not exist, the dimensions don't match. Backends are translated into human words.
      ElMessage.error(res.msg)
    }
  }).finally(() => {
    data.testingId = 0
  })
}

const del = (id) => {
  // Play confirmation boxes before deleting, do not enter then, do not request
  ElMessageBox.confirm('Data cannot be recovered after deletion. Are you sure you want to delete?', 'Confirm deletion', { type: 'warning' }).then(() => {
    request.delete('/aiModelConfig/delete/' + id).then(res => {
      if (res.code === '200') {
        ElMessage.success('Deleted')
        load()
      } else {
        // Enabled configuration does not allow deletion, backend stops
        ElMessage.error(res.msg)
      }
    })
  })
}

const modelTypeColor = (type) => {
  // Dialogue model green, vector model blue, reordered model orange
  if (type === 'Chat model') {
    return 'success'
  }
  if (type === 'Embedding model') {
    return 'primary'
  }
  return 'warning'
}

const reset = () => {
  // Clear two search conditions and return to page one, check the full list again
  data.name = ''
  data.modelType = ''
  data.pageNum = 1
  load()
}

// Check the page once it is loaded. You can see the first page when you enter the page.
load()
</script>
