
import { Outlet } from 'react-router-dom'
import LeftSidebar from './LeftSidebar'
import RightSidebar from './RightSidebar'
import LoginPortal from './LoginPortal'
import { useStore } from '../store'

export default function Layout() {
  const isAuthenticated = useStore(state => state.isAuthenticated)

  if (!isAuthenticated) {
    return <LoginPortal />
  }

  return (
    <div className="h-screen w-full overflow-hidden flex bg-bg-main bg-magenta-gradient text-sm antialiased">
      <LeftSidebar />
      <main className="flex-1 flex flex-col relative h-full overflow-hidden z-0">
        <Outlet />
      </main>
      <RightSidebar />
    </div>
  )
}
