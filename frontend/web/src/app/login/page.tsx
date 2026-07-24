"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Logo } from "@/components/Logo";
import { Mail, Lock, Sparkles, AlertCircle, FileSearch, BarChart3, ShieldCheck, ArrowRight } from "lucide-react";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password);
      router.replace("/profile");
    } catch (err: any) {
      setError(err.message || "Ошибка входа");
    } finally {
      setLoading(false);
    }
  };

  const handleOAuth = async (provider: "google" | "github") => {
    try {
      const res = await api.oauthAuthorize(provider);
      localStorage.setItem("oauth_state", res.state);
      window.location.href = res.auth_url;
    } catch (err: any) {
      setError(err.message || "Ошибка OAuth");
    }
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-[1.1fr_1fr] bg-background">
      {/* Hero — «припыленная» warm gray + sage. */}
      <aside className="relative hidden lg:flex flex-col justify-between p-12 overflow-hidden bg-gradient-to-br from-stone-50 via-stone-50/80 to-stone-100 dark:from-stone-950 dark:via-background dark:to-stone-900/40">
        {/* Mesh-gradient blobs (3 тёплых серо-зелёных). */}
        <div
          aria-hidden
          className="pointer-events-none absolute -top-40 -left-40 w-[600px] h-[600px] rounded-full bg-stone-300/40 dark:bg-stone-600/20 blur-3xl animate-[pulse_8s_ease-in-out_infinite]"
        />
        <div
          aria-hidden
          className="pointer-events-none absolute top-1/3 -right-32 w-[500px] h-[500px] rounded-full bg-stone-400/30 dark:bg-stone-500/15 blur-3xl animate-[pulse_10s_ease-in-out_infinite_2s]"
        />
        <div
          aria-hidden
          className="pointer-events-none absolute -bottom-32 left-1/4 w-[550px] h-[550px] rounded-full bg-stone-300/25 dark:bg-stone-600/10 blur-3xl animate-[pulse_12s_ease-in-out_infinite_4s]"
        />
        {/* Subtle grid pattern (тёплые серые точки). */}
        <div
          aria-hidden
          className="absolute inset-0 bg-[radial-gradient(circle_at_1px_1px,rgba(68,64,60,0.06)_1px,transparent_0)] dark:bg-[radial-gradient(circle_at_1px_1px,rgba(255,255,255,0.05)_1px,transparent_0)] [background-size:24px_24px]"
        />

        {/* Header */}
        <div className="relative z-10 flex items-center gap-2">
          <Logo size={32} withWordmark />
        </div>

        {/* Main content */}
        <div className="relative z-10 space-y-8 max-w-lg">
          {/* Trust badge — честный, без чисел. */}
          <div className="inline-flex items-center gap-2 rounded-full border border-stone-200 bg-white/90 backdrop-blur-sm px-3 py-1 text-xs font-medium shadow-sm">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-stone-400 opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-stone-500" />
            </span>
            <span className="text-stone-700">Используется кандидатами для подготовки к собеседованиям</span>
          </div>

          <div className="space-y-4">
            <h1 className="text-5xl font-bold tracking-tight leading-[1.05] text-stone-900">
              <span className="bg-gradient-to-br from-stone-700 via-stone-600 to-stone-500 bg-clip-text text-transparent">
                Резюме и письма,
              </span>
              <br />
              которые доходят
              <br />
              до интервью
            </h1>
            <p className="text-lg text-stone-600 leading-relaxed max-w-md">
              AI собирает профиль из GitHub и резюме, адаптирует под вакансию
              и проверяет каждый факт — без выдуманных достижений.
            </p>
          </div>

          <ul className="space-y-4">
            <li className="flex items-start gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-stone-800 text-white shadow-sm shrink-0">
                <FileSearch className="size-4" />
              </div>
              <div>
                <p className="text-sm font-medium text-stone-900">Импорт профиля из GitHub</p>
                <p className="text-xs text-stone-600">
                  Репозитории, README, технологии — автоматически в профиль
                </p>
              </div>
            </li>
            <li className="flex items-start gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-stone-700 text-white shadow-sm shrink-0">
                <BarChart3 className="size-4" />
              </div>
              <div>
                <p className="text-sm font-medium text-stone-900">Адаптация под вакансию</p>
                <p className="text-xs text-stone-600">
                  Сопроводительное письмо с подсветкой совпадений
                </p>
              </div>
            </li>
            <li className="flex items-start gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-stone-700 to-stone-600 text-white shadow-sm shrink-0">
                <ShieldCheck className="size-4" />
              </div>
              <div>
                <p className="text-sm font-medium text-stone-900">Факт-чекинг достижений</p>
                <p className="text-xs text-stone-600">
                  Каждое утверждение можно подтвердить или удалить
                </p>
              </div>
            </li>
          </ul>
        </div>

        {/* Footer */}
        <p className="relative z-10 text-xs text-stone-500">
          152-ФЗ · данные хранятся в РФ · резервные копии ежедневно
        </p>
      </aside>

      {/* Form */}
      <main className="flex items-center justify-center p-6 lg:p-12 bg-background">
        <div className="w-full max-w-md space-y-6">
          {/* Mobile logo */}
          <div className="flex items-center gap-2 lg:hidden">
            <Logo size={28} withWordmark />
          </div>

          <div className="space-y-2">
            <h2 className="text-3xl font-bold tracking-tight text-stone-900">С возвращением</h2>
            <p className="text-sm text-stone-600">
              Войдите, чтобы продолжить работу с профилем
            </p>
          </div>

          {error && (
            <Alert variant="destructive" className="animate-in fade-in slide-in-from-top-1">
              <AlertCircle />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {/* OAuth */}
          <div className="grid grid-cols-2 gap-3">
            <Button
              type="button"
              variant="outline"
              onClick={() => handleOAuth("google")}
              className="w-full"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24" aria-hidden>
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" />
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
              </svg>
              Google
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => handleOAuth("github")}
              className="w-full"
            >
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24" aria-hidden>
                <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
              </svg>
              GitHub
            </Button>
          </div>

          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-stone-200" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="px-2 bg-background text-stone-500">или email</span>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email" className="text-stone-700">Email</Label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-stone-400 pointer-events-none" />
                <Input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  placeholder="you@example.com"
                  className="pl-9 h-10 border-stone-200 focus-visible:ring-stone-400"
                />
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label htmlFor="password" className="text-stone-700">Пароль</Label>
                <Link
                  href="/forgot-password"
                  className="text-xs text-stone-500 hover:text-stone-800 transition-colors"
                >
                  Забыли пароль?
                </Link>
              </div>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-stone-400 pointer-events-none" />
                <Input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  placeholder="••••••••"
                  className="pl-9 h-10 border-stone-200 focus-visible:ring-stone-400"
                />
              </div>
            </div>

            <Button
              type="submit"
              disabled={loading}
              className="w-full h-10 bg-stone-800 hover:bg-stone-900 text-white shadow-sm hover:shadow-md transition-all"
            >
              <Sparkles className="size-4" />
              {loading ? "Входим..." : "Войти"}
              {!loading && <ArrowRight className="size-4 ml-auto" />}
            </Button>
          </form>

          <p className="text-center text-sm text-stone-600">
            Нет аккаунта?{" "}
            <Link
              href="/register"
              className="font-medium text-stone-800 hover:text-stone-900 underline-offset-4 hover:underline transition-colors"
            >
              Зарегистрироваться
            </Link>
          </p>
        </div>
      </main>
    </div>
  );
}
