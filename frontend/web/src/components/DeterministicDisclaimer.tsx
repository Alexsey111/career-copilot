/**
 * Единая подпись для детерминированных блоков (fit-анализ, карьерные инсайты,
 * evidence-инсайты): «Детерминированный разбор, а не оценка вероятности найма».
 * Зеркало подписей из streamlit-версии.
 */
export default function DeterministicDisclaimer({
  text = "Детерминированный разбор соответствия, а не вероятность найма.",
}: {
  text?: string;
}) {
  return (
    <p className="text-xs text-[color:var(--brand-teal-60)] italic mb-3">{text}</p>
  );
}