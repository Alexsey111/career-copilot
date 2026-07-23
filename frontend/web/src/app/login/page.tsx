"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { AlertCircle, Sparkles, FileSearch, ShieldCheck, BarChart3 } from "lucide-react";

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
    <div className="min-h-screen grid lg:grid-cols-2">
      {/* Hero — скрыт на мобильных, виден на lg+ */}
      <aside className="hidden lg:flex flex-col justify-between p-10 bg-gradient-to-br from-slate-50 via-slate-100 to-slate-50 border-r">
        <div className="flex items-center gap-2">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/logo.svg" alt="AI Career Copilot" className="h-8 w-8" />
          <span className="font-semibold text-lg">AI Career Copilot</span>
        </div>

        <div className="space-y-6 max-w-md">
          <h1 className="text-3xl font-bold tracking-tight">
            Резюме и письма,<br />которые доходят до интервью
          </h1>
          <p className="text-muted-foreground">
            AI собирает профиль из GitHub и резюме, адаптирует под вакансию
            и проверяет каждый факт — без выдуманных достижений.
          </p>

          <ul className="space-y-3">
            <li className="flex items-start gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-background ring-1 ring-foreground/10 shrink-0">
                <FileSearch className="size-4 text-primary" />
              </div>
              <div>
                <p className="text-sm font-medium">Импорт профиля из GitHub</p>
                <p className="text-xs text-muted-foreground">
                  Репозитории, README, технологии — автоматически в профиль
                </p>
              </div>
            </li>
            <li className="flex items-start gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-background ring-1 ring-foreground/10 shrink-0">
                <BarChart3 className="size-4 text-primary" />
              </div>
              <div>
                <p className="text-sm font-medium">Адаптация под вакансию</p>
                <p className="text-xs text-muted-foreground">
                  Сопроводительное письмо с подсветкой совпадений
                </p>
              </div>
            </li>
            <li className="flex items-start gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-background ring-1 ring-foreground/10 shrink-0">
                <ShieldCheck className="size-4 text-primary" />
              </div>
              <div>
                <p className="text-sm font-medium">Факт-чекинг достижений</p>
                <p className="text-xs text-muted-foreground">
                  Каждое утверждение можно подтвердить или удалить
                </p>
              </div>
            </li>
          </ul>
        </div>

        <p className="text-xs text-muted-foreground">
          152-ФЗ · данные хранятся в РФ · резервные копии ежедневно
        </p>
      </aside>

      {/* Form */}
      <main className="flex items-center justify-center p-6">
        <Card className="w-full max-w-md">
          <CardHeader>
            <div className="flex items-center gap-2 lg:hidden mb-2">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/logo.svg" alt="AI Career Copilot" className="h-6 w-6" />
              <span className="font-semibold">AI Career Copilot</span>
            </div>
            <CardTitle className="text-2xl">Вход</CardTitle>
            <CardDescription>Войдите, чтобы продолжить</CardDescription>
          </CardHeader>
          <CardContent>
            {error && (
              <Alert variant="destructive" className="mb-4">
                <AlertCircle />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            <div className="space-y-3 mb-6">
              <Button
                type="button"
                variant="outline"
                onClick={() => handleOAuth("google")}
                className="w-full"
              >
                <svg className="w-5 h-5" viewBox="0 0 24 24" aria-hidden>
                  <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" />
                  <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                  <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                  <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
                </svg>
                Войти через Google
              </Button>

              <Button
                type="button"
                variant="outline"
                onClick={() => handleOAuth("github")}
                className="w-full"
              >
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24" aria-hidden>
                  <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
                </svg>
                Войти через GitHub
              </Button>
            </div>

            <div className="relative mb-6">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-border" />
              </div>
              <div className="relative flex justify-center text-xs uppercase">
                <span className="px-2 bg-card text-muted-foreground">или</span>
              </div>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="password">Пароль</Label>
                <Input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
              </div>

              <Button type="submit" disabled={loading} className="w-full">
                <Sparkles />
                {loading ? "Вход..." : "Войти"}
              </Button>
            </form>

            <p className="mt-4 text-center text-sm text-muted-foreground">
              Нет аккаунта?{" "}
              <Link
                href="/register"
                className="text-foreground underline underline-offset-4 hover:text-primary"
              >
                Зарегистрироваться
              </Link>
            </p>
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
