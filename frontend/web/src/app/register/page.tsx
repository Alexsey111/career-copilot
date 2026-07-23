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
import { AlertCircle, Sparkles, FileSearch, ShieldCheck, BarChart3 } from "lucide-react";

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
    <div className="min-h-screen grid lg:grid-cols-2">
      <aside className="hidden lg:flex flex-col justify-between p-10 bg-gradient-to-br from-slate-50 via-slate-100 to-slate-50 border-r">
        <div className="flex items-center gap-2">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/logo.svg" alt="AI Career Copilot" className="h-8 w-8" />
          <span className="font-semibold text-lg">AI Career Copilot</span>
        </div>

        <div className="space-y-6 max-w-md">
          <h1 className="text-3xl font-bold tracking-tight">
            Начните с профиля,<br />а не с пустого резюме
          </h1>
          <p className="text-muted-foreground">
            Регистрация занимает минуту. Сразу после неё можно импортировать
            GitHub, загрузить резюме или собрать профиль вручную.
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

      <main className="flex items-center justify-center p-6">
        <Card className="w-full max-w-md">
          <CardHeader>
            <div className="flex items-center gap-2 lg:hidden mb-2">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/logo.svg" alt="AI Career Copilot" className="h-6 w-6" />
              <span className="font-semibold">AI Career Copilot</span>
            </div>
            <CardTitle className="text-2xl">Регистрация</CardTitle>
            <CardDescription>Создайте аккаунт, чтобы начать</CardDescription>
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
                <Label htmlFor="password">Пароль (минимум 8 символов)</Label>
                <Input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  minLength={8}
                  required
                />
              </div>

              <Button type="submit" disabled={loading} className="w-full">
                <Sparkles />
                {loading ? "Регистрация..." : "Зарегистрироваться"}
              </Button>
            </form>

            <p className="mt-4 text-center text-sm text-muted-foreground">
              Уже есть аккаунт?{" "}
              <Link
                href="/login"
                className="text-foreground underline underline-offset-4 hover:text-primary"
              >
                Войти
              </Link>
            </p>
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
