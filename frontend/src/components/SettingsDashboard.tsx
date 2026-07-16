import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Check, Settings, Save, Cpu, SlidersHorizontal } from 'lucide-react'
import { useStore, type AgentTask } from '../store'
import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export default function SettingsDashboard() {
  const { 
    preferences, updatePreference, 
    kernelMode, setKernelMode, 
    models, agentMappings, updateAgentMapping,
    isDirty, saveConfiguration
  } = useStore()
  
  const [showToast, setShowToast] = useState(false)

  const handleSave = () => {
    saveConfiguration()
    setShowToast(true)
    setTimeout(() => setShowToast(false), 3000)
  }

  const getModelFor = (task: AgentTask) => {
    return agentMappings.find(m => m.task === task)?.model || models[0]
  }

  const isAuto = kernelMode === 'auto'

  return (
    <div className="flex-1 h-full bg-bg-main overflow-y-auto relative pb-24">
      <div className="max-w-4xl mx-auto p-8">
        <header className="mb-8">
          <h1 className="text-2xl font-semibold text-white mb-2">Workspace Configuration</h1>
          <p className="text-sm text-text-muted">Manage your General Preferences, Model Registries, and Kernel Allocations.</p>
        </header>

        <div className="space-y-8">
          {/* Section 1: General */}
          <section className="bg-bg-panels border border-border-color rounded-2xl overflow-hidden">
            <div className="flex items-center gap-2 px-6 py-4 border-b border-border-color bg-white/[0.02]">
              <Settings className="w-4 h-4 text-text-muted" />
              <h2 className="text-sm font-medium text-white">General Preferences</h2>
            </div>
            <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-6">
              
              <div className="flex flex-col gap-2">
                <label className="text-xs font-medium text-text-primary">System Theme</label>
                <select 
                  value={preferences.theme}
                  onChange={e => updatePreference('theme', e.target.value as any)}
                  className="bg-bg-main border border-border-color rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-accent-orange smooth-transition"
                >
                  <option value="system">System Default</option>
                  <option value="dark">Charcoal Dark</option>
                  <option value="light">Light Mode</option>
                </select>
              </div>

              <div className="flex flex-col gap-2">
                <label className="text-xs font-medium text-text-primary">Language</label>
                <select 
                  value={preferences.language}
                  onChange={e => updatePreference('language', e.target.value)}
                  className="bg-bg-main border border-border-color rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-accent-orange smooth-transition"
                >
                  <option value="English">English</option>
                  <option value="Spanish">Español</option>
                  <option value="French">Français</option>
                  <option value="German">Deutsch</option>
                </select>
              </div>

              <div className="flex flex-col gap-2">
                <label className="text-xs font-medium text-text-primary">Text Density</label>
                <select 
                  value={preferences.textDensity}
                  onChange={e => updatePreference('textDensity', e.target.value as any)}
                  className="bg-bg-main border border-border-color rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-accent-orange smooth-transition"
                >
                  <option value="compact">Compact</option>
                  <option value="comfortable">Comfortable</option>
                  <option value="loose">Loose</option>
                </select>
              </div>

              <div className="flex items-center justify-between p-3 bg-bg-main border border-border-color rounded-lg mt-6 h-[38px]">
                <span className="text-xs font-medium text-text-primary">UI Animations</span>
                <button 
                  onClick={() => updatePreference('animations', !preferences.animations)}
                  className={cn(
                    "w-8 h-4 rounded-full relative smooth-transition",
                    preferences.animations ? "bg-accent-orange" : "bg-white/10"
                  )}
                >
                  <div className={cn(
                    "absolute top-0.5 w-3 h-3 bg-white rounded-full smooth-transition",
                    preferences.animations ? "left-[18px]" : "left-0.5"
                  )} />
                </button>
              </div>
            </div>
          </section>

          {/* Section 2 & 3: Master Switch & Registries */}
          <section className="bg-bg-panels border border-border-color rounded-2xl overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b border-border-color bg-white/[0.02]">
              <div className="flex items-center gap-2">
                <SlidersHorizontal className="w-4 h-4 text-text-muted" />
                <h2 className="text-sm font-medium text-white">Kernel Allocations System</h2>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-xs text-text-muted font-medium">Override Kernel Configuration</span>
                <button 
                  onClick={() => setKernelMode(isAuto ? 'manual' : 'auto')}
                  className={cn(
                    "w-10 h-5 rounded-full relative smooth-transition",
                    !isAuto ? "bg-accent-orange" : "bg-white/10"
                  )}
                >
                  <div className={cn(
                    "absolute top-0.5 w-4 h-4 bg-white rounded-full smooth-transition",
                    !isAuto ? "left-[22px]" : "left-0.5"
                  )} />
                </button>
              </div>
            </div>

            <div className="p-6">
              <div className="flex items-center gap-2 mb-6 text-text-muted">
                <Cpu className="w-4 h-4" />
                <h3 className="text-sm font-medium">Model Registries</h3>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {[
                  { label: 'Default Chat Model', task: 'Execution Agent' as AgentTask },
                  { label: 'Planner Model', task: 'Planner Agent' as AgentTask },
                  { label: 'Compiler Model', task: 'Compiler Agent' as AgentTask },
                  { label: 'Verification Model', task: 'Verification Agent' as AgentTask },
                ].map(item => (
                  <div key={item.label} className="flex flex-col gap-2">
                    <label className="text-xs font-medium text-text-primary flex justify-between">
                      {item.label}
                      {isAuto && <span className="text-[10px] text-accent-orange">Auto-Assigned</span>}
                    </label>
                    <select 
                      value={getModelFor(item.task)}
                      onChange={e => updateAgentMapping(item.task, e.target.value)}
                      disabled={isAuto}
                      className={cn(
                        "bg-bg-main border border-border-color rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-accent-orange smooth-transition",
                        isAuto && "opacity-50 pointer-events-none"
                      )}
                    >
                      {models.map(m => (
                        <option key={m} value={m}>{m}</option>
                      ))}
                    </select>
                  </div>
                ))}
              </div>

            </div>
          </section>

        </div>
      </div>

      {/* Persistent Footer */}
      <div className="fixed bottom-0 left-[260px] right-0 h-16 bg-bg-panels border-t border-border-color flex items-center justify-end px-8 z-30 shadow-2xl">
        <button 
          onClick={handleSave}
          disabled={!isDirty}
          className="flex items-center gap-2 bg-white text-black px-5 py-2 rounded-lg text-sm font-medium hover:bg-slate-200 smooth-transition disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Save className="w-4 h-4" />
          Save Configuration
        </button>
      </div>

      {/* Toast Notification */}
      <AnimatePresence>
        {showToast && (
          <motion.div
            initial={{ opacity: 0, y: 50, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.95 }}
            className="fixed bottom-24 right-8 bg-emerald-500 text-white px-4 py-3 rounded-xl shadow-2xl flex items-center gap-3 z-50 font-medium text-sm border border-emerald-400"
          >
            <div className="w-6 h-6 bg-white/20 rounded-full flex items-center justify-center">
              <Check className="w-4 h-4" />
            </div>
            System Kernel Configurations Saved Successfully
          </motion.div>
        )}
      </AnimatePresence>

    </div>
  )
}
