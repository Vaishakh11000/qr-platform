function labelFor(key: string): string {
  return key.replaceAll("_", " ");
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export default function StructuredValue({ value }: { value: unknown }) {
  if (Array.isArray(value)) {
    if (value.length === 0) return <span>—</span>;
    return (
      <ul className="flex flex-wrap gap-2">
        {value.map((item, index) => (
          <li
            key={index}
            className="max-w-full rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-700"
          >
            <StructuredValue value={item} />
          </li>
        ))}
      </ul>
    );
  }

  if (isRecord(value)) {
    const entries = Object.entries(value).filter(([, item]) => item != null && item !== "");
    if (entries.length === 0) return <span>—</span>;
    return (
      <dl className="grid gap-x-5 gap-y-3 sm:grid-cols-2">
        {entries.map(([key, item]) => (
          <div key={key} className="min-w-0">
            <dt className="text-xs font-medium capitalize text-slate-500">{labelFor(key)}</dt>
            <dd className="mt-1 break-words text-sm font-medium text-slate-800">
              <StructuredValue value={item} />
            </dd>
          </div>
        ))}
      </dl>
    );
  }

  if (typeof value === "boolean") return <span>{value ? "Yes" : "No"}</span>;
  if (value == null || value === "") return <span>—</span>;
  return <span className="whitespace-pre-line break-words">{String(value)}</span>;
}
