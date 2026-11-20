interface Props {
  content: Record<string, unknown>
}

function VersionSnapshotView({ content }: Props) {
  const name = typeof content.name === 'string' ? content.name : ''
  const description =
    typeof content.description === 'string' ? content.description : ''

  const features = Array.isArray(content.features)
    ? content.features
    : []

  const benefits = Array.isArray(content.benefits)
    ? content.benefits
    : []

  const applications = Array.isArray(content.applications)
    ? content.applications
    : []

  const supportedMaterials = Array.isArray(content.supported_materials)
    ? content.supported_materials
    : []

  const specifications =
    content.specifications &&
    typeof content.specifications === 'object' &&
    !Array.isArray(content.specifications)
      ? Object.entries(content.specifications as Record<string, unknown>)
      : []

  const standardFields = [
    'name', 'description', 'features', 'benefits',
    'applications', 'supported_materials', 'specifications',
  ]
  const customFields = Object.entries(content).filter(
    ([key]) => !standardFields.includes(key),
  )

  function displayValue(value: unknown): string {
    if (value === null || value === undefined) return '—'
    if (typeof value === 'object') return JSON.stringify(value, null, 2)
    return String(value)
  }

  return (
    <div className="mt-3 space-y-4 rounded-xl border border-white/[0.07] bg-slate-950/50 p-4">
      {name && (
        <div>
          <p className="text-[10px] uppercase tracking-wider text-slate-500">
            Product name
          </p>
          <h4 className="mt-1 text-sm font-semibold text-white">{name}</h4>
        </div>
      )}

      {description && (
        <div>
          <p className="text-[10px] uppercase tracking-wider text-slate-500">
            Description
          </p>
          <p className="mt-1 whitespace-pre-wrap text-xs leading-5 text-slate-300">
            {description}
          </p>
        </div>
      )}

      {features.length > 0 && (
        <div>
          <p className="mb-2 text-[10px] uppercase tracking-wider text-slate-500">
            Features
          </p>
          <ul className="space-y-2">
            {features.map((feature, index) => (
              <li key={index} className="flex gap-2 text-xs text-slate-300">
                <span className="text-emerald-400">•</span>
                {displayValue(feature)}
              </li>
            ))}
          </ul>
        </div>
      )}

      {benefits.length > 0 && (
        <div>
          <p className="mb-2 text-[10px] uppercase tracking-wider text-slate-500">
            Benefits
          </p>
          <ul className="space-y-2">
            {benefits.map((item, index) => (
              <li key={index} className="flex gap-2 text-xs text-slate-300">
                <span className="text-emerald-400">•</span>
                {displayValue(item)}
              </li>
            ))}
          </ul>
        </div>
      )}

      {applications.length > 0 && (
        <div>
          <p className="mb-2 text-[10px] uppercase tracking-wider text-slate-500">
            Applications
          </p>
          <ul className="space-y-2">
            {applications.map((item, index) => (
              <li key={index} className="flex gap-2 text-xs text-slate-300">
                <span className="text-emerald-400">•</span>
                {displayValue(item)}
              </li>
            ))}
          </ul>
        </div>
      )}

      {supportedMaterials.length > 0 && (
        <div>
          <p className="mb-2 text-[10px] uppercase tracking-wider text-slate-500">
            Supported materials
          </p>
          <ul className="space-y-2">
            {supportedMaterials.map((item, index) => (
              <li key={index} className="flex gap-2 text-xs text-slate-300">
                <span className="text-emerald-400">•</span>
                {displayValue(item)}
              </li>
            ))}
          </ul>
        </div>
      )}

      {specifications.length > 0 && (
        <div>
          <p className="mb-2 text-[10px] uppercase tracking-wider text-slate-500">
            Specifications
          </p>
          <div className="overflow-hidden rounded-lg border border-white/[0.07]">
            {specifications.map(([key, value]) => (
              <div
                key={key}
                className="grid grid-cols-2 gap-3 border-b border-white/[0.06] px-3 py-2 last:border-0"
              >
                <span className="text-xs text-slate-400">{key}</span>
                <span className="break-words text-right text-xs text-slate-200">
                  {displayValue(value)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {customFields.length > 0 && (
        <div>
          <p className="mb-2 text-[10px] uppercase tracking-wider text-slate-500">
            Additional information
          </p>
          <div className="space-y-2">
            {customFields.map(([key, value]) => (
              <div
                key={key}
                className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-3"
              >
                <p className="text-xs font-medium text-slate-300">{key}</p>
                <p className="mt-1 whitespace-pre-wrap break-words text-xs text-slate-400">
                  {displayValue(value)}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {!name && !description && features.length === 0 &&
        benefits.length === 0 && applications.length === 0 &&
        supportedMaterials.length === 0 &&
        specifications.length === 0 && customFields.length === 0 && (
          <p className="text-xs text-slate-500">This version has no content.</p>
        )}
    </div>
  )
}

export default VersionSnapshotView
