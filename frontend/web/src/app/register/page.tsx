"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Logo } from "@/components/Logo";
import { Mail, Lock, Sparkles, AlertCircle, FileSearch, BarChart3, ShieldCheck, ArrowRight } from "lucide-react";

export default function RegisterPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { register } = useAuth();
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await register(email, password);
      router.push("/profile");
    } catch (err: any) {
      setError(err.message || "Ошибка регистрации");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-[1.1fr_1fr]" style={{ backgroundColor: "var(--brand-cream)" }}>
      {/* Hero — тёмная зона #1A3134, лаймовые блобы (как у /login). */}
      <aside className="relative hidden lg:flex flex-col justify-between p-12 overflow-hidden bg-[#1A3134] text-[#F4FFDF]">
        <div
          aria-hidden
          className="pointer-events-none absolute -top-40 -left-40 w-[600px] h-[600px] rounded-full bg-[#CFFF71]/30 blur-3xl animate-[pulse_8s_ease-in-out_infinite]"
        />
        <div
          aria-hidden
          className="pointer-events-none absolute top-1/3 -right-32 w-[500px] h-[500px] rounded-full bg-[#CFFF71]/20 blur-3xl animate-[pulse_10s_ease-in-out_infinite_2s]"
        />
        <div
          aria-hidden
          className="pointer-events-none absolute -bottom-32 left-1/4 w-[550px] h-[550px] rounded-full bg-[#004D43]/50 blur-3xl animate-[pulse_12s_ease-in-out_infinite_4s]"
        />
        <div
          aria-hidden
          className="absolute inset-0 bg-[radial-gradient(circle_at_1px_1px,rgba(207,255,113,0.06)_1px,transparent_0)] [background-size:24px_24px]"
        />

        <div className="relative z-10 flex items-center gap-2">
          <Logo size={32} withWordmark />
        </div>

        <div className="relative z-10 space-y-8 max-w-lg">
          <div className="inline-flex items-center gap-2 rounded-full border border-[#CFFF71]/30 bg-[#1A3134]/80 backdrop-blur-sm px-3 py-1 text-xs font-medium shadow-sm">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#CFFF71] opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-[#CFFF71]" />
            </span>
            <span className="text-[#F4FFDF]/90">
              Бесплатный старт · 152-ФЗ · данные в РФ
            </span>
          </div>

          <div className="space-y-4">
            <h1 className="text-5xl font-bold tracking-tight leading-[1.05] text-[#F4FFDF]">
              <span className="text-[#CFFF71]">Начните с профиля,</span>
              <br />
              а не с пустого
              <br />
              резюме
            </h1>
            <p className="text-lg text-[#F4FFDF]/70 leading-relaxed max-w-md">
              Регистрация занимает минуту. Сразу после неё можно импортировать
              GitHub, загрузить резюме или собрать профиль вручную.
            </p>
          </div>

          <ul className="space-y-4">
            <li className="flex items-start gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#CFFF71] text-[#004D43] shadow-sm shrink-0">
                <FileSearch className="size-4" />
              </div>
              <div>
                <p className="text-sm font-medium text-[#F4FFDF]">Импорт профиля из GitHub</p>
                <p className="text-xs text-[#F4FFDF]/60">
                  Репозитории, README, технологии — автоматически в профиль
                </p>
              </div>
            </li>
            <li className="flex items-start gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#004D43] text-[#CFFF71] shadow-sm shrink-0 border border-[#CFFF71]/20">
                <BarChart3 className="size-4" />
              </div>
              <div>
                <p className="text-sm font-medium text-[#F4FFDF]">Адаптация под вакансию</p>
                <p className="text-xs text-[#F4FFDF]/60">
                  Сопроводительное письмо с подсветкой совпадений
                </p>
              </div>
            </li>
            <li className="flex items-start gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-[#CFFF71] to-[#004D43] text-[#F4FFDF] shadow-sm shrink-0">
                <ShieldCheck className="size-4" />
              </div>
              <div>
                <p className="text-sm font-medium text-[#F4FFDF]">Факт-чекинг достижений</p>
                <p className="text-xs text-[#F4FFDF]/60">
                  Каждое утверждение можно подтвердить или удалить
                </p>
              </div>
            </li>
          </ul>
        </div>

        <p className="relative z-10 text-xs text-[#F4FFDF]/50">
          152-ФЗ · данные хранятся в РФ · резервные копии ежедневно
        </p>
      </aside>

      {/* Form — светлая зона #F4FFDF, тёмно-teal текст. */}
      <main className="flex items-center justify-center p-6 lg:p-12" style={{ backgroundColor: "var(--brand-cream)" }}>
        <div className="w-full max-w-md space-y-6">
          <div className="flex items-center gap-2 lg:hidden">
            <Logo size={28} withWordmark />
          </div>

          <div className="space-y-2">
            <h2 className="text-3xl font-bold tracking-tight" style={{ color: "var(--brand-teal)" }}>
              Создайте аккаунт
            </h2>
            <p className="text-sm" style={{ color: "var(--brand-teal-60)" }}>
              Минута на регистрацию — и можно импортировать GitHub
            </p>
          </div>

          <Card style={{ backgroundColor: "white", borderColor: "var(--brand-teal-20)" }}>
            <CardHeader>
              <CardTitle style={{ color: "var(--brand-teal)" }}>Регистрация</CardTitle>
              <CardDescription style={{ color: "var(--brand-teal-60)" }}>
                Email и пароль. Без подтверждения по SMS, без рекламных рассылок.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {error && (
                <Alert variant="destructive" className="mb-4">
                  <AlertCircle />
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}

              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="email" style={{ color: "var(--brand-teal)" }}>Email</Label>
                  <div className="relative">
                    <Mail className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-[color:var(--brand-teal-60)] pointer-events-none" />
                    <Input
                      id="email"
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      required
                      placeholder="you@example.com"
                      className="pl-9 h-10 bg-white border-[color:var(--brand-teal-20)] text-[color:var(--brand-teal)] placeholder:text-[color:var(--brand-teal-40)] focus-visible:ring-[color:var(--brand-teal)]/30"
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="password" style={{ color: "var(--brand-teal)" }}>
                    Пароль (минимум 8 символов)
                  </Label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-[color:var(--brand-teal-60)] pointer-events-none" />
                    <Input
                      id="password"
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      minLength={8}
                      required
                      placeholder="••••••••"
                      className="pl-9 h-10 bg-white border-[color:var(--brand-teal-20)] text-[color:var(--brand-teal)] placeholder:text-[color:var(--brand-teal-40)] focus-visible:ring-[color:var(--brand-teal)]/30"
                    />
                  </div>
                </div>

                <Button
                  type="submit"
                  disabled={loading}
                  className="w-full h-10 font-semibold shadow-md shadow-[#004D43]/20 hover:shadow-lg hover:shadow-[#004D43]/30 transition-all"
                  style={{ backgroundColor: "var(--brand-lime)", color: "var(--brand-teal)" }}
                >
                  <Sparkles className="size-4" />
                  {loading ? "Регистрация..." : "Зарегистрироваться"}
                  {!loading && <ArrowRight className="size-4 ml-auto" />}
                </Button>
              </form>
            </CardContent>
          </Card>

          <p className="text-center text-sm" style={{ color: "var(--brand-teal-60)" }}>
            Уже есть аккаунт?{" "}
            <Link
              href="/login"
              className="font-semibold underline-offset-4 hover:underline"
              style={{ color: "var(--brand-teal)" }}
            >
              Войти
            </Link>
          </p>
        </div>
      </main>
    </div>
  );
}
