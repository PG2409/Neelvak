import { useState, useRef, useEffect } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { Plus, MessageSquare, Layers, Settings, ChevronDown, Download, MoreVertical, Edit2, Copy, Archive, Trash2, Pin, FileOutput } from 'lucide-react'
import { useStore } from '../store'
import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export default function LeftSidebar() {
  const { chats, activeChatId, setActiveChatId, addChat, deleteChat, renameChat, duplicateChat, pinChat, archiveChat, logout, user } = useStore()
  const navigate = useNavigate()
  
  const [hoveredChat, setHoveredChat] = useState<string | null>(null)
  const [contextMenu, setContextMenu] = useState<{ id: string, x: number, y: number } | null>(null)
  
  const [renamingId, setRenamingId] = useState<string | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const [originalRenameValue, setOriginalRenameValue] = useState('')

  const [isProfileOpen, setIsProfileOpen] = useState(false)
  
  const menuRef = useRef<HTMLDivElement>(null)
  const profileMenuRef = useRef<HTMLDivElement>(null)
  const renameInputRef = useRef<HTMLInputElement>(null)

  // Click away listener for Context Menu & Profile Menu
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      const target = e.target as Node
      if (contextMenu && menuRef.current && !menuRef.current.contains(target)) {
        setContextMenu(null)
      }
      if (isProfileOpen && profileMenuRef.current && !profileMenuRef.current.contains(target)) {
        setIsProfileOpen(false)
      }
    }
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (contextMenu) setContextMenu(null)
        if (isProfileOpen) setIsProfileOpen(false)
      }
    }
    
    document.addEventListener('mousedown', handleClickOutside)
    document.addEventListener('keydown', handleEsc)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
      document.removeEventListener('keydown', handleEsc)
    }
  }, [contextMenu, isProfileOpen])

  // Focus input when renaming starts
  useEffect(() => {
    if (renamingId && renameInputRef.current) {
      renameInputRef.current.focus()
    }
  }, [renamingId])

  const openContextMenu = (e: React.MouseEvent, id: string) => {
    e.stopPropagation()
    e.preventDefault()
    setContextMenu({ id, x: e.clientX, y: e.clientY })
  }

  const handleRenameSave = () => {
    if (renamingId && renameValue.trim() && renameValue !== originalRenameValue) {
      renameChat(renamingId, renameValue.trim())
    }
    setRenamingId(null)
  }

  const handleRenameKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleRenameSave()
    } else if (e.key === 'Escape') {
      setRenameValue(originalRenameValue)
      setRenamingId(null)
    }
  }

  const handleSettingsClick = () => {
    setIsProfileOpen(false)
    navigate('/customize')
  }

  const unarchivedChats = chats.filter(c => !c.isArchived && !c.projectId)
  const pinnedChats = unarchivedChats.filter(c => c.isPinned)
  const recentChats = unarchivedChats.filter(c => !c.isPinned)

  return (
    <aside className="w-[260px] bg-bg-panels border-r border-border-color flex flex-col h-full shrink-0 z-20">
      {/* Brand Header */}
      <div className="p-4 flex items-center justify-between shrink-0 mb-2">
        <span className="font-semibold text-white text-base">Neelvak AIOS</span>
      </div>

      {/* Main Nav */}
      <nav className="px-3 space-y-1 shrink-0">
        <button 
          onClick={() => addChat()}
          className="w-full flex items-center gap-3 px-3 py-2 text-white hover:bg-white/5 rounded-md smooth-transition group"
        >
          <Plus className="w-4 h-4" />
          <span className="text-sm">New chat</span>
        </button>
        
        <NavLink 
          to="/chats" 
          onClick={() => {
            const current = chats.find(c => c.id === activeChatId);
            if (current?.projectId) {
              const firstGlobal = chats.find(c => !c.projectId && !c.isArchived);
              setActiveChatId(firstGlobal ? firstGlobal.id : null);
            }
          }}
          className={({isActive}) => cn("w-full flex items-center gap-3 px-3 py-2 rounded-md smooth-transition", isActive ? "text-white bg-white/10" : "text-text-primary hover:bg-white/5")}
        >
          <MessageSquare className="w-4 h-4" />
          <span className="text-sm">Chats</span>
        </NavLink>
        
        <NavLink to="/projects" className={({isActive}) => cn("w-full flex items-center gap-3 px-3 py-2 rounded-md smooth-transition", isActive ? "text-white bg-white/10" : "text-text-primary hover:bg-white/5")}>
          <Layers className="w-4 h-4" />
          <span className="text-sm">Projects</span>
        </NavLink>
        
        <NavLink to="/customize" className={({isActive}) => cn("w-full flex items-center gap-3 px-3 py-2 rounded-md smooth-transition", isActive ? "text-white bg-white/10" : "text-text-primary hover:bg-white/5")}>
          <Settings className="w-4 h-4" />
          <span className="text-sm">Customize</span>
        </NavLink>
      </nav>

      {/* Chat List Section */}
      <div className="mt-6 flex-1 flex flex-col overflow-hidden">
        
        <div className="flex-1 overflow-y-auto px-3 space-y-0.5 pb-4">
          
          {pinnedChats.length > 0 && (
            <div className="mb-4">
              <div className="px-2 pb-1.5 text-[11px] font-medium text-text-muted flex justify-between items-center shrink-0">
                <span>Pinned</span>
              </div>
              {pinnedChats.map(chat => (
                <ChatRow key={chat.id} chat={chat} />
              ))}
            </div>
          )}

          <div className="px-2 pb-1.5 text-[11px] font-medium text-text-muted flex justify-between items-center shrink-0">
            <span>Recents</span>
          </div>
          {recentChats.map(chat => (
            <ChatRow key={chat.id} chat={chat} />
          ))}

        </div>
      </div>

      {/* Profile Footer */}
      <div 
        ref={profileMenuRef}
        onClick={() => setIsProfileOpen(!isProfileOpen)}
        className="p-3 border-t border-border-color shrink-0 flex items-center justify-between cursor-pointer hover:bg-white/5 smooth-transition relative"
      >
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-slate-300 text-slate-800 font-semibold flex items-center justify-center text-sm uppercase">
            {user?.name.charAt(0)}
          </div>
          <div className="flex flex-col">
            <span className="text-[13px] font-medium text-white leading-tight">{user?.name}</span>
            <span className="text-[11px] text-text-muted leading-tight">{user?.plan}</span>
          </div>
        </div>
        <div className="flex items-center gap-2 text-text-muted">
          <Download className="w-3 h-3 hover:text-white" />
          <ChevronDown className="w-3 h-3 ml-1" />
        </div>
        
        {/* Dropdown */}
        {isProfileOpen && (
          <div className="absolute bottom-full left-2 right-2 mb-2 bg-bg-card border border-border-color rounded-lg shadow-xl z-50 flex flex-col p-1 animate-in fade-in zoom-in-95 duration-100">
            <button onClick={handleSettingsClick} className="text-left text-sm text-text-primary hover:bg-white/10 px-3 py-2 rounded-md">Settings</button>
            <button onClick={() => setIsProfileOpen(false)} className="text-left text-sm text-text-primary hover:bg-white/10 px-3 py-2 rounded-md">Export Data</button>
            <div className="h-px bg-border-color my-1"></div>
            <button onClick={() => { setIsProfileOpen(false); logout(); }} className="text-left text-sm text-red-400 hover:bg-white/10 px-3 py-2 rounded-md">Log out</button>
          </div>
        )}
      </div>

      {/* Context Menu Portal */}
      {contextMenu && (
        <div 
          ref={menuRef}
          className="fixed bg-bg-card border border-border-color rounded-lg shadow-2xl py-1 z-50 min-w-[160px] flex flex-col animate-in fade-in zoom-in-95 duration-100"
          style={{ top: Math.min(contextMenu.y, window.innerHeight - 250), left: contextMenu.x + 10 }}
        >
          <button 
            onClick={() => { 
              const c = chats.find(x => x.id === contextMenu.id); 
              setRenamingId(contextMenu.id); 
              setRenameValue(c?.title || ''); 
              setOriginalRenameValue(c?.title || '');
              setContextMenu(null); 
            }} 
            className="flex items-center gap-2 px-3 py-2 text-sm text-text-primary hover:bg-white/10 hover:text-white"
          >
            <Edit2 className="w-3.5 h-3.5" /> Rename
          </button>
          <button onClick={() => { duplicateChat(contextMenu.id); setContextMenu(null) }} className="flex items-center gap-2 px-3 py-2 text-sm text-text-primary hover:bg-white/10 hover:text-white">
            <Copy className="w-3.5 h-3.5" /> Duplicate
          </button>
          <button onClick={() => { pinChat(contextMenu.id); setContextMenu(null) }} className="flex items-center gap-2 px-3 py-2 text-sm text-text-primary hover:bg-white/10 hover:text-white">
            <Pin className="w-3.5 h-3.5" /> {chats.find(c => c.id === contextMenu.id)?.isPinned ? 'Unpin' : 'Pin'}
          </button>
          <button onClick={() => { archiveChat(contextMenu.id); setContextMenu(null) }} className="flex items-center gap-2 px-3 py-2 text-sm text-text-primary hover:bg-white/10 hover:text-white">
            <Archive className="w-3.5 h-3.5" /> Archive
          </button>
          <button onClick={() => setContextMenu(null)} className="flex items-center gap-2 px-3 py-2 text-sm text-text-primary hover:bg-white/10 hover:text-white">
            <FileOutput className="w-3.5 h-3.5" /> Export
          </button>
          <div className="h-px bg-border-color my-1"></div>
          <button onClick={() => { deleteChat(contextMenu.id); setContextMenu(null) }} className="flex items-center gap-2 px-3 py-2 text-sm text-red-400 hover:bg-white/10">
            <Trash2 className="w-3.5 h-3.5" /> Delete
          </button>
        </div>
      )}
    </aside>
  )

  // Internal component for Chat Row to avoid prop drilling in map
  function ChatRow({ chat }: { chat: any }) {
    if (renamingId === chat.id) {
      return (
        <div className="px-2 py-1.5 rounded-md bg-white/10 flex items-center">
          <input 
            ref={renameInputRef}
            type="text"
            value={renameValue}
            onChange={(e) => setRenameValue(e.target.value)}
            onKeyDown={handleRenameKeyDown}
            onBlur={handleRenameSave}
            className="w-full bg-transparent border-0 text-[13px] text-white focus:outline-none"
          />
        </div>
      )
    }

    return (
      <div 
        onClick={() => setActiveChatId(chat.id)}
        onMouseEnter={() => setHoveredChat(chat.id)}
        onMouseLeave={() => setHoveredChat(null)}
        className={cn(
          "px-2 py-1.5 rounded-md text-[13px] flex justify-between items-center cursor-pointer smooth-transition group relative",
          activeChatId === chat.id ? "bg-white/10 text-white font-medium" : "text-text-primary hover:bg-white/5"
        )}
      >
        <span className="truncate pr-2">{chat.title}</span>
        {(hoveredChat === chat.id || activeChatId === chat.id || contextMenu?.id === chat.id) && (
          <div className="flex items-center gap-1 shrink-0 bg-transparent" onClick={(e) => openContextMenu(e, chat.id)}>
            <MoreVertical className="w-3.5 h-3.5 text-text-muted hover:text-white cursor-pointer" />
          </div>
        )}
      </div>
    )
  }
}
