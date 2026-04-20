import React, { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { MessageBell } from "./MessageBell";
import logoImg from "../../assets/logo.png";

interface NavItem {
  label: string;
  path: string;
  icon: string;
}

function getNavItems(role: string): NavItem[] {
  const common: NavItem[] = [
    { label: "Dashboard", path: "/", icon: "grid" },
  ];

  switch (role) {
    case "patient":
      return [
        ...common,
        { label: "New Intake", path: "/intake", icon: "clipboard" },
        { label: "My Medical Record", path: "/my-record", icon: "record" },
      ];
    case "scheduler":
      return [
        ...common,
        { label: "Appointments", path: "/appointments", icon: "calendar" },
        { label: "Conflicts", path: "/conflicts", icon: "alert-triangle" },
        { label: "Priority Queue", path: "/priority", icon: "list" },
      ];
    case "physician":
      return [
        ...common,
        { label: "My Patients", path: "/appointments", icon: "users" },
      ];
    case "nurse":
      return [
        ...common,
        { label: "Schedule Overview", path: "/appointments", icon: "calendar" },
      ];
    default:
      return common;
  }
}

const iconMap: Record<string, React.ReactNode> = {
  grid: (
    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
    </svg>
  ),
  clipboard: (
    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
    </svg>
  ),
  calendar: (
    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
    </svg>
  ),
  "alert-triangle": (
    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4.5c-.77-.833-2.694-.833-3.464 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z" />
    </svg>
  ),
  list: (
    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 10h16M4 14h16M4 18h16" />
    </svg>
  ),
  record: (
    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
    </svg>
  ),
  users: (
    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
    </svg>
  ),
};

function roleBadgeColor(role: string): string {
  switch (role) {
    case "patient":   return "bg-blue-50 text-blue-700";
    case "scheduler": return "bg-sky-50 text-sky-700";
    case "nurse":     return "bg-violet-50 text-violet-700";
    case "physician": return "bg-indigo-50 text-indigo-700";
    case "admin":     return "bg-red-50 text-red-700";
    default:          return "bg-gray-100 text-gray-600";
  }
}


export default function Layout({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  if (!user) return null;

  const navItems = getNavItems(user.role);
  const pageTitle = navItems.find((n) => n.path === location.pathname)?.label ?? "Anilla";

  return (
    <div
      className="flex h-screen overflow-hidden"
      style={{
        background: "linear-gradient(160deg, #eaf6fb 0%, #d8eef7 50%, #cce8f4 100%)",
      }}
    >
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/20 backdrop-blur-sm lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-60 flex-col border-r border-white/50 bg-white/70 backdrop-blur-md transition-transform lg:static lg:translate-x-0 ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {/* Logo */}
        <div className="flex items-start border-b border-white/50 px-1 pt-1 pb-2">
          <img src={logoImg} alt="Anilla" className="h-16 w-auto object-contain" />
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-0.5">
          {navItems.map((item) => {
            const active = location.pathname === item.path;
            return (
              <Link
                key={item.path}
                to={item.path}
                onClick={() => setSidebarOpen(false)}
                className={`flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium transition-colors ${
                  active
                    ? "bg-gray-900 text-white shadow-sm"
                    : "text-gray-600 hover:bg-white/60 hover:text-gray-900"
                }`}
              >
                <span className={active ? "text-white" : "text-gray-400"}>
                  {iconMap[item.icon] ?? null}
                </span>
                {item.label}
              </Link>
            );
          })}
        </nav>

        {/* User section */}
        <div className="border-t border-white/50 p-4">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-blue-100 text-blue-700 text-xs font-semibold uppercase">
              {user.first_name[0]}{user.last_name[0]}
            </div>
            <div className="flex-1 min-w-0">
              <div className="truncate text-sm font-medium text-gray-900">
                {user.first_name} {user.last_name}
              </div>
              <span className={`inline-block mt-0.5 rounded-full px-2 py-0.5 text-xs font-medium capitalize ${roleBadgeColor(user.role)}`}>
                {user.role}
              </span>
            </div>
          </div>
        </div>
      </aside>

      {/* Main area */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Top header */}
        <header className="flex h-16 shrink-0 items-center justify-between border-b border-white/50 bg-white/60 px-4 backdrop-blur-md lg:px-6">
          <button
            onClick={() => setSidebarOpen(true)}
            className="rounded-xl p-2 text-gray-500 hover:bg-white/60 lg:hidden"
            aria-label="Open menu"
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>

          <div className="hidden lg:block">
            <h1 className="text-base font-semibold text-gray-800">{pageTitle}</h1>
          </div>

          <div className="flex items-center gap-3">
            {(user.role === "scheduler" || user.role === "nurse" || user.role === "physician") && (
              <MessageBell />
            )}
            <span className="hidden text-sm text-gray-500 sm:block">
              {user.first_name} {user.last_name}
            </span>
            <button
              onClick={logout}
              className="rounded-xl border border-gray-200/80 bg-white/60 px-4 py-1.5 text-sm font-medium text-gray-600 hover:bg-white/80 transition-colors"
            >
              Sign out
            </button>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto p-5 lg:p-8">{children}</main>
      </div>
    </div>
  );
}
