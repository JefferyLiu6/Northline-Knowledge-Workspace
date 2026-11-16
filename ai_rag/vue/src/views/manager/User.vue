<template>
  <div>
    <div class="card" style="margin-bottom: 5px">
      <!-- Entered name to deposit data.name, mixed matching as name parameter to backend for point query -->
      <el-input v-model="data.name" style="width: 240px; margin-right: 10px" placeholder="Enter Name to Query"></el-input>
      <!-- The selected role is stored in data.rolle, which is accurately matched as a roller parameter to the backend; empty with open character -->
      <el-select v-model="data.role" clearable style="width: 180px; margin-right: 10px" placeholder="Please Select Role">
        <el-option label="Administrator" value="ADMIN"></el-option>
        <el-option label="Standard user" value="USER"></el-option>
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
      <!-- data.tableData from a list returned by /user/ selectPage; save selected row id in data.ids when ticking changes -->
      <el-table stripe :data="data.tableData" @selection-change="handleSelectionChange">
        <!-- Multiple rows, delete use with batch -->
        <el-table-column type="selection" width="55" />
        <el-table-column prop="username" label="Account" />
        <!-- avatar stored the file download address, which is empty and does not rewrite pictures to avoid cracks. -->
        <el-table-column prop="avatar" label="Avatar" width="80">
          <template #default="scope">
            <el-image v-if="scope.row.avatar && !scope.row.avatar.endsWith('/1721114905635-shiba-inu.jpeg')"
                      class="user-table-photo" :src="scope.row.avatar" fit="cover"
                      :preview-src-list="[scope.row.avatar]" preview-teleported>
              <template #error><WorkspaceAvatar :user="scope.row" /></template>
            </el-image>
            <WorkspaceAvatar v-else :user="scope.row" />
          </template>
        </el-table-column>
        <el-table-column prop="name" label="Name" />
        <!-- Store ADMIN/USER role values and show readable labels. -->
        <el-table-column prop="role" label="Role">
          <template #default="scope">
            {{ scope.row.role === 'ADMIN' ? 'Administrator' : 'Standard user' }}
          </template>
        </el-table-column>
        <el-table-column prop="phone" label="Phone" />
        <el-table-column prop="email" label="Email" />
        <!-- The table contains NORMAL/ DISABLED, displays a normal green tab and deactivates the red label -->
        <el-table-column prop="status" label="Status">
          <template #default="scope">
            <el-tag :type="scope.row.status === 'NORMAL' ? 'success' : 'danger'">
              {{ scope.row.status === 'NORMAL' ? 'Active' : 'Disabled' }}
            </el-tag>
          </template>
        </el-table-column>
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
    <!-- Data.total does not render the whole page bar unreflective when 0, avoiding a single zero page below the empty list -->
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
    <el-dialog title="User Information" v-model="data.formVisible" width="40%" destroy-on-close>
      <el-form :model="data.form" label-width="70px" style="padding: 20px">
        <!-- Data.form.id at editing has value and account input boxes are disabled because the backend update interface does not accept changes to accounts -->
        <el-form-item label="Account">
          <el-input v-model="data.form.username" placeholder="Enter your username" :disabled="data.form.id !== undefined"></el-input>
        </el-form-item>
        <!-- Show password boxes only when added. The backend update interface does not process passwords while editing, and change password to personal center -->
        <el-form-item v-if="!data.form.id" label="Password">
          <el-input v-model="data.form.password" show-password placeholder="Password defaults to 123456 if not filled"></el-input>
        </el-form-item>
        <!-- Trigger handlefile Upload after uploading successfully, write the returned download address into data.form.avatar -->
        <el-form-item label="Avatar">
          <el-upload :action="baseUrl + '/files/upload'" :headers="uploadHeaders" :on-success="handleFileUpload" list-type="picture">
            <el-button type="primary">Click to upload</el-button>
          </el-upload>
        </el-form-item>
        <el-form-item label="Name">
          <el-input v-model="data.form.name" placeholder="Please enter name"></el-input>
        </el-form-item>
        <el-form-item label="Role">
          <el-select v-model="data.form.role" style="width: 100%">
            <el-option label="Administrator" value="ADMIN"></el-option>
            <el-option label="Standard user" value="USER"></el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="Phone">
          <el-input v-model="data.form.phone" placeholder="Please enter phone"></el-input>
        </el-form-item>
        <el-form-item label="Email">
          <el-input v-model="data.form.email" placeholder="Please enter email"></el-input>
        </el-form-item>
        <el-form-item label="Status">
          <el-radio-group v-model="data.form.status">
            <el-radio value="NORMAL">Active</el-radio>
            <el-radio value="DISABLED">Disabled</el-radio>
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
const uploadHeaders = { token: JSON.parse(localStorage.getItem("xm-user") || "{}").token }
import WorkspaceAvatar from '@/components/WorkspaceAvatar.vue'
import { reactive } from 'vue'
import { Delete, Edit } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/utils/request.js'

// An action for header uploading components requires a full address, not to go reply.js, so take the interface root address separately
const baseUrl = import.meta.env.VITE_BASE_URL

const data = reactive({
  // Control the display of user information windows to hide, add and edit the same window
  formVisible: false,
  // The objects bound by each box in the window. Id for editing, no id for adding
  form: {},
  // Table data, filled with list by /user/ secactPage
  tableData: [],
  // Current page number, update and retrace the page code when the component is changed
  pageNum: 1,
  // Number of articles per page, fixed at 10
  pageSize: 10,
  // Total bar number, decide to show pages by page line, 0 hours the whole strip is not rendered
  total: 0,
  // The value of the top name search box to send to backends as query parameters
  name: '',
  // The value of the top role to pull the frame as a query parameter to the back for exact matching
  role: '',
  // _Other Organiser
  ids: []
})

const load = () => {
  // Page-by-page query interface with four parameters from page numbers, number of lines per page, name search box, role bottom frame
  request.get('/user/selectPage', {
    params: {
      page_num: data.pageNum,
      page_size: data.pageSize,
      name: data.name,
      role: data.role
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
  // Role default normal user, status default normal and backend default value for add
  data.form = { role: 'USER', status: 'NORMAL' }
  data.formVisible = true
}

const handleEdit = (row) => {
  // (b) Deep copy of the current line to avoid direct modification of the objects in the tabledata leading to a change in the window;
  // id, save will update the interface when a copy comes in.
  data.form = JSON.parse(JSON.stringify(row))
  data.formVisible = true
}

const save = () => {
  // Data.form.id exists to explain that the current window is editing mode, and backend updates the user table log with id
  // Data.form.id does not exist as an explanation for adding a new mode, and the backend inserts a new user record
  const action = data.form.id
      ? request.put('/user/update', data.form)
      : request.post('/user/add', data.form)
  action.then(res => {
    if (res.code === '200') {
      ElMessage.success('Saved')
      // Close the window and recheck the list so that the table shows the latest data
      data.formVisible = false
      load()
    } else {
      // Repeat account, role parameter error failed. Backend returns human message in msg
      ElMessage.error(res.msg)
    }
  })
}

const del = (id) => {
  // Play confirmation boxes before deleting, do not enter then, do not request
  ElMessageBox.confirm('Data cannot be recovered after deletion. Are you sure you want to delete?', 'Confirm deletion', { type: 'warning' }).then(() => {
    // id is embedded on the path, and backends receive with path parameters
    request.delete('/user/delete/' + id).then(res => {
      if (res.code === '200') {
        ElMessage.success('Deleted')
        // Delete recheck list and remove deleted lines from table
        load()
      } else {
        // Deleting the current login account will be blocked by a backend and hinted in msg
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
    request.delete('/user/deleteBatch', { data: data.ids }).then(res => {
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

const handleFileUpload = (res) => {
  if (res.code !== "200") {
    ElMessage.error(res.msg || "Upload failed")
    return
  }
  // Rees.data returned from the backend after uploading success is a file download address, which returns to the header field of the form,
  // This address is written in the avtar column of the user table when the dot is sure to save
  data.form.avatar = res.data
}

const reset = () => {
  // Clear two search conditions and return to page one, check the full list again
  data.name = ''
  data.role = ''
  data.pageNum = 1
  load()
}

// Check the page once it is loaded. You can see the first page when you enter the page.
load()
</script>

<style scoped>
.user-table-photo {
  display: block;
  width: 34px;
  height: 34px;
  border-radius: 50%;
}
</style>
