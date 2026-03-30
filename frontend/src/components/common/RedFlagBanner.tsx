import type { RedFlagAlert } from "../../types";

interface Props {
  flags: RedFlagAlert[];
  onAcknowledge?: (flagId: string) => void;
  compact?: boolean;
}

function severityStyles(severity: RedFlagAlert["severity"]): string {
  switch (severity) {
    case "emergency":
      return "border-red-600 bg-red-50 text-red-900";
    case "urgent":
      return "border-red-500 bg-red-50 text-red-800";
    case "elevated":
      return "border-amber-500 bg-amber-50 text-amber-900";
  }
}

function severityIcon(severity: RedFlagAlert["severity"]): JSX.Element {
  if (severity === "emergency" || severity === "urgent") {
    return (
      <svg className="h-5 w-5 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4.5c-.77-.833-2.694-.833-3.464 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z" />
      </svg>
    );
  }
  return (
    <svg className="h-5 w-5 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M12 2a10 10 0 100 20 10 10 0 000-20z" />
    </svg>
  );
}

export function RedFlagBanner({ flags, onAcknowledge, compact }: Props) {
  const unacknowledged = flags.filter((f) => !f.acknowledged);

  if (unacknowledged.length === 0) return null;

  return (
    <div className="space-y-2">
      {unacknowledged.map((flag) => (
        <div
          key={flag.id}
          className={`flex items-start gap-3 rounded-lg border-l-4 p-3 ${severityStyles(flag.severity)}`}
          role="alert"
        >
          <div className="mt-0.5 shrink-0">{severityIcon(flag.severity)}</div>
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <span className="rounded-full bg-white/60 px-2 py-0.5 text-xs font-semibold uppercase tracking-wide">
                {flag.severity}
              </span>
              {!compact && (
                <span className="text-sm font-semibold">Red Flag Alert</span>
              )}
            </div>
            <p className={`mt-1 text-sm ${compact ? "line-clamp-1" : ""}`}>
              {flag.trigger_description}
            </p>
          </div>
          {onAcknowledge && (
            <button
              onClick={() => onAcknowledge(flag.id)}
              className="shrink-0 rounded-md bg-white/80 px-3 py-1 text-xs font-medium hover:bg-white"
            >
              Acknowledge
            </button>
          )}
        </div>
      ))}
    </div>
  );
}
