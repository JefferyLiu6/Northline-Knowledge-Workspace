import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', redirect: '/login' },
    {
      path: '/manager',
      component: () => import('@/views/Manager.vue'),
      children: [
        { path: 'home', meta: { name: 'Dashboard' }, component: () => import('@/views/manager/Home.vue'),  },
        { path: 'user', meta: { name: 'User Management', requiresAdmin: true }, component: () => import('@/views/manager/User.vue'), },
        // The knowledge base is a level-I classification of enterprise information that only managers can maintain
        { path: 'knowledgeBase', meta: { name: 'Knowledge Bases', requiresAdmin: true }, component: () => import('@/views/manager/KnowledgeBase.vue'), },
        // Knowledge documents are attached to the knowledge base and only administrators can upload and remove them
        { path: 'knowledgeDocument', meta: { name: 'Document Management', requiresAdmin: true }, component: () => import('@/views/manager/KnowledgeDocument.vue'), },
        // Severing strategy determines how documents are sliced into segments.
        { path: 'chunkStrategy', meta: { name: 'Chunking Strategy', requiresAdmin: true }, component: () => import('@/views/manager/ChunkStrategy.vue'), },
        // The knowledge session is the smallest unit to retrieve and supports manual correction.
        { path: 'knowledgeChunk', meta: { name: 'Knowledge Chunks', requiresAdmin: true }, component: () => import('@/views/manager/KnowledgeChunk.vue'), },
        // Enter a question to see what parts of the search strategy have been recalled.
        { path: 'retrievalTest', meta: { name: 'Retrieval Testing', requiresAdmin: true }, component: () => import('@/views/manager/RetrievalTest.vue'), },
        // Management page for a set of search parameters
        { path: 'retrievalStrategy', meta: { name: 'Retrieval Strategy', requiresAdmin: true }, component: () => import('@/views/manager/RetrievalStrategy.vue'), },
        // The same problem, running side by side with a set of tactics, looking at the difference.
        { path: 'retrievalDebug', meta: { name: 'Retrieval Debugger', requiresAdmin: true }, component: () => import('@/views/manager/RetrievalDebug.vue'), },
        // Access configuration of three models, with immediate effect without restarting
        { path: 'aiModelConfig', meta: { name: 'AI Model Configuration', requiresAdmin: true }, component: () => import('@/views/manager/AiModelConfig.vue'), },
        // All the tips sent to models are maintained here.
        { path: 'promptTemplate', meta: { name: 'Prompt Template', requiresAdmin: true }, component: () => import('@/views/manager/PromptTemplate.vue'), },
        // If you can use this table to determine which tools you want to use, Agent, turn the switch on is real.
        { path: 'functionTool', meta: { name: 'Tool Center', requiresAdmin: true }, component: () => import('@/views/manager/FunctionTool.vue'), },
        // Every tool call has a log, and every success is recorded.
        { path: 'toolCallLog', meta: { name: 'Tool Call Log', requiresAdmin: true }, component: () => import('@/views/manager/ToolCallLog.vue'), },
        // Enter a question and see if Agent decides whether to re-retrieve it.
        { path: 'agentTest', meta: { name: 'Agent Execution', requiresAdmin: true }, component: () => import('@/views/manager/AgentTest.vue'), },
        // Run the log list and the execution time line for each run
        { path: 'agentRun', meta: { name: 'Agent Run History', requiresAdmin: true }, component: () => import('@/views/manager/AgentRun.vue'), },
        // An application = a knowledge base + a search strategy + a question-and-answer mode
        { path: 'qaApp', meta: { name: 'Application Management', requiresAdmin: true }, component: () => import('@/views/manager/QaApp.vue'), },
        // The manager directly asks questions about the application, and then reads the answers.
        { path: 'qaChat', meta: { name: 'Q&A Testing', requiresAdmin: true }, component: () => import('@/views/manager/QaChat.vue'), },
        // All session logs and user feedback, and the question of stepping will be added to the optimization list.
        { path: 'chatLog', meta: { name: 'Chat Logs and Feedback', requiresAdmin: true }, component: () => import('@/views/manager/ChatLog.vue'), },
        // Assessments and usages, three sources: manual entry, document generation, feedback deposition
        { path: 'evalDataset', meta: { name: 'Evaluation Datasets', requiresAdmin: true }, component: () => import('@/views/manager/EvalDataset.vue'), },
        // Batch run evaluation, using LLM-as-judge to calculate four indicators
        { path: 'evalTask', meta: { name: 'Batch Evaluation', requiresAdmin: true }, component: () => import('@/views/manager/EvalTask.vue'), },
        // Multi-reports were compared, and horizontally the difference in points from each step of optimization
        { path: 'evalDashboard', meta: { name: 'Strategy Comparison', requiresAdmin: true }, component: () => import('@/views/manager/EvalDashboard.vue'), },
        { path: 'person', meta: { name: 'Profile' }, component: () => import('@/views/manager/Person.vue'), },
        { path: 'password', meta: { name: 'Change Password' }, component: () => import('@/views/manager/Password.vue'), },
        // New Path
      ]
    },
    {
      path: '/front',
      component: () => import('@/views/Front.vue'),
      children: [
        { path: 'home', component: () => import('@/views/front/Home.vue'),  },
        // Personal center displays and changes information on current login users, Meta superscript requiresLogin,
        // The guards below stopped the unincorporated access.
        { path: 'person', meta: { requiresLogin: true }, component: () => import('@/views/front/Person.vue'),  },
      ]
    },
    { path: '/login', component: () => import('@/views/Login.vue') },
    { path: '/register', component: () => import('@/views/Register.vue') },
    { path: '/404', component: () => import('@/views/404.vue') },
    { path: '/:pathMatch(.*)', redirect: '/404' }
  ]
})

// Toggle Page Jump to Top
router.afterEach(() => {
  setTimeout(() => {
    window.scroll({ top: 0, behavior: 'smooth' })
  }, 0)
})

router.beforeEach((to) => {
  // Take the current user from the cache saved at login. Get an empty object when not login
  const user = JSON.parse(localStorage.getItem('xm-user') || '{}')
  // Administration requires first login on all pages, no id indicates that there are no users in the cache and returns login page
  if (to.path.startsWith('/manager') && !user.id) {
    return '/login'
  }
  // User only requests login on the page marked requiresLogin, and the front page is open to visitors
  if (to.meta.requiresLogin && !user.id) {
    return '/login'
  }
  // The web page marked by Meta is accessible only to administrators.
  // Back to the management front page instead of white screen when ordinary users miss access
  if (to.meta.requiresAdmin && user.role !== 'ADMIN') {
    return '/manager/home'
  }
})

export default router
