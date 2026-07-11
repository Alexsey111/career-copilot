"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";

function OAuthCallbackInner({ provider }: { provider: "google" | "github" }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [error, setError] = useState("");

  useEffect(() => {
    const code = searchParams.get("code");
    const state = searchParams.get("state");
    const savedState = localStorage.getItem("oauth_state");

    if (!code) {
      setError("Authorization code not found");
      return;
    }

    if (savedState && state && state !== savedState) {
      setError("Invalid state parameter");
      return;
    }

    localStorage.removeItem("oauth_state");

    api
      .oauthCallback(provider, code, state || undefined)
      .then((res) => {
        localStorage.setItem("auth_token", res.access_token);
        router.push("/");
      })
      .catch((err: any) => {
        setError(err.message || "OAuth login failed");
      });
  }, [provider, searchParams, router]);

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="w-full max-w-md bg-white rounded-xl shadow-md p-8 text-center">
          <div className="text-red-600 mb-4">{error}</div>
          <a href="/login" className="text-blue-600 hover:underline">
            Вернуться к входу
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="text-gray-500">Завершение входа...</div>
    </div>
  );
}

export default function OAuthCallback({ provider }: { provider: "google" | "github" }) {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center bg-gray-50">
          <div className="text-gray-500">Загрузка...</div>
        </div>
      }
    >
      <OAuthCallbackInner provider={provider} />
    </Suspense>
  );
}
