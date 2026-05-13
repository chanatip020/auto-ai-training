import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom';
import { clearToken, isAuthed } from '../lib/auth';

const navItems = [
  { to: '/', label: 'Dashboard' },
  { to: '/projects/new', label: 'New project' },
  { to: '/settings', label: 'Settings' },
];

export function AppShell() {
  const navigate = useNavigate();
  const onLogout = () => {
    clearToken();
    navigate('/login');
  };

  return (
    <div className="flex h-screen overflow-hidden">
      <aside className="hidden w-56 shrink-0 flex-col border-r border-slate-200 bg-white md:flex">
        <div className="border-b border-slate-200 px-4 py-4">
          <Link to="/" className="text-sm font-semibold text-slate-900">
            AI Auto Training
          </Link>
          <div className="mt-0.5 text-[10px] uppercase tracking-wider text-slate-400">
            v0.1
          </div>
        </div>
        <nav className="flex-1 space-y-0.5 px-2 py-3">
          {navItems.map((it) => (
            <NavLink
              key={it.to}
              to={it.to}
              end
              className={({ isActive }) =>
                'block rounded-md px-3 py-1.5 text-sm transition ' +
                (isActive
                  ? 'bg-blue-50 text-blue-700'
                  : 'text-slate-700 hover:bg-slate-100')
              }
            >
              {it.label}
            </NavLink>
          ))}
        </nav>
        {isAuthed() && (
          <button
            onClick={onLogout}
            className="border-t border-slate-200 px-4 py-3 text-left text-xs text-slate-500 hover:bg-slate-50"
          >
            Sign out
          </button>
        )}
      </aside>
      <main className="flex-1 overflow-y-auto px-6 py-8">
        <div className="mx-auto max-w-6xl">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
