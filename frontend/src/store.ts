import { create } from 'zustand'

export type KernelMode = 'auto' | 'manual' | 'hybrid'
export type AgentTask = 'Planner Agent' | 'Policy Agent' | 'Tool Manager' | 'Memory Agent' | 'RAG Agent' | 'Execution Agent' | 'Verification Agent' | 'Runtime Scheduler' | 'Compiler Agent'

export interface AgentMapping {
  task: AgentTask
  model: string
}

export interface ProjectFile {
  id: string
  name: string
  size: string
  type: string
}

export interface Project {
  id: string
  title: string
  description: string
  createdAt: number
  memory: string
  instructions: string
  files: ProjectFile[]
}

export interface Chat {
  id: string
  title: string
  timestamp: number
  isPinned: boolean
  isFavorite: boolean
  isArchived: boolean
  projectId: string | null
}

export interface TraceNode {
  id: string
  text: string
  icon: string
  color: string
}

export interface Message {
  id: string
  chatId: string
  role: 'user' | 'system'
  content: string
  traces?: TraceNode[]
}

export interface Preferences {
  theme: 'dark' | 'light' | 'system'
  language: string
  animations: boolean
  textDensity: 'compact' | 'comfortable' | 'loose'
}

interface AppState {
  // Auth
  isAuthenticated: boolean
  authToken: string | null
  user: { id: string; name: string; email: string; role: string; plan: string } | null
  organization: { id: string; name: string } | null
  loginWithToken: (token: string, employee: { id: string; name: string; email: string; role: string }, org: { id: string; name: string }) => void
  logout: () => void

  // Theme & Preferences
  preferences: Preferences
  updatePreference: <K extends keyof Preferences>(key: K, value: Preferences[K]) => void
  sidebarCollapsed: boolean
  toggleSidebar: () => void
  activeRightTab: 'content' | 'agent'
  setActiveRightTab: (tab: 'content' | 'agent') => void

  // Kernel & Matrix
  kernelMode: KernelMode
  setKernelMode: (mode: KernelMode) => void
  agentMappings: AgentMapping[]
  updateAgentMapping: (task: AgentTask, model: string) => void
  isDirty: boolean
  saveConfiguration: () => void
  resetConfiguration: () => void

  // Models
  models: string[]

  // Projects
  projects: Project[]
  activeProjectId: string | null
  setActiveProjectId: (id: string | null) => void
  addProject: (title: string, description: string) => void
  updateProjectInstructions: (id: string, instructions: string) => void
  addProjectFile: (id: string, file: Omit<ProjectFile, 'id'>) => void

  // Chats & Messages
  chats: Chat[]
  activeChatId: string | null
  setActiveChatId: (id: string | null) => void
  addChat: (projectId?: string | null) => void
  renameChat: (id: string, newTitle: string) => void
  deleteChat: (id: string) => void
  duplicateChat: (id: string) => void
  pinChat: (id: string) => void
  archiveChat: (id: string) => void

  messages: Message[]
  addMessage: (chatId: string, role: 'user' | 'system', content: string) => string
  addTraceToMessage: (messageId: string, trace: TraceNode) => void
}

const DEFAULT_MODELS = [
  'Claude Sonnet', 'Claude Opus', 'GPT-5', 'GPT-4.1', 
  'Gemini 2.5 Pro', 'Gemini Flash', 'DeepSeek', 'Qwen', 'Llama', 'Mistral', 'Grok'
]

const DEFAULT_MAPPINGS: AgentMapping[] = [
  { task: 'Planner Agent', model: 'Claude Sonnet' },
  { task: 'Policy Agent', model: 'GPT-4.1' },
  { task: 'Tool Manager', model: 'Gemini Flash' },
  { task: 'Memory Agent', model: 'DeepSeek' },
  { task: 'RAG Agent', model: 'Qwen' },
  { task: 'Execution Agent', model: 'Claude Opus' },
  { task: 'Verification Agent', model: 'Llama' },
  { task: 'Runtime Scheduler', model: 'Mistral' },
  { task: 'Compiler Agent', model: 'Grok' }
]

export const useStore = create<AppState>((set) => ({
  // Auth
  isAuthenticated: false,
  authToken: null,
  user: null,
  organization: null,
  loginWithToken: (token, employee, org) => set({
    isAuthenticated: true,
    authToken: token,
    user: { ...employee, plan: employee.role === 'admin' ? 'Admin' : 'Pro plan' },
    organization: org
  }),
  logout: () => set({ isAuthenticated: false, authToken: null, user: null, organization: null, activeChatId: null }),

  // Preferences & UI
  preferences: {
    theme: 'system',
    language: 'English',
    animations: true,
    textDensity: 'comfortable'
  },
  updatePreference: (key, value) => set(state => ({ preferences: { ...state.preferences, [key]: value }, isDirty: true })),
  sidebarCollapsed: false,
  toggleSidebar: () => set(state => ({ sidebarCollapsed: !state.sidebarCollapsed })),
  activeRightTab: 'content',
  setActiveRightTab: (tab) => set({ activeRightTab: tab }),

  // Kernel
  kernelMode: 'auto',
  setKernelMode: (mode) => set({ kernelMode: mode, isDirty: true }),
  agentMappings: [...DEFAULT_MAPPINGS],
  updateAgentMapping: (task, model) => set(state => ({
    agentMappings: state.agentMappings.map(m => m.task === task ? { ...m, model } : m),
    isDirty: true
  })),
  isDirty: false,
  saveConfiguration: () => set({ isDirty: false }),
  resetConfiguration: () => set({ agentMappings: [...DEFAULT_MAPPINGS], kernelMode: 'auto', isDirty: false }),

  // Models
  models: DEFAULT_MODELS,

  // Projects
  projects: [
    { id: 'p1', title: 'AIOS', description: 'Core microkernel design', createdAt: Date.now(), memory: 'Full Context Available', instructions: '', files: [] },
    { id: 'p2', title: 'Compiler', description: 'Optimization vectors', createdAt: Date.now(), memory: 'Full Context Available', instructions: '', files: [] },
    { id: 'p3', title: 'Memory', description: 'RAG and vector indexing', createdAt: Date.now(), memory: 'Full Context Available', instructions: '', files: [] },
    { id: 'p4', title: 'DBMS', description: 'Storage schema', createdAt: Date.now(), memory: 'Full Context Available', instructions: '', files: [] },
    { id: 'p5', title: 'Research', description: 'Experimental modeling', createdAt: Date.now(), memory: 'Full Context Available', instructions: '', files: [] },
    { id: 'p6', title: 'Personal', description: 'Scratchpad and notes', createdAt: Date.now(), memory: 'Full Context Available', instructions: '', files: [] }
  ],
  activeProjectId: null,
  setActiveProjectId: (id) => set({ activeProjectId: id }),
  addProject: (title, description) => {
    const id = 'p' + Date.now().toString()
    set(state => ({ projects: [{ id, title, description, createdAt: Date.now(), memory: 'Full Context Available', instructions: '', files: [] }, ...state.projects] }))
  },
  updateProjectInstructions: (id, instructions) => set(state => ({
    projects: state.projects.map(p => p.id === id ? { ...p, instructions } : p)
  })),
  addProjectFile: (id, file) => set(state => ({
    projects: state.projects.map(p => p.id === id ? { ...p, files: [...p.files, { ...file, id: 'f' + Date.now().toString() + Math.random() }] } : p)
  })),

  // Chats
  chats: [
    { id: '1', title: 'File reading and comprehension request', timestamp: Date.now() - 100000, isPinned: false, isFavorite: false, isArchived: false, projectId: null },
    { id: '2', title: 'Roadmap for Neelvak code impl...', timestamp: Date.now() - 200000, isPinned: true, isFavorite: true, isArchived: false, projectId: null },
    { id: '3', title: 'System architecture blueprint', timestamp: Date.now() - 300000, isPinned: false, isFavorite: false, isArchived: false, projectId: 'p1' },
  ],
  activeChatId: '1',
  setActiveChatId: (id) => set({ activeChatId: id }),
  addChat: (projectId = null) => {
    const id = Date.now().toString()
    set(state => ({
      chats: [{ id, title: 'New Conversation', timestamp: Date.now(), isPinned: false, isFavorite: false, isArchived: false, projectId }, ...state.chats],
      activeChatId: id,
      messages: state.messages.filter(m => m.chatId !== id) // clear any old if collision (unlikely)
    }))
  },
  renameChat: (id, newTitle) => set(state => ({
    chats: state.chats.map(c => c.id === id ? { ...c, title: newTitle } : c)
  })),
  deleteChat: (id) => set(state => ({
    chats: state.chats.filter(c => c.id !== id),
    activeChatId: state.activeChatId === id ? null : state.activeChatId
  })),
  duplicateChat: (id) => set(state => {
    const chatToDup = state.chats.find(c => c.id === id)
    if (!chatToDup) return state
    const newId = Date.now().toString()
    return {
      chats: [{ ...chatToDup, id: newId, title: chatToDup.title + ' (Copy)', timestamp: Date.now() }, ...state.chats],
      activeChatId: newId
    }
  }),
  pinChat: (id) => set(state => ({
    chats: state.chats.map(c => c.id === id ? { ...c, isPinned: !c.isPinned } : c)
  })),
  archiveChat: (id) => set(state => ({
    chats: state.chats.map(c => c.id === id ? { ...c, isArchived: true } : c)
  })),

  // Messages
  messages: [],
  addMessage: (chatId, role, content) => {
    const id = Date.now().toString() + Math.random().toString()
    set(state => ({
      messages: [...state.messages, { id, chatId, role, content, traces: [] }]
    }))
    return id
  },
  addTraceToMessage: (messageId, trace) => set(state => ({
    messages: state.messages.map(m => 
      m.id === messageId ? { ...m, traces: [...(m.traces || []), trace] } : m
    )
  }))
}))
