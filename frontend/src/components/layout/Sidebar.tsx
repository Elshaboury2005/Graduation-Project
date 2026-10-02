import React from 'react';
import { NavLink } from 'react-router-dom';

export default function Sidebar() {
  const links = [
    { to: '/', label: 'Dashboard' },
    { to: '/pipelines', label: 'Pipelines' },
    { to: '/reliability', label: 'Reliability Testing' },
    { to: '/reports', label: 'Reports' },
  ];

  return (
    <aside className="w-64 bg-slate-800 border-r border-slate-700 min-h-screen flex flex-col">
      <div className="p-4 border-b border-slate-700">
        <h1 className="text-xl font-bold text-indigo-400">Resilient Big Data Platform</h1>
      </div>
      <nav className="flex-1 p-4 space-y-2">
        {links.map((link) => (
          <NavLink
            key={link.to}
            to={link.to}
            className={({ isActive }) =>
              `block px-4 py-2 rounded-md transition-colors ${
                isActive ? 'bg-indigo-600 text-white' : 'text-slate-300 hover:bg-slate-700'
              }`
            }
          >
            {link.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
