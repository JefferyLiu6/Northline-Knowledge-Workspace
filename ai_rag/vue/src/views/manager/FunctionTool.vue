<template>
  <div>
    <div class="card" style="margin-bottom: 5px">
      <!-- Enter a tool name to store data.keyword as a keyword parameter for blurry matching -->
      <el-input v-model="data.keyword" style="width: 220px; margin-right: 10px" placeholder="Please enter tool name to query"></el-input>
      <el-select v-model="data.enabled" clearable style="width: 140px; margin-right: 10px" placeholder="Enabled Status">
        <el-option label="Enabled" value="Yes"></el-option>
        <el-option label="Disabled" value="No"></el-option>
      </el-select>
      <el-button type="info" plain @click="load">Query</el-button>
      <el-button type="warning" plain style="margin: 0 10px" @click="reset">Reset</el-button>
    </div>
    <div class="card" style="margin-bottom: 5px">
      <el-button type="primary" plain @click="handleAdd">Add new</el-button>
      <!-- See if you can really send a tool definition to the model. -->
      <el-button type="success" plain @click="viewDefinitions">View model received tool definition</el-button>
      <!-- Number of calls by tool and success rate -->
      <el-button type="warning" plain @click="viewSummary">Call Statistics</el-button>
    </div>

    <div class="card" style="margin-bottom: 5px">
      <!-- Data.tableData from list returned by /fundactionTool/ selectPage -->
      <el-table stripe :data="data.tableData">
        <el-table-column prop="tool_code" label="Tool Code" width="180" />
        <el-table-column prop="tool_name" label="Tool Name" width="150" />
        <!-- This description will be sent to the model as it is, which will determine when this tool should be adjusted. -->
        <el-table-column prop="description" label="Tool Description (will be sent to the model)" show-overflow-tooltip />
        <!-- It's got tools in the table, but it doesn't work. The model can't get them. -->
        <el-table-column prop="implemented" label="Code Implementation" width="100">
          <template #default="scope">
            <el-tag :type="scope.row.implemented ? 'success' : 'danger'" size="small">
              {{ scope.row.implemented ? 'Implemented' : 'Not Implemented' }}
            </el-tag>
          </template>
        </el-table-column>
        <!-- Real Switch: The next time the model is implemented, it won't get the tool. -->
        <el-table-column prop="enabled" label="Enabled" width="100">
          <template #default="scope">
            <el-switch
                :model-value="scope.row.enabled === 'Yes'"
                @change="toggle(scope.row, $event)"
            />
          </template>
        </el-table-column>
        <el-table-column prop="sort" label="Sorting" width="80" />
        <el-table-column label="Actions" width="140" fixed="right">
          <template #default="scope">
            <el-button type="primary" size="small" @click="handleEdit(scope.row)">Edit</el-button>
            <el-button type="danger" size="small" @click="del(scope.row.id)">Delete</el-button>
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
          @current-change="load"
      />
    </div>

    <!-- Add and edit this window -->
    <el-dialog title="Function Tool" v-model="data.formVisible" width="50%" destroy-on-close>
      <el-form ref="formRef" :model="data.form" :rules="data.rules" label-width="110px" style="padding: 20px">
        <!-- Encoding must match the name of ai/tools. py to achieve function -->
        <el-form-item label="Tool Code" prop="tool_code">
          <el-input v-model="data.form.tool_code" placeholder="Must be consistent with the function name in ai/tools.py"></el-input>
        </el-form-item>
        <el-form-item label="Tool Name" prop="tool_name">
          <el-input v-model="data.form.tool_name" placeholder="Name for humans"></el-input>
        </el-form-item>
        <!-- This text will be sent to the model in its original form, and the better it is used. -->
        <el-form-item label="Tool Description" prop="description">
          <el-input v-model="data.form.description" type="textarea" :rows="3" placeholder="Write clearly what this tool can do, when it should be used, this will be sent to the model as is"></el-input>
        </el-form-item>
        <!-- Inscription JSON, the key is a parameter name and the value is what this parameter means -->
        <el-form-item label="Input Parameter Description">
          <el-input v-model="data.form.input_schema" type="textarea" :rows="3" placeholder='{"query":"Search query","kb_id":"Knowledge base ID"}'></el-input>
        </el-form-item>
        <el-form-item label="Sorting">
          <el-input-number v-model="data.form.sort" :min="0" :max="999" style="width: 100%"></el-input-number>
        </el-form-item>
        <el-form-item label="Enabled">
          <el-radio-group v-model="data.form.enabled">
            <el-radio value="Yes">Yes</el-radio>
            <el-radio value="No">No</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="data.formVisible = false">Cancel</el-button>
        <el-button type="primary" @click="save">Confirm</el-button>
      </template>
    </el-dialog>

    <!-- Tool Definition Preview: This is what the model really gets -->
    <el-dialog title="Tool Definition Received by the Model" v-model="data.definitionVisible" width="60%" destroy-on-close>
      <div style="max-height: 460px; overflow: auto; background: #f7f7f7; padding: 12px; white-space: pre-wrap; font-size: 13px">{{ data.definitionText }}</div>
      <template #footer>
        <el-button @click="data.definitionVisible = false">Close</el-button>
      </template>
    </el-dialog>

    <!-- Call statistics: how many times each tool has been adjusted and failed -->
    <el-dialog title="Tool Call Statistics" v-model="data.summaryVisible" width="55%" destroy-on-close>
      <el-table stripe :data="data.summary" size="small">
        <el-table-column prop="tool_name" label="Tool" width="160" />
        <el-table-column prop="enabled" label="Enabled" width="80" />
        <el-table-column prop="total" label="Call Count" width="110" />
        <el-table-column prop="failed" label="Failure Count" width="110" />
        <el-table-column prop="success_rate" label="Success Rate (%)">
          <template #default="scope">{{ scope.row.success_rate ?? '—' }}</template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="data.summaryVisible = false">Close</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/utils/request.js'

const data = reactive({
  formVisible: false,
  form: {},
  tableData: [],
  pageNum: 1,
  pageSize: 10,
  total: 0,
  // Value of the top tool name search box
  keyword: '',
  // The value to pull the frame under top enabled state
  enabled: '',
  // Control tool definition preview window
  definitionVisible: false,
  definitionText: '',
  // Control the call to the statistical window
  summaryVisible: false,
  summary: [],
  rules: {
    tool_code: [
      { required: true, message: 'Please enter tool encoding', trigger: 'blur' }
    ],
    tool_name: [
      { required: true, message: 'Please enter the tool name', trigger: 'blur' }
    ],
    description: [
      { required: true, message: 'Please enter tool description', trigger: 'blur' }
    ]
  }
})

const formRef = ref()

const load = () => {
  request.get('/functionTool/selectPage', {
    params: {
      page_num: data.pageNum,
      page_size: data.pageSize,
      keyword: data.keyword,
      enabled: data.enabled
    }
  }).then(res => {
    if (res.code === '200') {
      data.tableData = res.data?.list || []
      data.total = res.data?.total || 0
    } else {
      ElMessage.error(res.msg)
    }
  })
}

const handleAdd = () => {
  // Enabled by default when adding, sorting last
  data.form = { enabled: 'Yes', sort: 0 }
  data.formVisible = true
}

const handleEdit = (row) => {
  // Deep copy the current line, avoid direct changes to the objects in the tableData that lead to a change in the window.
  data.form = JSON.parse(JSON.stringify(row))
  data.formVisible = true
}

const save = () => {
  formRef.value.validate(valid => {
    if (!valid) {
      return
    }
    const action = data.form.id
        ? request.put('/functionTool/update', data.form)
        : request.post('/functionTool/add', data.form)
    action.then(res => {
      if (res.code === '200') {
        ElMessage.success('Saved')
        data.formVisible = false
        load()
      } else {
        // Encoding duplicates, description of these operations as empty failed and backend returns the human voice hint in msg
        ElMessage.error(res.msg)
      }
    })
  })
}

const toggle = (row, checked) => {
  // As soon as the switch is changed, the list of tools obtained by the next execution of the model will change.
  request.put('/functionTool/toggle/' + row.id, null, {
    params: { enabled: checked ? 'Yes' : 'No' }
  }).then(res => {
    if (res.code === '200') {
      ElMessage.success(checked ? 'Enabled' : 'Disabled')
      load()
    } else {
      ElMessage.error(res.msg)
      load()
    }
  })
}

const del = (id) => {
  ElMessageBox.confirm('Data cannot be recovered after deletion. Are you sure you want to delete?', 'Confirm deletion', { type: 'warning' }).then(() => {
    request.delete('/functionTool/delete/' + id).then(res => {
      if (res.code === '200') {
        ElMessage.success('Deleted')
        load()
      } else {
        // The tools in the code are not allowed to be deleted. Backend stops.
        ElMessage.error(res.msg)
      }
    })
  })
}

const viewDefinitions = () => {
  // It's the part where the model is actually sent.
  request.get('/functionTool/definitions').then(res => {
    if (res.code === '200') {
      data.definitionText = JSON.stringify(res.data, null, 2)
      data.definitionVisible = true
    } else {
      ElMessage.error(res.msg)
    }
  })
}

const viewSummary = () => {
  request.get('/functionTool/logSummary').then(res => {
    if (res.code === '200') {
      data.summary = res.data || []
      data.summaryVisible = true
    } else {
      ElMessage.error(res.msg)
    }
  })
}

const reset = () => {
  data.keyword = ''
  data.enabled = ''
  data.pageNum = 1
  load()
}

// Check the page once you load it.
load()
</script>
