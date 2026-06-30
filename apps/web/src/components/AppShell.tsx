import {
  Download,
  Gauge,
  Home,
  Languages,
  PlaySquare,
  Settings,
  Upload,
} from 'lucide-react'
import { NavLink, Outlet, useParams } from 'react-router-dom'

function navClass({ isActive }: { isActive: boolean }) {
  return `inline-flex h-9 items-center gap-2 rounded-md px-3 text-sm font-medium transition ${
    isActive ? 'bg-accent text-white' : 'text-slate-700 hover:bg-slate-100'
  }`
}

export function AppShell() {
  const params = useParams()
  const projectId = params.projectId

  const projectLinks = projectId
    ? [
        { to: `/projects/${projectId}/progress`, label: '进度', icon: Gauge },
        { to: `/projects/${projectId}/proofread`, label: '校对', icon: Languages },
        { to: `/projects/${projectId}/preview`, label: '预览', icon: PlaySquare },
        { to: `/projects/${projectId}/downloads`, label: '下载', icon: Download },
      ]
    : []

  return (
    <div className="min-h-screen bg-slate-100">
      <header className="border-b border-line bg-white">
        <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 py-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-md bg-accent text-sm font-bold text-white">
              MS
            </div>
            <div>
              <div className="text-sm font-semibold text-ink">短剧多语种处理台</div>
              <div className="text-xs text-slate-500">字幕、配音、混音、打包</div>
            </div>
          </div>
          <nav className="flex flex-wrap gap-1">
            <NavLink className={navClass} to="/">
              <Home className="h-4 w-4" aria-hidden="true" />
              项目
            </NavLink>
            <NavLink className={navClass} to="/upload">
              <Upload className="h-4 w-4" aria-hidden="true" />
              上传
            </NavLink>
            {projectLinks.map((item) => {
              const Icon = item.icon
              return (
                <NavLink key={item.to} className={navClass} to={item.to}>
                  <Icon className="h-4 w-4" aria-hidden="true" />
                  {item.label}
                </NavLink>
              )
            })}
            <NavLink className={navClass} to="/skills">
              <Settings className="h-4 w-4" aria-hidden="true" />
              Skill
            </NavLink>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}
