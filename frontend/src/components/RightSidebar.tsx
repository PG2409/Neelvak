
import { useStore, type AgentTask } from '../store'
import { Archive, Network, Shield, Wrench, Settings2, Cpu, FileCheck2, Clock, TerminalSquare } from 'lucide-react'
import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

const AGENT_META: Record<AgentTask, { icon: React.ReactNode, path: string, color: string }> = {
  'Planner Agent': { icon: <Network className="w-3 h-3" />, path: 'compiler/planner.py', color: 'text-blue-400' },
  'Policy Agent': { icon: <Shield className="w-3 h-3" />, path: 'compiler/policy.py', color: 'text-emerald-400' },
  'Tool Manager': { icon: <Wrench className="w-3 h-3" />, path: 'runtime/tool_manager.py', color: 'text-amber-400' },
  'Memory Agent': { icon: <Settings2 className="w-3 h-3" />, path: 'memory/manager.py', color: 'text-sky-400' },
  'RAG Agent': { icon: <Archive className="w-3 h-3" />, path: 'memory/context.py', color: 'text-purple-400' },
  'Execution Agent': { icon: <Cpu className="w-3 h-3" />, path: 'runtime/execution.py', color: 'text-orange-400' },
  'Verification Agent': { icon: <FileCheck2 className="w-3 h-3" />, path: 'compiler/verify.py', color: 'text-teal-400' },
  'Runtime Scheduler': { icon: <Clock className="w-3 h-3" />, path: 'runtime/scheduler.py', color: 'text-indigo-400' },
  'Compiler Agent': { icon: <TerminalSquare className="w-3 h-3" />, path: 'compiler/compiler.py', color: 'text-pink-400' }
}

export default function RightSidebar() {
  const { 
    activeRightTab, setActiveRightTab, 
    kernelMode, setKernelMode, 
    agentMappings, updateAgentMapping, 
    models, isDirty, saveConfiguration, resetConfiguration 
  } = useStore()

  const isManual = kernelMode !== 'auto'

  const handleSave = () => {
    saveConfiguration()
    // Simulated toast could go here
    alert("Configuration Saved to Global State")
  }

  return (
    <aside className="w-[320px] bg-bg-panels border-l border-border-color flex flex-col h-full shrink-0 z-20 shadow-2xl">
      {/* Tabs */}
      <div className="flex border-b border-border-color px-2 pt-2 shrink-0">
        <button 
          onClick={() => setActiveRightTab('content')}
          className={cn("px-4 py-2.5 text-sm font-medium smooth-transition", activeRightTab === 'content' ? "text-white border-b-2 border-white" : "text-text-muted border-b-2 border-transparent hover:text-text-primary")}
        >
          Content
        </button>
        <button 
          onClick={() => setActiveRightTab('agent')}
          className={cn("px-4 py-2.5 text-sm font-medium smooth-transition", activeRightTab === 'agent' ? "text-white border-b-2 border-white" : "text-text-muted border-b-2 border-transparent hover:text-text-primary")}
        >
          Agent Architecture
        </button>
      </div>

      {/* Tab 1: Content */}
      {activeRightTab === 'content' && (
        <div className="flex-1 p-4 overflow-y-auto">
          <div className="w-[120px] h-[120px] bg-bg-card border border-border-color rounded-xl p-3 flex flex-col justify-between cursor-pointer hover:border-white/20 smooth-transition">
            <span className="text-white text-xs font-medium truncate">neelvak.zip</span>
            <span className="text-[9px] font-mono text-text-muted border border-border-color px-1.5 py-0.5 rounded w-max">ZIP</span>
          </div>
        </div>
      )}

      {/* Tab 2: Agent Architecture */}
      {activeRightTab === 'agent' && (
        <div className="flex-1 p-4 overflow-y-auto flex flex-col gap-5">
          {/* Kernel Override Switch */}
          <div className="bg-bg-card border border-border-color rounded-xl p-4 flex flex-col gap-3">
            <div className="flex justify-between items-start">
              <div className="flex flex-col gap-1">
                <span className="text-white text-sm font-medium leading-tight">Kernel Control</span>
                <span className={cn("text-xs leading-tight transition-colors", isManual ? "text-accent-orange" : "text-text-muted")}>
                  {isManual ? "Manual Override Enabled (Constraints bypassed)" : "Auto-Allocation Enabled (Based on structure)"}
                </span>
              </div>
              <label className="relative inline-flex items-center cursor-pointer mt-0.5 shrink-0">
                <input 
                  type="checkbox" 
                  className="sr-only peer" 
                  checked={isManual}
                  onChange={(e) => setKernelMode(e.target.checked ? 'manual' : 'auto')}
                />
                <div className="w-9 h-5 bg-black/50 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-accent-orange"></div>
              </label>
            </div>
          </div>

          {/* Action Bar */}
          <div className="flex justify-between items-center px-1">
            <span className="text-xs font-medium text-white">Agent Mapping Matrix</span>
            <div className="flex gap-2">
              <button onClick={resetConfiguration} className="text-[10px] text-text-muted hover:text-white smooth-transition">Reset</button>
              {isDirty && (
                <button onClick={handleSave} className="text-[10px] bg-accent-orange text-white px-2 py-0.5 rounded smooth-transition hover:bg-orange-600">Save</button>
              )}
            </div>
          </div>
          
          {/* Agent Matrix Forms */}
          <div className="flex flex-col gap-3 pb-8">
            {agentMappings.map(mapping => (
              <div key={mapping.task} className={cn("bg-bg-main border border-border-color rounded-lg p-3 flex flex-col gap-2 smooth-transition", !isManual && "opacity-50 pointer-events-none")}>
                <div className="flex justify-between items-center">
                  <span className="text-xs font-semibold text-white flex items-center gap-1.5">
                    <span className={AGENT_META[mapping.task]?.color}>{AGENT_META[mapping.task]?.icon}</span>
                    {mapping.task}
                  </span>
                  <span className="text-[9px] text-text-muted bg-white/5 px-1.5 py-0.5 rounded border border-border-color">
                    {AGENT_META[mapping.task]?.path}
                  </span>
                </div>
                <select 
                  value={mapping.model}
                  onChange={(e) => updateAgentMapping(mapping.task, e.target.value)}
                  disabled={!isManual}
                  className="w-full bg-bg-card border border-border-color text-text-primary text-xs rounded p-1.5 focus:outline-none focus:border-accent-orange disabled:opacity-70"
                >
                  {models.map(m => <option key={m} value={m}>{m}</option>)}
                </select>
              </div>
            ))}
          </div>
        </div>
      )}
    </aside>
  )
}
