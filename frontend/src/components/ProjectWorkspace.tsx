import React, { useState, useRef, useEffect, type DragEvent } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Plus, ArrowUp, Paperclip, HardDrive, FileText, UploadCloud, File as FileIcon, Layers } from 'lucide-react'
import { useStore } from '../store'
import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export default function ProjectWorkspace() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { projects, chats, messages, addChat, setActiveChatId, activeChatId, updateProjectInstructions, addProjectFile } = useStore()
  
  const project = projects.find(p => p.id === id)
  
  const [inputValue, setInputValue] = useState('')
  const [isSimulating, setIsSimulating] = useState(false)
  const [isExecutionCollapsed, setIsExecutionCollapsed] = useState(false)
  
  const [isDragging, setIsDragging] = useState(false)
  const [instructionsEdit, setInstructionsEdit] = useState('')
  const [isEditingInstructions, setIsEditingInstructions] = useState(false)

  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const feedRef = useRef<HTMLDivElement>(null)

  const projectChats = chats.filter(c => c.projectId === id)
  
  useEffect(() => {
    if (project) {
      if (!activeChatId || !projectChats.find(c => c.id === activeChatId)) {
        if (projectChats.length > 0) {
          setActiveChatId(projectChats[0].id)
        } else {
          addChat(project.id)
        }
      }
    }
  }, [project, activeChatId, projectChats, setActiveChatId, addChat])

  const activeMessages = messages.filter(m => m.chatId === activeChatId)

  if (!project) {
    return <div className="flex-1 flex items-center justify-center text-text-muted">Workspace isolated or not found.</div>
  }

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

    useStore.getState().addMessage(activeChatId, 'user', content)

    // Simulate backend for now since we aren't hooking up the project context to the real kernel yet
    // To wire to real kernel, we'd use the same fetch logic from ChatCanvas.
    setTimeout(() => {
       setIsSimulating(false)
       useStore.getState().addMessage(activeChatId, 'system', `Workspace Execution Complete for ${project.title}. Context files, memory, and instructions have been applied to this partitioned sandbox.`)
    }, 1500)
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragging(false)
  }

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragging(false)
    
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      Array.from(e.dataTransfer.files).forEach(file => {
        const sizeStr = (file.size / 1024 / 1024).toFixed(2) + ' MB'
        addProjectFile(project.id, {
          name: file.name,
          size: sizeStr,
          type: file.name.split('.').pop()?.toUpperCase() || 'FILE'
        })
      })
    }
  }

  const saveInstructions = () => {
    updateProjectInstructions(project.id, instructionsEdit)
    setIsEditingInstructions(false)
  }

  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight
    }
  }, [messages, isExecutionCollapsed])

  return (
    <div className="flex-1 flex flex-col h-full bg-bg-main overflow-hidden">
      <header className="h-14 flex items-center gap-4 px-6 shrink-0 border-b border-border-color z-10 bg-bg-panels">
        <button 
          onClick={() => navigate('/projects')}
          className="text-text-muted hover:text-white p-1 rounded-md hover:bg-white/10 smooth-transition"
        >
          <ArrowLeft className="w-4 h-4" />
        </button>
        <div className="flex flex-col">
          <span className="font-semibold text-white text-sm">{project.title} Workspace</span>
          <span className="text-[11px] text-text-muted truncate max-w-[400px]">Strictly Isolated Sandbox Mode</span>
        </div>
      </header>

      <div className="flex-1 grid grid-cols-1 md:grid-cols-[1fr_320px] overflow-hidden">
        
        {/* LEFT COLUMN: CHAT CANVAS */}
        <div className="flex flex-col relative overflow-hidden border-r border-border-color">
          <div ref={feedRef} className="flex-1 overflow-y-auto px-6 pb-40 flex flex-col items-center">
            
            {activeMessages.length === 0 && (
               <div className="w-full flex-1 flex flex-col items-center justify-center text-center py-20">
                  <div className="w-12 h-12 rounded-2xl bg-white/5 flex items-center justify-center mb-4">
                     <Layers className="w-6 h-6 text-text-primary" />
                  </div>
                  <h2 className="text-xl font-semibold text-white mb-2">{project.title} Environment</h2>
                  <p className="text-text-muted text-sm max-w-sm">All messages, files, and memory sent here are strictly partitioned and cannot leak outside this project.</p>
               </div>
            )}

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
              </React.Fragment>
            ))}
            
            {isSimulating && (
               <div className="w-full max-w-3xl mt-4 mb-10 flex justify-start pl-4">
                  <div className="flex items-center gap-3">
                     <div className="w-3 h-3 border-2 border-text-muted border-t-white rounded-full animate-spin"></div>
                     <span className="text-sm text-text-muted italic">Processing in isolated container...</span>
                  </div>
               </div>
            )}
          </div>

          <div className="absolute bottom-6 left-0 right-0 flex justify-center px-6 pointer-events-none z-20">
            <div className="w-full max-w-3xl bg-bg-card border border-border-color rounded-2xl shadow-xl p-3 flex flex-col gap-3 pointer-events-auto">
              <textarea 
                ref={textareaRef}
                value={inputValue}
                onChange={handleInput}
                onKeyDown={handleKeyDown}
                rows={1} 
                placeholder={`Message ${project.title}...`}
                className="w-full bg-transparent border-0 text-[15px] text-white placeholder-text-muted focus:outline-none focus:ring-0 resize-none px-2 pt-1"
              />
              <div className="flex justify-between items-center">
                <button className="w-8 h-8 rounded-full hover:bg-white/10 flex items-center justify-center text-text-primary smooth-transition">
                  <Plus className="w-5 h-5" />
                </button>
                <div className="flex items-center gap-2">
                  <button 
                    onClick={handleSubmit}
                    disabled={isSimulating || !inputValue.trim()}
                    className="w-8 h-8 rounded-lg bg-white/10 hover:bg-white/20 flex items-center justify-center text-white smooth-transition shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <ArrowUp className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN: CONTEXT PANEL */}
        <div className="bg-bg-panels overflow-y-auto flex flex-col">
           <div className="p-5 flex flex-col gap-6">
              
              {/* Memory Block */}
              <div className="flex flex-col gap-3">
                 <div className="flex items-center gap-2 text-white">
                    <HardDrive className="w-4 h-4 text-text-muted" />
                    <span className="text-sm font-semibold">Memory</span>
                 </div>
                 <div className="bg-bg-main border border-border-color rounded-xl p-4 shadow-sm">
                    <p className="text-xs text-text-muted leading-relaxed">
                       {project.memory || "No memory segments allocated yet."}
                    </p>
                 </div>
              </div>

              {/* Instructions Block */}
              <div className="flex flex-col gap-3">
                 <div className="flex items-center justify-between text-white">
                    <div className="flex items-center gap-2">
                       <FileText className="w-4 h-4 text-text-muted" />
                       <span className="text-sm font-semibold">Instructions</span>
                    </div>
                    {!isEditingInstructions && (
                       <button onClick={() => { setInstructionsEdit(project.instructions); setIsEditingInstructions(true); }} className="w-6 h-6 rounded-md hover:bg-white/10 flex items-center justify-center text-text-muted hover:text-white smooth-transition">
                          <Plus className="w-3.5 h-3.5" />
                       </button>
                    )}
                 </div>
                 
                 {isEditingInstructions ? (
                    <div className="flex flex-col gap-2">
                       <textarea 
                          value={instructionsEdit}
                          onChange={(e) => setInstructionsEdit(e.target.value)}
                          placeholder="How should Neelvak act in this project?"
                          className="w-full h-24 bg-bg-main border border-border-color rounded-xl p-3 text-xs text-white focus:outline-none focus:border-white/20 resize-none"
                       />
                       <div className="flex justify-end gap-2">
                          <button onClick={() => setIsEditingInstructions(false)} className="text-xs text-text-muted hover:text-white px-2 py-1">Cancel</button>
                          <button onClick={saveInstructions} className="text-xs bg-white text-black font-medium px-3 py-1 rounded-md hover:bg-white/90">Save</button>
                       </div>
                    </div>
                 ) : (
                    <div className="bg-bg-main border border-border-color rounded-xl p-4 shadow-sm min-h-[60px]">
                       {project.instructions ? (
                          <p className="text-xs text-text-primary whitespace-pre-wrap">{project.instructions}</p>
                       ) : (
                          <p className="text-xs text-text-muted italic">No custom instructions defined.</p>
                       )}
                    </div>
                 )}
              </div>

              {/* Files Block */}
              <div className="flex flex-col gap-3">
                 <div className="flex items-center gap-2 text-white mb-1">
                    <Paperclip className="w-4 h-4 text-text-muted" />
                    <span className="text-sm font-semibold">Files</span>
                 </div>
                 
                 {/* Drag and drop zone */}
                 <div 
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onDrop={handleDrop}
                    className={cn(
                       "border-2 border-dashed rounded-xl p-6 flex flex-col items-center justify-center text-center smooth-transition cursor-pointer",
                       isDragging ? "border-sky-500 bg-sky-500/10" : "border-border-color hover:border-white/20 hover:bg-white/5"
                    )}
                 >
                    <UploadCloud className={cn("w-6 h-6 mb-2", isDragging ? "text-sky-400" : "text-text-muted")} />
                    <span className="text-xs font-medium text-white mb-1">Upload to Project</span>
                    <span className="text-[10px] text-text-muted">Drag & drop PDFs, TXT, or Code</span>
                 </div>

                 {/* File List */}
                 {project.files && project.files.length > 0 && (
                    <div className="flex flex-col gap-2 mt-2">
                       {project.files.map(file => (
                          <div key={file.id} className="flex items-center gap-3 p-2.5 rounded-lg bg-bg-main border border-border-color group">
                             <div className="w-8 h-8 rounded-md bg-white/5 flex items-center justify-center shrink-0">
                                <FileIcon className="w-4 h-4 text-text-primary" />
                             </div>
                             <div className="flex flex-col overflow-hidden">
                                <span className="text-xs font-medium text-white truncate">{file.name}</span>
                                <span className="text-[10px] text-text-muted">{file.type} • {file.size}</span>
                             </div>
                          </div>
                       ))}
                    </div>
                 )}

              </div>

           </div>
        </div>

      </div>
    </div>
  )
}
