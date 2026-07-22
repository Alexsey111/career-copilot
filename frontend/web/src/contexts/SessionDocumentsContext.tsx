"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

/**
 * Хранит «сессионные» артефакты по вакансии, собранные в ходе прохождения
 * потока (анализ → резюме → письмо → отклик): analysis_id, resume_document_id,
 * cover_letter_document_id. Это позволяет экранам `/documents`, `/applications`
 * открывать последние сгенерированные документы без ручного ввода ID, а
 * fit-блоку вакансии — получать analysis_id.
 *
 * Состояние синхронизируется с localStorage (ключ `ccp:session-docs`), чтобы
 * переживать перезагрузку страницы, но не шарится между устройствами (это
 * клиентский кэш, источник истины — бэкенд).
 */

export interface VacancySession {
  analysisId?: string;
  resumeId?: string;
  coverLetterId?: string;
  applicationId?: string;
}

type SessionMap = Record<string, VacancySession>;

interface SessionDocumentsContextValue {
  getSession: (vacancyId: string) => VacancySession | undefined;
  setSessionDoc: (
    vacancyId: string,
    kind: "analysisId" | "resumeId" | "coverLetterId" | "applicationId",
    id: string
  ) => void;
  clearVacancy: (vacancyId: string) => void;
}

const STORAGE_KEY = "ccp:session-docs";

const SessionDocumentsContext = createContext<SessionDocumentsContextValue | null>(null);

function readStorage(): SessionMap {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as SessionMap) : {};
  } catch {
    return {};
  }
}

export function SessionDocumentsProvider({ children }: { children: ReactNode }) {
  const [sessions, setSessions] = useState<SessionMap>({});

  useEffect(() => {
    setSessions(readStorage());
  }, []);

  const setSessionDoc = useCallback(
    (
      vacancyId: string,
      kind: "analysisId" | "resumeId" | "coverLetterId" | "applicationId",
      id: string
    ) => {
      setSessions((prev) => {
        const current = prev[vacancyId] ?? {};
        const updated: SessionMap = {
          ...prev,
          [vacancyId]: { ...current, [kind]: id },
        };
        if (typeof window !== "undefined") {
          try {
            window.localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
          } catch {
            // ignore
          }
        }
        return updated;
      });
    },
    []
  );

  const getSession = useCallback(
    (vacancyId: string) => sessions[vacancyId],
    [sessions]
  );

  const clearVacancy = useCallback(
    (vacancyId: string) => {
      setSessions((prev) => {
        const next = { ...prev };
        delete next[vacancyId];
        if (typeof window !== "undefined") {
          try {
            window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
          } catch {
            // ignore
          }
        }
        return next;
      });
    },
    []
  );

  const value = useMemo<SessionDocumentsContextValue>(
    () => ({ getSession, setSessionDoc, clearVacancy }),
    [getSession, setSessionDoc, clearVacancy]
  );

  return (
    <SessionDocumentsContext.Provider value={value}>
      {children}
    </SessionDocumentsContext.Provider>
  );
}

export function useSessionDocs(): SessionDocumentsContextValue {
  const ctx = useContext(SessionDocumentsContext);
  if (!ctx) {
    throw new Error("useSessionDocs must be used within <SessionDocumentsProvider>");
  }
  return ctx;
}