import React, { useState, useRef, useEffect } from 'react'
import { ChevronDown, Plus, Mic, ArrowUp, ChevronRight } from 'lucide-react'
import { useStore, type TraceNode } from '../store'
import TraceNodeItem from './TraceNodeItem'

const KERNEL_TRACE_STEPS: TraceNode[] = [
  { id: 't1', text: "Kernel initialized", icon: "fa-solid fa-power-off", color: "text-slate-400" },
  { id: 't2', text: "Reading memory <span class='text-white'>memory/manager.py</span>", icon: "fa-regular fa-file-code", color: "text-text-muted" },
  { id: 't3', text: "Searching RAG index", icon: "fa-solid fa-magnifying-glass", color: "text-sky-400" },
  { id: 't4', text: "Planning execution via topological sort", icon: "fa-solid fa-diagram-project", color: "text-violet-400" },
  { id: 't5', text: "Selecting Runtime A (Competitive)", icon: "fa-solid fa-microchip", color: "text-blue-400" },
  { id: 't6', text: "Policy Engine: Validating constraints", icon: "fa-solid fa-shield-halved", color: "text-accent-orange" },
  { id: 't7', text: "Running tools sandbox", icon: "fa-solid fa-toolbox", color: "text-amber-400" },
  { id: 't8', text: "Yielding structural output back to user", icon: "fa-solid fa-check", color: "text-emerald-400" }
]

export default function ChatCanvas() {
  const { chats, activeChatId, messages } = useStore()
  const [inputValue, setInputValue] = useState('')
  const [isSimulating, setIsSimulating] = useState(false)
  const [isExecutionCollapsed, setIsExecutionCollapsed] = useState(false)

  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const feedRef = useRef<HTMLDivElement>(null)
  const traceTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const activeChat = chats.find(c => c.id === activeChatId)
  const activeMessages = messages.filter(m => m.chatId === activeChatId)

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInputValue(e.target.value)
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 200) + 'px'
    }
  }

  const handleSubmit = async () => {
    if (!inputValue.trim() || isSimulating || !activeChatId) return
    const content = inputValue.trim()
    setInputValue('')
    if (textareaRef.current) textareaRef.current.style.height = 'auto'

    setIsExecutionCollapsed(false)
    setIsSimulating(true)

    // Add user message to store
    const msgId = useStore.getState().addMessage(activeChatId, 'user', content)

    // Stream kernel trace steps visually at 300ms intervals while waiting for API
    let step = 0
    traceTimerRef.current = setInterval(() => {
      if (step < KERNEL_TRACE_STEPS.length) {
        useStore.getState().addTraceToMessage(msgId, KERNEL_TRACE_STEPS[step])
        step++
      }
    }, 300)

    try {
      // Call the real Neelvak backend kernel
      const token = useStore.getState().authToken
      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      if (token) headers['Authorization'] = `Bearer ${token}`
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers,
        body: JSON.stringify({ prompt: content, conversation_id: activeChatId })
      })

      if (traceTimerRef.current) {
        clearInterval(traceTimerRef.current)
        traceTimerRef.current = null
      }

      // Ensure all trace steps are shown
      const remainingSteps = KERNEL_TRACE_STEPS.slice(step)
      for (const s of remainingSteps) {
        useStore.getState().addTraceToMessage(msgId, s)
      }

      if (!response.ok) {
        const errData = await response.json().catch(() => ({ detail: 'Unknown error' }))
        useStore.getState().addMessage(activeChatId, 'system', `Kernel Error: ${errData.detail || response.statusText}`)
      } else {
        const data = await response.json()
        const output = data.output || data.message || JSON.stringify(data)
        const prefix = data.cached ? '⚡ Cached Response\n\n' : ''
        useStore.getState().addMessage(activeChatId, 'system', prefix + output)
      }
    } catch (err) {
      if (traceTimerRef.current) {
        clearInterval(traceTimerRef.current)
        traceTimerRef.current = null
      }
      const errorMsg = err instanceof Error ? err.message : 'Network error'
      useStore.getState().addMessage(activeChatId, 'system', `Connection error: ${errorMsg}. Is the Neelvak kernel running?`)
    } finally {
      setIsSimulating(false)
      setIsExecutionCollapsed(true)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (traceTimerRef.current) clearInterval(traceTimerRef.current)
    }
  }, [])

  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight
    }
  }, [messages, isExecutionCollapsed])

  if (!activeChat || activeChat.projectId) {
    return <div className="flex-1 flex items-center justify-center text-text-muted">No active chat selected</div>
  }

  return (
    <>
      <header className="h-14 flex items-center justify-between px-6 shrink-0 z-10">
        <div className="flex items-center gap-2 text-white font-medium cursor-pointer hover:bg-white/5 px-2 py-1.5 rounded-md smooth-transition">
          <span>{activeChat.title}</span>
          <ChevronDown className="w-3 h-3 text-text-muted mt-0.5" />
        </div>
      </header>

      <div ref={feedRef} className="flex-1 overflow-y-auto px-6 pb-40 flex flex-col items-center">
        {activeMessages.map((msg) => (
          <React.Fragment key={msg.id}>
            {msg.role === 'user' ? (
              <div className="w-full max-w-3xl mt-8 mb-6 flex justify-end">
                <div className="bg-bg-card border border-border-color px-5 py-4 rounded-2xl rounded-tr-sm text-[15px] text-white max-w-[85%] leading-relaxed shadow-sm whitespace-pre-wrap">
                  {msg.content}
                </div>
              </div>
            ) : (
              <div className="w-full max-w-3xl mt-4 mb-10 flex justify-start pl-4">
                <div className="text-[15px] text-white leading-relaxed w-full whitespace-pre-wrap">
                  {msg.content}
                </div>
              </div>
            )}

            {msg.traces && msg.traces.length > 0 && (
              <div className="w-full max-w-3xl pl-4 mb-4">
                <button
                  onClick={() => setIsExecutionCollapsed(!isExecutionCollapsed)}
                  className="flex items-center gap-2 text-xs font-medium text-text-muted hover:text-white smooth-transition bg-white/5 border border-border-color px-3 py-1.5 rounded-md mb-2"
                >
                  {isExecutionCollapsed ? <ChevronRight className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                  {isExecutionCollapsed ? 'View Execution Steps' : 'Hide Reasoning Trace'}
                </button>

                {!isExecutionCollapsed && (
                  <div className="mt-3">
                    {msg.traces.map((trace, idx) => (
                      <TraceNodeItem key={trace.id + idx} node={trace} />
                    ))}
                    {isSimulating && (
                      <div className="flex items-start gap-3 py-1.5 text-[13.5px]">
                        <div className="w-6 h-6 rounded flex items-center justify-center text-white shrink-0 bg-bg-main shadow-sm animate-pulse">
                          <div className="w-2 h-2 bg-white rounded-full"></div>
                        </div>
                        <span className="text-text-muted mt-0.5 italic">Kernel executing...</span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </React.Fragment>
        ))}

        {/* Empty state */}
        {activeMessages.length === 0 && (
          <div className="flex-1 flex flex-col items-center justify-center text-center py-20">
            <h2 className="text-2xl font-semibold text-white mb-3">Neelvak AIOS</h2>
            <p className="text-text-muted text-sm max-w-sm">Type a message to start interacting with the kernel. Your query will be processed through the full microkernel pipeline.</p>
          </div>
        )}
      </div>

      {/* Floating Composer */}
      <div className="absolute bottom-6 left-0 right-0 flex justify-center px-6 z-20 pointer-events-none">
        <div className="w-full max-w-3xl bg-bg-card border border-border-color rounded-2xl shadow-xl p-3 flex flex-col gap-3 pointer-events-auto">
          <textarea
            ref={textareaRef}
            value={inputValue}
            onChange={handleInput}
            onKeyDown={handleKeyDown}
            rows={1}
            placeholder="Write a message to Neelvak..."
            className="w-full bg-transparent border-0 text-[15px] text-white placeholder-text-muted focus:outline-none focus:ring-0 resize-none px-2 pt-1"
          />
          <div className="flex justify-between items-center">
            <button className="w-8 h-8 rounded-full hover:bg-white/10 flex items-center justify-center text-text-primary smooth-transition">
              <Plus className="w-5 h-5" />
            </button>
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg hover:bg-white/5 cursor-pointer text-text-muted text-xs smooth-transition">
                <span>Neelvak Kernel</span>
                <ChevronDown className="w-3 h-3" />
              </div>
              <button className="w-8 h-8 rounded-lg hover:bg-white/10 flex items-center justify-center text-text-primary smooth-transition">
                <Mic className="w-4 h-4" />
              </button>
              <button
                onClick={handleSubmit}
                disabled={isSimulating || !inputValue.trim()}
                className="w-8 h-8 rounded-lg bg-white/10 hover:bg-white/20 flex items-center justify-center text-white smooth-transition shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isSimulating ? (
                  <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                ) : (
                  <ArrowUp className="w-4 h-4" />
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
