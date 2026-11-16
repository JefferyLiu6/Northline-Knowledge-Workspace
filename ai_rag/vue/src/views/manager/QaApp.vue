<template>
  <div>
    <div class="card" style="margin-bottom: 5px">
      <el-input v-model="data.name" style="width: 220px; margin-right: 10px" placeholder="Please enter application name to query"></el-input>
      <el-select v-model="data.status" clearable style="width: 140px; margin-right: 10px" placeholder="Status">
        <el-option label="Active" value="Active"></el-option>
        <el-option label="Disabled" value="Disabled"></el-option>
      </el-select>
      <el-button type="info" plain @click="load">Query</el-button>
      <el-button type="warning" plain style="margin: 0 10px" @click="reset">Reset</el-button>
    </div>
    <div class="card" style="margin-bottom: 5px">
      <el-button type="primary" plain @click="handleAdd">Add new</el-button>
    </div>

    <div class="card" style="margin-bottom: 5px">
      <!-- Data.tableData from QaApp/ secretPage returns list -->
      <el-table stripe :data="data.tableData">
        <el-table-column prop="name" label="Application name" width="180" />
        <!-- Which one of the libraries is it? The name was found in the back end by a link sheet. -->
        <el-table-column label="Attach knowledge base" min-width="200">
          <template #default="scope">
            <el-tag v-for="name in scope.row.kb_names" :key="name" size="small" style="margin-right: 4px">{{ name }}</el-tag>
          </template>
        </el-table-column>
        <!-- Turn off the straight link and open the LangGraph status chart. -->
        <el-table-column prop="agent_enabled" label="Mode" width="130">
          <template #default="scope">
            <el-tag :type="scope.row.agent_enabled === 'Yes' ? 'warning' : 'info'" size="small">
              {{ scope.row.agent_enabled === 'Yes' ? 'Agentic' : 'Linear chain' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="max_history" label="History count" width="100" />
        <el-table-column prop="status" label="Status" width="90">
          <template #default="scope">
            <el-tag :type="scope.row.status === 'Active' ? 'success' : 'info'" size="small">{{ scope.row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="Actions" width="200" fixed="right">
          <template #default="scope">
            <!-- Try this application directly on the management end, without cutting to the user -->
            <el-button type="success" size="small" @click="openChat(scope.row)">Try it</el-button>
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
    <el-dialog title="Q&A apps" v-model="data.formVisible" width="55%" destroy-on-close>
      <el-form ref="formRef" :model="data.form" :rules="data.rules" label-width="120px" style="padding: 10px 20px">
        <el-form-item label="Application name" prop="name">
          <el-input v-model="data.form.name" placeholder="Please enter the application name"></el-input>
        </el-form-item>
        <el-form-item label="Application description">
          <el-input v-model="data.form.description" type="textarea" :rows="2" placeholder="What range of questions does this application answer"></el-input>
        </el-form-item>
        <!-- An application can hang up multiple libraries and search together in these vaults. -->
        <el-form-item label="Attach knowledge base" prop="kb_ids">
          <el-select v-model="data.form.kb_ids" multiple style="width: 100%" placeholder="At least select one knowledge base">
            <el-option v-for="kb in data.kbOptions" :key="kb.id" :label="kb.name" :value="kb.id"></el-option>
          </el-select>
        </el-form-item>
        <!-- Use default search policy when not selecting -->
        <el-form-item label="Retrieval Strategy">
          <el-select v-model="data.form.retrieval_strategy_id" clearable style="width: 100%" placeholder="Do not select and use the default strategy">
            <el-option v-for="item in data.strategyOptions" :key="item.id" :label="item.name" :value="item.id"></el-option>
          </el-select>
        </el-form-item>
        <!-- Turn off the straight link from chapter 15-19 and open the status chart for chapter 22. -->
        <el-form-item label="Agentic mode">
          <el-radio-group v-model="data.form.agent_enabled">
            <el-radio value="No">Linear chain</el-radio>
            <el-radio value="Yes">Agentic (model decides whether to re-query)</el-radio>
          </el-radio-group>
        </el-form-item>
        <!-- Number of historical messages brought into model, 0 means no history -->
        <el-form-item label="History message count">
          <el-input-number v-model="data.form.max_history" :min="0" :max="20" style="width: 100%"></el-input-number>
        </el-form-item>
        <!-- If you can't retrieve the information, say that. You don't let the model make it up. -->
        <el-form-item label="Fallback script">
          <el-input v-model="data.form.empty_answer" placeholder="Response content when no materials are found"></el-input>
        </el-form-item>
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
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/utils/request.js'
import router from '@/router/index.js'

const data = reactive({
  formVisible: false,
  form: {},
  tableData: [],
  // Two drop-downs for the knowledge base and retrieval strategy
  kbOptions: [],
  strategyOptions: [],
  pageNum: 1,
  pageSize: 10,
  total: 0,
  name: '',
  status: '',
  rules: {
    name: [
      { required: true, message: 'Please enter the application name', trigger: 'blur' }
    ],
    kb_ids: [
      { required: true, message: 'At least select one knowledge base', trigger: 'change' }
    ]
  }
})

const formRef = ref()

const loadOptions = () => {
  request.get('/knowledgeBase/selectAll').then(res => {
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

const load = () => {
  request.get('/qaApp/selectPage', {
    params: { page_num: data.pageNum, page_size: data.pageSize, name: data.name, status: data.status }
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
  // Adds by default to a straight link. History strip six, and the quiz gives a standard.
  data.form = {
    kb_ids: [],
    agent_enabled: 'No',
    max_history: 6,
    empty_answer: 'No relevant content was found in the knowledge base.',
    status: 'Active'
  }
  data.formVisible = true
}

const handleEdit = (row) => {
  // Deep Copy Current Line, Kb_ids is detected from backend by association table
  data.form = JSON.parse(JSON.stringify(row))
  data.formVisible = true
}

const save = () => {
  formRef.value.validate(valid => {
    if (!valid) {
      return
    }
    const action = data.form.id
        ? request.put('/qaApp/update', data.form)
        : request.post('/qaApp/add', data.form)
    action.then(res => {
      if (res.code === '200') {
        ElMessage.success('Saved')
        data.formVisible = false
        load()
      } else {
        // Repeated names, no knowledge base attached, history crossed the line and backends returned to people's tip.
        ElMessage.error(res.msg)
      }
    })
  })
}

const del = (id) => {
  ElMessageBox.confirm('Data cannot be recovered after deletion. Are you sure you want to delete?', 'Confirm deletion', { type: 'warning' }).then(() => {
    request.delete('/qaApp/delete/' + id).then(res => {
      if (res.code === '200') {
        ElMessage.success('Deleted')
        load()
      } else {
        ElMessage.error(res.msg)
      }
    })
  })
}

const openChat = (row) => {
  // Jump with an application ID to the question-and-answer page and ask directly about this application.
  router.push('/manager/qaChat?appId=' + row.id)
}

const reset = () => {
  data.name = ''
  data.status = ''
  data.pageNum = 1
  load()
}

loadOptions()
load()
</script>
