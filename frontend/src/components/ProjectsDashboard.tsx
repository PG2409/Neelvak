import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, Folder, LayoutGrid, Clock, MoreVertical, X } from 'lucide-react'
import { useStore } from '../store'

export default function ProjectsDashboard() {
  const { projects, setActiveProjectId, addProject } = useStore()
  const navigate = useNavigate()
  
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [newTitle, setNewTitle] = useState('')
  const [newDescription, setNewDescription] = useState('')

  const handleOpenProject = (id: string) => {
    setActiveProjectId(id)
    navigate(`/projects/${id}`)
  }

  const handleCreateProject = (e: React.FormEvent) => {
    e.preventDefault()
    if (newTitle.trim()) {
      addProject(newTitle.trim(), newDescription.trim())
      setNewTitle('')
      setNewDescription('')
      setIsModalOpen(false)
    }
  }

  return (
    <div className="flex-1 h-full bg-bg-main overflow-y-auto p-8 relative">
      <div className="max-w-6xl mx-auto">
        <header className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-semibold text-white mb-1">Projects</h1>
            <p className="text-sm text-text-muted">Manage your isolated workspaces and custom kernel deployments.</p>
          </div>
          <button 
            onClick={() => setIsModalOpen(true)}
            className="flex items-center gap-2 bg-white text-black px-4 py-2 rounded-lg text-sm font-medium hover:bg-slate-200 smooth-transition"
          >
            <Plus className="w-4 h-4" /> New Project
          </button>
        </header>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {projects.map(project => (
            <div 
              key={project.id}
              onClick={() => handleOpenProject(project.id)}
              className="group bg-bg-panels border border-border-color rounded-xl p-5 hover:border-white/20 hover:bg-white/[0.03] cursor-pointer smooth-transition flex flex-col h-48 relative"
            >
              <div className="flex items-start justify-between mb-3">
                <div className="w-10 h-10 rounded-lg bg-bg-main border border-border-color flex items-center justify-center text-text-muted group-hover:text-white smooth-transition">
                  <Folder className="w-5 h-5" />
                </div>
                <button className="text-text-muted hover:text-white p-1 rounded-md hover:bg-white/10 opacity-0 group-hover:opacity-100 smooth-transition" onClick={e => e.stopPropagation()}>
                  <MoreVertical className="w-4 h-4" />
                </button>
              </div>
              
              <h3 className="text-lg font-medium text-white mb-1">{project.title}</h3>
              <p className="text-sm text-text-muted line-clamp-2 flex-1">{project.description}</p>
              
              <div className="flex items-center justify-between mt-auto pt-4 border-t border-border-color/50 text-xs text-text-muted">
                <div className="flex items-center gap-1.5">
                  <LayoutGrid className="w-3.5 h-3.5" />
                  <span>Workspace Active</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <Clock className="w-3.5 h-3.5" />
                  <span>Updated just now</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Creation Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 animate-in fade-in duration-200">
          <div 
            className="bg-bg-panels border border-border-color rounded-2xl w-full max-w-md shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between p-5 border-b border-border-color">
              <h2 className="text-lg font-semibold text-white">Create New Project</h2>
              <button 
                onClick={() => setIsModalOpen(false)}
                className="text-text-muted hover:text-white p-1 rounded-md hover:bg-white/10 smooth-transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            
            <form onSubmit={handleCreateProject} className="p-5 flex flex-col gap-4">
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-medium text-text-primary">Project Title</label>
                <input 
                  autoFocus
                  type="text" 
                  value={newTitle}
                  onChange={e => setNewTitle(e.target.value)}
                  className="w-full bg-bg-main border border-border-color rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-accent-orange smooth-transition"
                  placeholder="e.g. Memory Optimization"
                  required
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-medium text-text-primary">Description</label>
                <textarea 
                  value={newDescription}
                  onChange={e => setNewDescription(e.target.value)}
                  className="w-full bg-bg-main border border-border-color rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-accent-orange smooth-transition resize-none"
                  placeholder="Briefly describe the purpose of this isolated workspace..."
                  rows={3}
                />
              </div>
              
              <div className="flex justify-end gap-3 mt-4">
                <button 
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 text-sm font-medium text-text-primary hover:text-white smooth-transition"
                >
                  Cancel
                </button>
                <button 
                  type="submit"
                  disabled={!newTitle.trim()}
                  className="bg-white text-black px-4 py-2 rounded-lg text-sm font-medium hover:bg-slate-200 smooth-transition disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Create Project
                </button>
              </div>
            </form>
          </div>
          <div className="absolute inset-0 -z-10" onClick={() => setIsModalOpen(false)}></div>
        </div>
      )}
    </div>
  )
}
