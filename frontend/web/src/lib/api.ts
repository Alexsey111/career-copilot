const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:7000/api/v1";

interface RequestOptions extends RequestInit {
  token?: string;
}

/**
 * Извлекает человекочитаемое сообщение об ошибке из ответа API.
 * Бэкенд возвращает:
 *   - строковый `detail` (HTTPException) — отдаём как есть;
 *   - структурированный `detail` (QuotaErrorDetail: {action, plan, used, limit, reason})
 *     — иначе `new Error(detail)` даст "[object Object]";
 *   - fastapi-список ошибок валидации `detail: [{msg, ...}]`.
 */
function extractErrorMessage(error: any, status: number): string {
  const detail = error?.detail;
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }
  if (detail && typeof detail === "object") {
    if (typeof detail.reason === "string" && detail.reason.trim()) {
      const used = detail.used ?? null;
      const limit = detail.limit ?? null;
      const quota =
        used != null && limit != null ? ` (использовано ${used}/${limit})` : "";
      return `Квота превышена: ${detail.reason}${quota}. План: ${detail.plan}.`;
    }
    if (Array.isArray(detail)) {
      const msg = detail
        .map((e: any) => (typeof e?.msg === "string" ? e.msg : String(e)))
        .join("; ");
      if (msg.trim()) return msg;
    }
  }
  return `API error: ${status}`;
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
    const { token, ...fetchOptions } = options;
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(options.headers as Record<string, string> || {}),
    };

    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    const res = await fetch(`${this.baseUrl}${endpoint}`, {
      ...fetchOptions,
      headers,
    });

    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(extractErrorMessage(error, res.status));
    }

    return res.json();
  }

  // Auth
  async register(email: string, password: string) {
    return this.request<{ access_token: string; refresh_token: string }>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
  }

  async login(email: string, password: string) {
    return this.request<{ access_token: string; refresh_token: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
  }

  async refreshToken(refreshToken: string) {
    return this.request<{ access_token: string; refresh_token: string }>("/auth/refresh", {
      method: "POST",
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
  }

  async getMe(token: string) {
    return this.request<{ id: string; email: string }>("/auth/me", { token });
  }

  // OAuth
  async oauthAuthorize(provider: "google" | "github") {
    return this.request<{ auth_url: string; state: string }>(
      `/auth/oauth/${provider}/authorize`
    );
  }

  async oauthCallback(provider: "google" | "github", code: string, state?: string) {
    return this.request<{ access_token: string; refresh_token: string }>(
      `/auth/oauth/${provider}/callback?code=${code}${state ? `&state=${state}` : ""}`,
      { method: "POST" }
    );
  }

  // Profile
  async getProfile(token: string) {
    return this.request("/profile/resume-state", { token });
  }

  async importResume(token: string, text: string) {
    return this.request("/profile/import-resume-text", {
      method: "POST",
      token,
      body: JSON.stringify({ text }),
    });
  }

  async extractResume(token: string, sourceFileId: string) {
    return this.request("/profile/import-resume", {
      method: "POST",
      token,
      body: JSON.stringify({ source_file_id: sourceFileId }),
    });
  }

  async extractStructured(token: string, extractionId: string) {
    return this.request("/profile/extract-structured", {
      method: "POST",
      token,
      body: JSON.stringify({ extraction_id: extractionId }),
    });
  }

  async extractAchievements(token: string, extractionId: string) {
    return this.request("/profile/extract-achievements", {
      method: "POST",
      token,
      body: JSON.stringify({ extraction_id: extractionId }),
    });
  }

  // Vacancies
  async searchVacancies(token: string, params: Record<string, string | number>) {
    const query = new URLSearchParams(params as Record<string, string>).toString();
    return this.request(`/vacancies/search?${query}`, { token });
  }

  async semanticSearchVacancies(token: string, query: string, params: Record<string, string | number> = {}) {
    const searchParams = new URLSearchParams({ query, ...params as Record<string, string> }).toString();
    return this.request(`/vacancies/semantic-search?${searchParams}`, { token });
  }

  async importVacancyFromUrl(token: string, sourceUrl: string) {
    return this.request("/vacancies/import-from-url", {
      method: "POST",
      token,
      body: JSON.stringify({ source_url: sourceUrl }),
    });
  }

  async importVacancyFromText(token: string, text: string) {
    return this.request("/vacancies/import", {
      method: "POST",
      token,
      body: JSON.stringify({ description_raw: text, source: "manual" }),
    });
  }

  async getVacancy(token: string, vacancyId: string) {
    return this.request(`/vacancies/${vacancyId}`, { token });
  }

  async analyzeVacancy(token: string, vacancyId: string) {
    return this.request(`/vacancies/${vacancyId}/analyze`, {
      method: "POST",
      token,
      body: JSON.stringify({}),
    });
  }

  async getVacancyAnalysis(token: string, vacancyId: string) {
    return this.request(`/vacancies/${vacancyId}/analysis/latest`, { token });
  }

  // Documents
  async generateResume(token: string, vacancyId: string) {
    return this.request("/documents/resumes/generate", {
      method: "POST",
      token,
      body: JSON.stringify({ vacancy_id: vacancyId }),
    });
  }

  async generateCoverLetter(token: string, vacancyId: string, variant: string = "standard") {
    return this.request("/documents/letters/generate", {
      method: "POST",
      token,
      body: JSON.stringify({ vacancy_id: vacancyId, variant }),
    });
  }

  async getDocument(token: string, documentId: string) {
    return this.request(`/documents/${documentId}`, { token });
  }

  async approveDocument(token: string, documentId: string, setActive = true) {
    return this.request(`/documents/${documentId}/review`, {
      method: "PATCH",
      token,
      body: JSON.stringify({
        review_status: "approved",
        set_active_when_approved: setActive,
      }),
    });
  }

  // Applications
  async createApplication(token: string, vacancyId: string, resumeId?: string, coverLetterId?: string) {
    return this.request("/applications", {
      method: "POST",
      token,
      body: JSON.stringify({
        vacancy_id: vacancyId,
        resume_document_id: resumeId,
        cover_letter_document_id: coverLetterId,
      }),
    });
  }

  async listApplications(token: string) {
    return this.request("/applications", { token });
  }

  async updateApplicationStatus(token: string, appId: string, status: string) {
    return this.request(`/applications/${appId}/status`, {
      method: "PATCH",
      token,
      body: JSON.stringify({ status }),
    });
  }

  async getApplicationAnalytics(token: string) {
    return this.request("/applications/analytics/summary", { token });
  }

  // Interview Prep
  async createInterviewPrep(token: string, applicationId: string) {
    return this.request("/interview-prep/sessions", {
      method: "POST",
      token,
      body: JSON.stringify({ application_id: applicationId }),
    });
  }

  async getInterviewPrep(token: string, sessionId: string) {
    return this.request(`/interview-prep/sessions/${sessionId}`, { token });
  }

  // Files
  async uploadFile(token: string, file: File, fileKind: string = "resume") {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("file_kind", fileKind);

    const res = await fetch(`${this.baseUrl}/files/upload`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: formData,
    });

    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(extractErrorMessage(error, res.status));
    }
    return res.json();
  }

  async exportDocument(token: string, documentId: string, format: string = "txt") {
    const res = await fetch(`${this.baseUrl}/documents/${documentId}/export/${format}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) throw new Error("Export failed");
    return res.text();
  }

  async exportDocumentBlob(token: string, documentId: string, format: string = "docx") {
    const res = await fetch(`${this.baseUrl}/documents/${documentId}/export/${format}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(extractErrorMessage(error, res.status));
    }
    return res.blob();
  }

  // Vacancy fit
  async getVacancyFit(token: string, vacancyId: string) {
    return this.request(`/vacancies/${vacancyId}/fit`, { token });
  }

  // Vacancy import from file
  async importVacancyFromFile(
    token: string,
    sourceFileId: string,
    title: string,
    company?: string,
    location?: string,
    sourceUrl?: string
  ) {
    return this.request("/vacancies/import-from-file", {
      method: "POST",
      token,
      body: JSON.stringify({
        source_file_id: sourceFileId,
        title,
        company: company || null,
        location: location || null,
        source_url: sourceUrl || null,
      }),
    });
  }

  // Documents — list/active/review/diff/enhance/activate
  async getActiveDocument(token: string, documentKind: string, vacancyId?: string) {
    const query = new URLSearchParams({ document_kind: documentKind });
    if (vacancyId) query.set("vacancy_id", vacancyId);
    return this.request(`/documents/active?${query.toString()}`, { token });
  }

  async getDocumentReviewSummary(token: string, documentId: string) {
    return this.request(`/documents/${documentId}/review-summary`, { token });
  }

  async getDocumentDiff(token: string, documentId: string, targetId: string) {
    return this.request(`/documents/${documentId}/diff/${targetId}`, { token });
  }

  async enhanceResume(token: string, documentId: string, resumeText: string) {
    return this.request(`/documents/resumes/${documentId}/enhance`, {
      method: "POST",
      token,
      body: JSON.stringify({ resume_text: resumeText }),
    });
  }

  async enhanceCoverLetter(token: string, documentId: string, coverLetterText: string) {
    return this.request(`/documents/letters/${documentId}/enhance`, {
      method: "POST",
      token,
      body: JSON.stringify({ cover_letter_text: coverLetterText }),
    });
  }

  async activateDocument(token: string, documentId: string) {
    return this.request(`/documents/${documentId}/activate`, {
      method: "POST",
      token,
    });
  }

  // Achievements review + intake
  async reviewAchievement(token: string, achievementId: string, payload: Record<string, unknown>) {
    return this.request(`/profile/achievements/${achievementId}/review`, {
      method: "PATCH",
      token,
      body: JSON.stringify(payload),
    });
  }

  async intakeManual(token: string, payload: Record<string, unknown>) {
    return this.request("/profile/intake/manual", {
      method: "POST",
      token,
      body: JSON.stringify(payload),
    });
  }

  async intakeGithubPublic(token: string, payload: Record<string, unknown>) {
    return this.request("/profile/intake/github-public", {
      method: "POST",
      token,
      body: JSON.stringify(payload),
    });
  }

  async generateRepositoryAchievements(token: string, payload: Record<string, unknown> = {}) {
    return this.request("/profile/repository-achievements/generate", {
      method: "POST",
      token,
      body: JSON.stringify(payload),
    });
  }

  // Applications — workflow/timeline/activity/reminders/submit
  async getApplicationReminders(token: string) {
    return this.request("/applications/reminders", { token });
  }

  async getApplication(token: string, appId: string) {
    return this.request(`/applications/${appId}`, { token });
  }

  async getApplicationWorkflow(token: string, appId: string) {
    return this.request(`/applications/${appId}/workflow`, { token });
  }

  async getApplicationTimeline(token: string, appId: string) {
    return this.request(`/applications/${appId}/timeline`, { token });
  }

  async getApplicationActivityLog(token: string, appId: string) {
    return this.request(`/applications/${appId}/activity-log`, { token });
  }

  async submitApplication(token: string, appId: string, payload: { source?: string; external_link?: string }) {
    return this.request(`/applications/${appId}/submit`, {
      method: "POST",
      token,
      body: JSON.stringify(payload),
    });
  }

  // Evidence
  async getEvidenceSnippets(token: string) {
    return this.request("/evidence/snippets", { token });
  }

  async getEvidenceSnippet(token: string, snippetId: string) {
    return this.request(`/evidence/snippets/${snippetId}`, { token });
  }

  async confirmEvidence(token: string, snippetId: string) {
    return this.request(`/evidence/${snippetId}/confirm`, { method: "POST", token });
  }

  async rejectEvidence(token: string, snippetId: string) {
    return this.request(`/evidence/${snippetId}/reject`, { method: "POST", token });
  }

  async getEvidenceUsages(token: string) {
    return this.request("/evidence/usages", { token });
  }

  async getEvidenceInsights(token: string) {
    return this.request("/evidence/insights", { token });
  }

  // Career insights
  async getCareerInsights(token: string) {
    return this.request("/career-insights/summary", { token });
  }

  // Interview prep
  async listInterviewPrepSessions(token: string) {
    return this.request("/interview-prep/sessions", { token });
  }

  async getInterviewPrepReadiness(token: string, sessionId: string) {
    return this.request(`/interview-prep/sessions/${sessionId}/readiness`, { token });
  }

  async deleteInterviewPrepSession(token: string, sessionId: string) {
    return this.request(`/interview-prep/sessions/${sessionId}`, {
      method: "DELETE",
      token,
    });
  }

  // Trust / health
  async getHealthDiagnostics(token: string) {
    return this.request("/health/diagnostics", { token });
  }

  async getReviewSummary(token: string, entityType: "document" | "interview_prep", entityId: string) {
    return this.request(`/review/summary/${entityType}/${entityId}`, { token });
  }

  // Billing
  async getSubscription(token: string) {
    return this.request("/me/billing/subscription", { token });
  }

  async createCheckout(token: string, payload: Record<string, unknown> = {}) {
    return this.request("/billing/checkout", {
      method: "POST",
      token,
      body: JSON.stringify(payload),
    });
  }

  async createPortalSession(token: string) {
    return this.request("/billing/portal", { method: "POST", token });
  }

  // Consent
  async listConsents(token: string) {
    return this.request("/consent/", { token });
  }

  async grantConsent(token: string, consentType: string) {
    return this.request("/consent/", {
      method: "POST",
      token,
      body: JSON.stringify({ consent_type: consentType }),
    });
  }

  async revokeConsent(token: string, consentType: string) {
    return this.request(`/consent/${consentType}`, {
      method: "DELETE",
      token,
    });
  }

  async checkConsents(token: string) {
    return this.request("/consent/check", { token });
  }
}

export const api = new ApiClient();
export type { ApiClient };
