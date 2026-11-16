<template>
  <div>
    <div class="card" style="margin-bottom: 5px">
      <!-- The entered policy name is stored in data.name, which is a blurry match for the name parameter -->
      <el-input v-model="data.name" style="width: 220px; margin-right: 10px" placeholder="Please enter the strategy name to search"></el-input>
      <!-- The selected type is stored in data.strategyType as a precise match to the strategy_type parameter -->
      <el-select v-model="data.strategyType" clearable style="width: 180px; margin-right: 10px" placeholder="Please select the strategy type">
        <el-option label="Recursive chunking" value="Recursive chunking"></el-option>
        <el-option label="Parent-child chunking" value="Parent-child chunking"></el-option>
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
      <!-- Data.tableData from list returned by /chunkStrategy/ selectPage -->
      <el-table stripe :data="data.tableData">
        <el-table-column prop="name" label="Strategy Name" width="200" />
        <el-table-column prop="strategy_type" label="Strategy Type" width="120" />
        <!-- Recursive fragments cut only one layer, and the father and son have to cut both pieces. -->
        <el-table-column prop="chunk_size" label="Segment Length" width="100" />
        <el-table-column prop="chunk_overlap" label="Overlap Characters" width="100" />
        <!-- The length of the parent piece is only necessary for the father and son, and the column of the backwards block is empty. -->
        <el-table-column prop="parent_chunk_size" label="Parent Chunk Length" width="100">
          <template #default="scope">{{ scope.row.parent_chunk_size || '-' }}</template>
        </el-table-column>
        <el-table-column prop="separators" label="Separator" width="160" show-overflow-tooltip />
        <!-- Only one default strategy in the whole table is used when the knowledge base does not have a separate strategy. -->
        <el-table-column prop="is_default" label="Default" width="80">
          <template #default="scope">
            <el-tag v-if="scope.row.is_default === 'Yes'" type="success" size="small">Default</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="remark" label="Remarks" show-overflow-tooltip />
        <el-table-column label="Actions" width="100" fixed="right">
          <template #default="scope">
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
    <el-dialog title="Chunking Strategy" v-model="data.formVisible" width="45%" destroy-on-close>
      <el-form ref="formRef" :model="data.form" :rules="data.rules" label-width="110px" style="padding: 20px">
        <el-form-item label="Strategy Name" prop="name">
          <el-input v-model="data.form.name" placeholder="Please enter the strategy name"></el-input>
        </el-form-item>
        <!-- When you choose a parent to split it, you'll have the length of the child. -->
        <el-form-item label="Strategy Type" prop="strategy_type">
          <el-select v-model="data.form.strategy_type" style="width: 100%">
            <el-option label="Recursive chunking" value="Recursive chunking"></el-option>
            <el-option label="Parent-child chunking" value="Parent-child chunking"></el-option>
          </el-select>
        </el-form-item>
        <!-- Snippet length is the number of target characters to be cut. It's the length of a sub-block when the father and son split up. -->
        <el-form-item label="Segment Length" prop="chunk_size">
          <el-input-number v-model="data.form.chunk_size" :min="50" :max="4000" :step="50" style="width: 100%"></el-input-number>
        </el-form-item>
        <!-- We're going to have a bit of an overlap between the next and the other, so we don't get a sentence that just doesn't work on both sides. -->
        <el-form-item label="Overlap Characters" prop="chunk_overlap">
          <el-input-number v-model="data.form.chunk_overlap" :min="0" :max="1000" :step="10" style="width: 100%"></el-input-number>
        </el-form-item>
        <!-- Only fathers and sons have to fill in the length of the parent block, and this item is not shown when it returns. -->
        <el-form-item v-if="data.form.strategy_type === 'Parent-child chunking'" label="Parent Chunk Length" prop="parent_chunk_size">
          <el-input-number v-model="data.form.parent_chunk_size" :min="100" :max="8000" :step="100" style="width: 100%"></el-input-number>
        </el-form-item>
        <!-- Comma separated, trying sequentially; \n for line breaks use the default separators when empty -->
        <el-form-item label="Separator">
          <el-input v-model="data.form.separators" placeholder="Leave blank to use default, example: \n\n,\n,.,!,?"></el-input>
        </el-form-item>
        <!-- The default tags for other policies will automatically be removed from the backend when set to default -->
        <el-form-item label="Set as Default">
          <el-radio-group v-model="data.form.is_default">
            <el-radio value="Yes">Yes</el-radio>
            <el-radio value="No">No</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="Remarks">
          <el-input v-model="data.form.remark" type="textarea" :rows="2" placeholder="Description of what kind of materials this set of parameters is suitable for"></el-input>
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
import { Delete, Edit } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/utils/request.js'

const data = reactive({
  // Control the display of a strategic window hidden, add and edit the same bullet window
  formVisible: false,
  // The objects bound by each box in the window. Id for editing, no id for adding
  form: {},
  // Table data, filled with list by /chunkStrategy/ selectPage
  tableData: [],
  pageNum: 1,
  pageSize: 10,
  total: 0,
  // Value of the top policy name search box
  name: '',
  // Value of the top policy type to pull a frame down
  strategyType: '',
  // The front end verification rules for windows, names, types and lengths are required
  rules: {
    name: [
      { required: true, message: 'Please enter the strategy name', trigger: 'blur' }
    ],
    strategy_type: [
      { required: true, message: 'Please select the strategy type', trigger: 'change' }
    ],
    chunk_size: [
      { required: true, message: 'Please enter the segment length', trigger: 'blur' }
    ]
  }
})

// FormRef bind el-form in the window, trigger whole table check when point is determined
const formRef = ref()

const load = () => {
  // Page-by-page query interface with four parameters from page numbers, number of lines per page, name search box, type drop frame
  request.get('/chunkStrategy/selectPage', {
    params: {
      page_num: data.pageNum,
      page_size: data.pageSize,
      name: data.name,
      strategy_type: data.strategyType
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
  // Add a common default value when adding, no id, save will walk an additional interface
  data.form = { strategy_type: 'Recursive chunking', chunk_size: 500, chunk_overlap: 50, is_default: 'No' }
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
    // Data.form.id exists to explain that the current window is edit mode, and backend updates chunk_strategy table logs with id
    // Data.form.id does not exist as an explanation for adding a new mode, and the backend inserts a new strategy record
    const action = data.form.id
        ? request.put('/chunkStrategy/update', data.form)
        : request.post('/chunkStrategy/add', data.form)
    action.then(res => {
      if (res.code === '200') {
        ElMessage.success('Saved')
        // Close the window and recheck the list so that the table shows the latest data
        data.formVisible = false
        load()
      } else {
        // The business of repeating names, overlaps greater than the length of a segment, parent blocks smaller than sub-blocks failed and backend returns human voice tips in msg
        ElMessage.error(res.msg)
      }
    })
  })
}

const del = (id) => {
  // Play confirmation boxes before deleting, do not enter then, do not request
  ElMessageBox.confirm('Data cannot be recovered after deletion. Are you sure you want to delete?', 'Confirm deletion', { type: 'warning' }).then(() => {
    request.delete('/chunkStrategy/delete/' + id).then(res => {
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
  // Clear two search conditions and return to page one, check the full list again
  data.name = ''
  data.strategyType = ''
  data.pageNum = 1
  load()
}

// Check the page once it is loaded. You can see the first page when you enter the page.
load()
</script>
