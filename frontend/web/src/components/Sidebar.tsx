"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";

const navItems = [
  { href: "/", label: "Главная", icon: "🏠" },
  { href: "/profile", label: "Профиль", icon: "👤" },
  { href: "/vacancies", label: "Вакансии", icon: "💼" },
  { href: "/documents", label: "Документы", icon: "📄" },
  { href: "/applications", label: "Отклики", icon: "📋" },
  { href: "/interview", label: "Интервью", icon: "🎤" },
  { href: "/consent", label: "Согласия", icon: "🔐" },
];

export default function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  return (
    <aside className="w-64 bg-white border-r border-gray-200 flex flex-col">
      <div className="p-4 border-b border-gray-200">
        <h1 className="text-lg font-bold text-blue-600">Career Copilot</h1>
        <p className="text-xs text-gray-500">AI assistant for HH</p>
      </div>

      <nav className="flex-1 p-4 space-y-1">
        {navItems.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
              pathname === item.href
                ? "bg-blue-50 text-blue-700 font-medium"
                : "text-gray-600 hover:bg-gray-100"
            }`}
          >
            <span>{item.icon}</span>
            <span>{item.label}</span>
          </Link>
        ))}
      </nav>

      <div className="p-4 border-t border-gray-200">
        <p className="text-xs text-gray-500 truncate">{user?.email}</p>
        <button
          onClick={logout}
          className="mt-2 w-full text-left text-sm text-red-600 hover:text-red-800"
        >
          Выйти
        </button>
      </div>
    </aside>
  );
}
