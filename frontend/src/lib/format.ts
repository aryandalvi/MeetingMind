export function formatDate(iso: string | null | undefined, opts: Intl.DateTimeFormatOptions = {}): string {
  if (!iso) return "";
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  if (!y || !m || !d) return iso;
  return new Date(y, m - 1, d).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric", ...opts });
}

export function daysFrom(base: string | null | undefined, iso: string | null | undefined): number | null {
  if (!base || !iso) return null;
  const a = Date.UTC(...(base.split("-").map(Number) as [number, number, number]));
  const b = Date.UTC(...(iso.split("-").map(Number) as [number, number, number]));
  return Math.round((b - a) / 86_400_000);
}

export function relativeLabel(days: number | null): string {
  if (days === null) return "";
  if (days === 0) return "same day";
  if (days === 1) return "next day";
  if (days < 0) return `${-days} days before`;
  return `in ${days} days`;
}

export function wordCount(text: string): number {
  const t = text.trim();
  return t ? t.split(/\s+/).length : 0;
}

export function plural(n: number, word: string, pluralWord = `${word}s`): string {
  return `${n} ${n === 1 ? word : pluralWord}`;
}

export const OWNER_SOURCE_LABEL: Record<string, string> = {
  explicit_name: "Named in the transcript",
  self_commitment: "Self-commitment (“I'll…”)",
  addressed_request: "Request addressed to them",
  inferred_from_reply: "Inferred from their reply",
  unassigned: "No owner found",
  user: "Set by you",
};

export const STATUS_LABEL: Record<string, string> = {
  open: "Open",
  in_progress: "In progress",
  done: "Done",
  blocked: "Blocked",
};
