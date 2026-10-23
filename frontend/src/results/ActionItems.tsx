import { useEffect, useMemo, useState } from "react";
import { CheckCheck, Flag, Info, ListChecks, Plus, Search, Trash2, UserRound } from "lucide-react";
import { useWorkspace } from "../state/workspace";
import type { ActionItem, ActionStatus, Priority } from "../types";
import { daysFrom, formatDate, OWNER_SOURCE_LABEL, relativeLabel, STATUS_LABEL } from "../lib/format";
import { Badge, Button, cx, EmptyState, SectionHeader, SignalBadge } from "../components/ui";
import { EvidenceList } from "../components/Evidence";
import { ConfirmDialog } from "../components/ConfirmDialog";

type SortKey = "order" | "deadline" | "owner" | "priority" | "status";
const PRIORITY_RANK: Record<Priority, number> = { high: 0, medium: 1, low: 2 };
const STATUS_RANK: Record<ActionStatus, number> = { blocked: 0, open: 1, in_progress: 2, done: 3 };
const STATUS_TONE: Record<ActionStatus, string> = {
  open: "bg-lavender-50 text-violet-700",
  in_progress: "bg-blush-50 text-blush-600",
  done: "bg-sage-50 text-sage-600",
  blocked: "bg-rose-50 text-rose-600",
};

/** Text input that looks like plain text and commits on blur / Enter. */
function InlineText({ value, onCommit, placeholder, className, multiline, ariaLabel, list }: {
  value: string;
  onCommit: (v: string) => void;
  placeholder?: string;
  className?: string;
  multiline?: boolean;
  ariaLabel: string;
  list?: string;
}) {
  const [v, setV] = useState(value);
  useEffect(() => setV(value), [value]);
  const commit = () => {
    if (v.trim() !== value) onCommit(v.trim());
  };
  const cls = cx(
    "w-full rounded-lg border border-transparent bg-transparent px-2 py-1 -mx-2 transition hover:border-line focus:border-violet-400 focus:bg-surface focus:ring-4 focus:ring-lavender-100 focus:outline-none",
    className,
  );
  return multiline ? (
    <textarea aria-label={ariaLabel} rows={Math.max(1, Math.ceil(v.length / 70))} className={cx(cls, "resize-none")} value={v} placeholder={placeholder} onChange={(e) => setV(e.target.value)} onBlur={commit} onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && (e.preventDefault(), (e.target as HTMLTextAreaElement).blur())} />
  ) : (
    <input aria-label={ariaLabel} list={list} className={cls} value={v} placeholder={placeholder} onChange={(e) => setV(e.target.value)} onBlur={commit} onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()} />
  );
}

function ActionCard({ item, base, onDelete }: { item: ActionItem; base: string | null; onDelete: () => void }) {
  const { updateAction } = useWorkspace();
  const d = item.deadline;
  const days = daysFrom(base, d?.normalized_date);
  return (
    <article className={cx("card p-5 transition", item.status === "done" && "opacity-75")} id={`action-${item.id}`}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-md bg-mist px-1.5 py-0.5 text-[11px] font-semibold text-muted">{item.id}</span>
        <select
          aria-label="Status"
          value={item.status}
          onChange={(e) => updateAction(item.id, { status: e.target.value as ActionStatus })}
          className={cx("cursor-pointer rounded-full border-0 py-0.5 pr-7 pl-2.5 text-xs font-medium focus:ring-2 focus:ring-lavender-200", STATUS_TONE[item.status])}
        >
          {Object.entries(STATUS_LABEL).map(([k, label]) => (
            <option key={k} value={k}>{label}</option>
          ))}
        </select>
        <select
          aria-label="Priority"
          value={item.priority}
          onChange={(e) => updateAction(item.id, { priority: e.target.value as Priority })}
          className="cursor-pointer rounded-full border border-line bg-surface py-0.5 pr-7 pl-2.5 text-xs text-muted focus:ring-2 focus:ring-lavender-200"
        >
          <option value="high">High priority</option>
          <option value="medium">Medium priority</option>
          <option value="low">Low priority</option>
        </select>
        {!item.edited && <SignalBadge signal={item.signal} />}
        {item.is_inferred && <Badge title="The owner or task was inferred from context, not stated outright.">inferred</Badge>}
        {item.edited && <Badge tone="blush">edited</Badge>}
        {item.needs_review && (
          <Badge tone="amber" title={item.review_reasons.join("\n")}>
            <Flag className="h-3 w-3" /> needs review
          </Badge>
        )}
        <button onClick={onDelete} className="ml-auto rounded-lg p-1.5 text-faint transition hover:bg-rose-50 hover:text-rose-600" aria-label={`Delete ${item.id}`} title="Delete">
          <Trash2 className="h-4 w-4" />
        </button>
      </div>

      <div className="mt-3">
        <InlineText
          multiline
          ariaLabel="Task description"
          value={item.description}
          onCommit={(v) => v && updateAction(item.id, { description: v })}
          className={cx("text-[15.5px] font-medium text-ink", item.status === "done" && "line-through decoration-faint")}
        />
      </div>

      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <div>
          <div className="mb-0.5 flex items-center gap-1 text-[11px] font-medium tracking-wide text-faint uppercase">
            <UserRound className="h-3 w-3" /> Owner
          </div>
          <InlineText
            ariaLabel="Owner"
            list="mm-people"
            value={item.owner}
            placeholder="Unassigned"
            onCommit={(v) => updateAction(item.id, { owner: v })}
            className={cx("text-sm", item.owner === "Unassigned" ? "text-amber-600" : "text-ink")}
          />
          <div className="text-[11px] text-faint">{OWNER_SOURCE_LABEL[item.owner_source]}</div>
        </div>
        <div>
          <div className="mb-0.5 text-[11px] font-medium tracking-wide text-faint uppercase">Deadline</div>
          <div className="flex items-center gap-2">
            <input
              type="date"
              aria-label="Deadline date"
              value={d?.normalized_date ?? ""}
              onChange={(e) => updateAction(item.id, { deadlineDate: e.target.value || null, deadlineText: e.target.value || "" })}
              className="rounded-lg border border-line bg-surface px-2 py-1 text-sm text-ink focus:border-violet-400 focus:ring-4 focus:ring-lavender-100 focus:outline-none"
            />
            {d?.normalized_date && <span className="text-xs text-faint">{relativeLabel(days)}</span>}
          </div>
          {d && (
            <div className={cx("mt-0.5 text-[11px]", d.is_ambiguous ? "text-amber-600" : "text-faint")}>
              {d.date_type === "user" ? "Set by you" : `Said: “${d.text}”`}
              {d.normalized_date && d.date_type !== "user" && ` → ${formatDate(d.normalized_date, { weekday: "short" })}`}
              {!d.normalized_date && " (no date resolved)"}
            </div>
          )}
        </div>
      </div>

      {item.needs_review && item.review_reasons.length > 0 && (
        <div className="mt-3 flex items-start gap-2 rounded-xl bg-amber-50 px-3 py-2 text-xs text-amber-600">
          <Flag className="mt-px h-3.5 w-3.5 shrink-0" />
          <span className="flex-1">{item.review_reasons.join(" ")}</span>
          <button onClick={() => updateAction(item.id, { needs_review: false })} className="shrink-0 font-medium underline-offset-2 hover:underline">
            Mark reviewed
          </button>
        </div>
      )}
      <div className="mt-3">
        <EvidenceList evidence={item.evidence} />
      </div>
    </article>
  );
}

export function ActionItems() {
  const { report, addAction, deleteAction, updateAction } = useWorkspace();
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<"all" | ActionStatus>("all");
  const [owner, setOwner] = useState("all");
  const [reviewOnly, setReviewOnly] = useState(false);
  const [sort, setSort] = useState<SortKey>("order");
  const [toDelete, setToDelete] = useState<ActionItem | null>(null);

  const items = report?.action_items ?? [];
  const owners = useMemo(() => Array.from(new Set(items.map((a) => a.owner))).sort(), [items]);
  const people = useMemo(() => Array.from(new Set([...(report?.people.map((p) => p.name) ?? []), "Unassigned"])), [report]);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = items.filter(
      (a) =>
        (status === "all" || a.status === status) &&
        (owner === "all" || a.owner === owner) &&
        (!reviewOnly || a.needs_review) &&
        (!q || a.description.toLowerCase().includes(q) || a.owner.toLowerCase().includes(q)),
    );
    const order = new Map(items.map((a, i) => [a.id, i]));
    const cmp: Record<SortKey, (a: ActionItem, b: ActionItem) => number> = {
      order: (a, b) => order.get(a.id)! - order.get(b.id)!,
      deadline: (a, b) => (a.deadline?.normalized_date ?? "9999").localeCompare(b.deadline?.normalized_date ?? "9999"),
      owner: (a, b) => (a.owner === "Unassigned" ? 1 : 0) - (b.owner === "Unassigned" ? 1 : 0) || a.owner.localeCompare(b.owner),
      priority: (a, b) => PRIORITY_RANK[a.priority] - PRIORITY_RANK[b.priority],
      status: (a, b) => STATUS_RANK[a.status] - STATUS_RANK[b.status],
    };
    return [...list].sort((a, b) => cmp[sort](a, b) || order.get(a.id)! - order.get(b.id)!);
  }, [items, query, status, owner, reviewOnly, sort]);

  if (!report) return null;
  const reviewCount = items.filter((a) => a.needs_review).length;
  const doneCount = items.filter((a) => a.status === "done").length;

  function add() {
    const id = addAction();
    setStatus("all");
    setOwner("all");
    setReviewOnly(false);
    setQuery("");
    setTimeout(() => document.getElementById(`action-${id}`)?.scrollIntoView({ behavior: "smooth", block: "center" }), 60);
  }

  return (
    <div className="space-y-5">
      <SectionHeader
        eyebrow="Action items"
        title="Who does what, by when"
        description="Edit any task, owner, deadline or status — changes update this report and every export. Flagged items had an inferred owner, an unclear date, or weak evidence."
        actions={
          <Button icon={<Plus className="h-4 w-4" />} onClick={add}>
            Add task
          </Button>
        }
      />

      <div className="card flex flex-col gap-3 p-3 lg:flex-row lg:items-center">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-faint" />
          <input className="field h-9 pl-9" placeholder="Search tasks or owners" value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Search action items" />
        </div>
        <div className="flex flex-wrap gap-2">
          <select className="field h-9 w-auto py-0" value={status} onChange={(e) => setStatus(e.target.value as typeof status)} aria-label="Filter by status">
            <option value="all">All statuses</option>
            {Object.entries(STATUS_LABEL).map(([k, l]) => (
              <option key={k} value={k}>{l}</option>
            ))}
          </select>
          <select className="field h-9 w-auto py-0" value={owner} onChange={(e) => setOwner(e.target.value)} aria-label="Filter by owner">
            <option value="all">All owners</option>
            {owners.map((o) => (
              <option key={o} value={o}>{o}</option>
            ))}
          </select>
          <select className="field h-9 w-auto py-0" value={sort} onChange={(e) => setSort(e.target.value as SortKey)} aria-label="Sort">
            <option value="order">Sort: transcript order</option>
            <option value="deadline">Sort: deadline</option>
            <option value="owner">Sort: owner</option>
            <option value="priority">Sort: priority</option>
            <option value="status">Sort: status</option>
          </select>
          <button
            onClick={() => setReviewOnly((r) => !r)}
            aria-pressed={reviewOnly}
            className={cx("inline-flex h-9 items-center gap-1.5 rounded-xl border px-3 text-sm transition", reviewOnly ? "border-amber-600/30 bg-amber-50 text-amber-600" : "border-line-strong text-muted hover:text-ink")}
          >
            <Flag className="h-3.5 w-3.5" /> Needs review ({reviewCount})
          </button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted">
        <span>
          Showing {visible.length} of {items.length}
        </span>
        <span>
          {doneCount} done · {items.filter((a) => a.owner === "Unassigned").length} unassigned
        </span>
        {reviewCount > 0 && (
          <button className="inline-flex items-center gap-1 text-violet-600 hover:underline" onClick={() => items.filter((a) => a.needs_review).forEach((a) => updateAction(a.id, { needs_review: false }))}>
            <CheckCheck className="h-3.5 w-3.5" /> Mark all reviewed
          </button>
        )}
        <span className="inline-flex items-center gap-1 text-faint" title="The signal label combines how explicit the wording is with a semantic similarity check. It is a heuristic, not a calibrated probability.">
          <Info className="h-3.5 w-3.5" /> About “signal”
        </span>
      </div>

      <datalist id="mm-people">
        {people.map((p) => (
          <option key={p} value={p} />
        ))}
      </datalist>

      {items.length === 0 ? (
        <EmptyState icon={<ListChecks className="h-5 w-5" />} title="No action items detected">
          Nobody clearly committed to or was asked to do something. Use “Add task” to record one manually.
        </EmptyState>
      ) : visible.length === 0 ? (
        <EmptyState title="No tasks match these filters" />
      ) : (
        <div className="space-y-3">
          {visible.map((a) => (
            <ActionCard key={a.id} item={a} base={report.meeting.date} onDelete={() => setToDelete(a)} />
          ))}
        </div>
      )}

      <ConfirmDialog
        open={toDelete !== null}
        title="Delete this action item?"
        confirmLabel="Delete"
        onCancel={() => setToDelete(null)}
        onConfirm={() => {
          if (toDelete) deleteAction(toDelete.id);
          setToDelete(null);
        }}
      >
        “{toDelete?.description}” will be removed from the report and from all exports.
      </ConfirmDialog>
    </div>
  );
}
