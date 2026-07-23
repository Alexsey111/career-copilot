/**
 * Типы ответов API — зеркала pydantic-схем бэкенда (`app/schemas/`).
 * Используются страницами и компонентами вместо `any`.
 * Поля помечены optional, если бэкенд может их не вернуть (зависит от контекста).
 */

// ---- Vacancy fit (GET /vacancies/{id}/fit) ----
export interface VacancyFitEvidence {
  evidence_id?: string | null;
  title: string;
  reason?: string;
  score?: number | null;
  fact_status?: string | null;
  evidence_strength?: string | null;
  star_preview?: Record<string, unknown>;
  snippet_text?: string | null;
}

export interface VacancyFitRequirement {
  requirement: string;
  scope: string;
  severity: string;
  coverage_level: string;
  reason: string;
  evidence_ids?: string[];
  supporting_evidence?: VacancyFitEvidence[];
}

export interface VacancyFitCoverage {
  required: string[];
  strong: VacancyFitRequirement[];
  medium: VacancyFitRequirement[];
  missing: VacancyFitRequirement[];
}

export interface VacancyFitResponse {
  analysis_id?: string | null;
  analysis_version?: string | null;
  vacancy_id: string;
  overall_fit_score: number;
  skills_fit: number;
  evidence_fit: number;
  experience_fit: number;
  leadership_fit: number;
  gap_severity: string;
  readiness_recommendation: string;
  requirements?: VacancyFitRequirement[];
  evidence_coverage: VacancyFitCoverage;
}

// ---- Vacancy analysis (GET /vacancies/{id}/analysis/latest) ----
export interface VacancyAnalysisResponse {
  analysis_id: string;
  vacancy_id: string;
  must_have: Record<string, unknown>[];
  nice_to_have: Record<string, unknown>[];
  keywords: string[];
  strengths: Record<string, unknown>[];
  gaps: Record<string, unknown>[];
  risks?: Record<string, unknown>[];
  match_logic?: Record<string, unknown>;
  language_tone_hints?: Record<string, unknown>;
  match_score: number | null;
  analysis_version: string;
  created_at: string;
}

// ---- Documents ----
export interface ActiveDocumentResponse {
  id: string;
  vacancy_id: string | null;
  document_kind: string;
  version_label: string;
  review_status: string;
  is_active: boolean;
  created_at: string;
  updated_at?: string;
  rendered_text?: string;
}

export interface DocumentRead {
  id: string;
  document_kind?: string;
  vacancy_id?: string | null;
  version_label?: string;
  review_status?: string;
  is_active?: boolean;
  rendered_text?: string;
  content_json?: Record<string, unknown>;
  created_at?: string;
  updated_at?: string;
}

export interface DocumentReviewSummary {
  document_id: string;
  document_kind: string;
  review_status: string;
  is_active: boolean;
  version_label: string;
  readiness?: Record<string, unknown>;
  quality?: Record<string, unknown>;
  provenance?: Record<string, unknown>;
  claims_needing_confirmation?: Record<string, unknown>[];
  warnings?: Record<string, unknown>[];
  selected_achievements?: Record<string, unknown>[];
  selected_achievement_ids?: string[];
  selected_evidence_ids?: string[];
  evidence_selection_reason?: string;
  selected_evidence?: Record<string, unknown>[];
  unused_evidence?: Record<string, unknown>[];
  matched_keywords?: string[];
  missing_keywords?: string[];
  selection_rationale?: string;
  rendered_text_preview?: string;
}

export interface DocumentDiffSection {
  section: string;
  base?: string;
  target?: string;
  change?: string;
}

export interface DocumentDiffResponse {
  base_document_id: string;
  target_document_id: string;
  document_kind: string;
  sections: DocumentDiffSection[];
}

// ---- Evidence ----
export interface EvidenceSnippetItem {
  id: string;
  title: string;
  snippet_text?: string;
  source_type?: string;
  skills?: string[];
  evidence_strength?: string;
  fact_status?: string;
  usage_count?: number;
  used_in_documents_count?: number;
  used_in_interviews_count?: number;
  star_summary?: Record<string, unknown>;
  created_at?: string;
}

export interface EvidenceUsageItem {
  snippet_id?: string;
  target_type?: string;
  target_id?: string;
  note?: string;
  date?: string;
}

export interface EvidenceInsightsResponse {
  weak_evidence_count?: number;
  missing_metrics_count?: number;
  recommendations?: Record<string, unknown>[];
  [key: string]: unknown;
}

// ---- Achievements ----
export interface AchievementItem {
  id: string;
  title: string;
  situation?: string;
  task?: string;
  action?: string;
  result?: string;
  metric_text?: string;
  fact_status?: string;
  evidence_note?: string;
  source?: string;
}

export interface AchievementExtractResponse {
  extraction_id?: string;
  achievements?: AchievementItem[];
  count?: number;
}

export interface AchievementReviewPayload {
  title: string;
  situation?: string;
  task?: string;
  action?: string;
  result?: string;
  metric_text?: string;
  fact_status?: string;
  evidence_note?: string;
}

// ---- Applications ----
export interface ApplicationListItem {
  id: string;
  vacancy_id?: string;
  vacancy_title?: string;
  company?: string;
  location?: string;
  status: string;
  applied_at?: string | null;
  result?: string | null;
  notes?: string;
  created_at?: string;
}

export interface ApplicationWorkflowResponse {
  application_id?: string;
  current_status?: string;
  allowed_transitions?: string[];
  can_submit?: boolean;
  is_final?: boolean;
  review_required?: boolean;
  review_blockers?: Record<string, unknown>[];
}

export interface ApplicationStatusHistoryItem {
  status: string;
  changed_at?: string;
  note?: string | null;
}

export interface ApplicationEventItem {
  event_type?: string;
  event_label?: string;
  created_at?: string;
  payload?: Record<string, unknown>;
}

export interface ApplicationReminderItem {
  application_id?: string;
  kind?: string;
  message?: string;
  severity?: string;
}

export interface ApplicationAnalytics {
  total?: number;
  active?: number;
  submitted?: number;
  offers?: number;
  rejected?: number;
  average_prep_hours?: number;
  conversion_by_resume_version?: Record<string, unknown>[];
  [key: string]: unknown;
}

// ---- Career insights ----
export interface CareerInsightsResponse {
  repeated_gaps?: Record<string, unknown>[];
  evidence_coverage_trends?: Record<string, unknown>;
  application_patterns?: Record<string, unknown>;
  strategic_recommendations?: Record<string, unknown>[];
  vacancy_intelligence_sample?: Record<string, unknown>[];
  [key: string]: unknown;
}

// ---- Interview prep ----
export interface InterviewPrepSessionListItem {
  id: string;
  application_id?: string;
  prep_status?: string;
  readiness_score?: number | null;
  created_at?: string;
}

export interface InterviewPrepReadinessRead {
  ready?: boolean;
  readiness_score?: number | null;
  blockers?: Record<string, unknown>[];
  warnings?: Record<string, unknown>[];
  competency_coverage_matrix?: Record<string, unknown>;
  roadmap?: Record<string, unknown>[];
  prep_status?: string;
}

export interface InterviewPrepWeakArea {
  code?: string;
  message?: string;
  severity?: string;
  category?: string;
}

export interface InterviewPrepSuggestedAnswer {
  format?: string;
  situation?: string;
  task?: string;
  action?: string;
  result?: string;
  tech_stack?: string[];
  tradeoffs?: string[];
  talking_points?: string[];
  source_evidence_id?: string | null;
  source_title?: string | null;
  fact_status?: string;
  grounding_status?: string;
  requires_human_review?: boolean;
  draft_text?: string;
  quality?: Record<string, unknown>;
}

export interface InterviewPrepQuestion {
  id?: string;
  prompt: string;
  category?: string;
  competency_name?: string;
  requires_careful_answer?: boolean;
  recommended_evidence_ids?: string[];
  // Бэк отдаёт структурированный объект (см. InterviewPrepSuggestedAnswer)
  // с полями format/situation/task/action/result/tech_stack/talking_points/draft_text.
  // Для обратной совместимости допускаем строку.
  suggested_answer?: InterviewPrepSuggestedAnswer | string;
  answer_quality?: Record<string, unknown>;
}

export interface InterviewPrepSessionRead {
  id: string;
  application_id?: string;
  prep_status?: string;
  readiness_score?: number | null;
  questions?: InterviewPrepQuestion[];
  weak_areas?: InterviewPrepWeakArea[];
  competency_map?: Record<string, unknown>;
  evidence_links?: Record<string, unknown>[];
  readiness?: InterviewPrepReadinessRead;
  created_at?: string;
}

// ---- Trust / review summary ----
export interface ReviewSummaryResponse {
  entity_type?: string;
  entity_id?: string;
  ready?: boolean;
  requires_human_review?: boolean;
  risk_level?: string;
  quality?: Record<string, unknown>;
  blockers?: Record<string, unknown>[];
  warnings?: Record<string, unknown>[];
  claims_requiring_confirmation?: Record<string, unknown>[];
  gap_risk_items?: Record<string, unknown>[];
  selected_evidence?: Record<string, unknown>[];
  provenance_summary?: Record<string, unknown>;
  recommended_actions?: Record<string, unknown>[];
}

export interface HealthDiagnosticsResponse {
  status?: string;
  backend_reachable?: boolean;
  db_reachable?: boolean;
  counts?: Record<string, number>;
  active_documents?: Record<string, unknown>[];
  current_application?: Record<string, unknown> | null;
  [key: string]: unknown;
}

// ---- Billing ----
export interface PlanUsageItem {
  action: string;
  used: number;
  limit: number | null;
  window_days?: number | null;
  window_seconds?: number | null;
  // Самая старая запись в текущем окне (ISO 8601, UTC). null если used=0.
  // Фронт использует для обратного отсчёта «сброс через X мин» — когда
  // эта запись выйдет за окно, used уменьшится на 1.
  oldest_in_window?: string | null;
}

export interface MySubscriptionResponse {
  user_id?: string;
  plan: string;
  status?: string;
  stripe_customer_id?: string | null;
  stripe_subscription_id?: string | null;
  current_period_end?: string | null;
  canceled_at?: string | null;
  usage?: PlanUsageItem[];
}

export interface CheckoutResponse {
  checkout_url?: string;
  session_id?: string;
}

export interface PortalResponse {
  portal_url?: string;
}

// ---- Profile intake ----
export interface ProfileIntakeResponse {
  profile_id?: string;
  extraction_id?: string;
  project_count?: number;
  evidence_snippet_count?: number;
  [key: string]: unknown;
}

// ---- Consent ----
export interface ConsentItem {
  consent_type: string;
  title?: string;
  description?: string;
  version?: string;
  is_granted?: boolean;
  is_required?: boolean;
  granted_at?: string | null;
  revoked_at?: string | null;
}