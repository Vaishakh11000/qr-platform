import StructuredValue from "./structured-value";

export interface ProductDetailsProps {
  features: unknown[];
  benefits: unknown[];
  applications: unknown[];
  materials: unknown[];
  specifications: Record<string, unknown>;
  customFields: [string, unknown][];
}

export default function ProductDetails({
  features,
  benefits,
  applications,
  materials,
  specifications,
  customFields,
}: ProductDetailsProps) {
  return (
    <>
      {features.length > 0 && (
        <section>
          <h2 className="text-2xl font-bold">Key features</h2>
          <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {features.map((feature, index) => (
              <div key={index} className="rounded-xl border border-slate-200 bg-white p-6">
                <span className="text-xs font-bold text-slate-400">FEATURE {String(index + 1).padStart(2, "0")}</span>
                <div className="mt-3 font-semibold"><StructuredValue value={feature} /></div>
              </div>
            ))}
          </div>
        </section>
      )}

      {benefits.length > 0 && (
        <section>
          <h2 className="text-2xl font-bold">Benefits</h2>
          <ul className="mt-6 grid gap-3 sm:grid-cols-2">
            {benefits.map((benefit, index) => (
              <li key={index} className="rounded-lg bg-white p-5 leading-7 text-slate-700">
                <StructuredValue value={benefit} />
              </li>
            ))}
          </ul>
        </section>
      )}

      {Object.keys(specifications).length > 0 && (
        <section>
          <h2 className="text-2xl font-bold">Technical specifications</h2>
          <div className="mt-6 overflow-hidden rounded-xl border border-slate-200 bg-white">
            {Object.entries(specifications).map(([key, value]) => (
              <div key={key} className="grid grid-cols-1 gap-2 border-b border-slate-100 p-5 last:border-0 sm:grid-cols-2">
                <span className="text-sm font-semibold capitalize text-slate-500">{key.replaceAll("_", " ")}</span>
                <div className="min-w-0 text-sm font-medium"><StructuredValue value={value} /></div>
              </div>
            ))}
          </div>
        </section>
      )}

      {customFields.length > 0 && (
        <section>
          <h2 className="text-2xl font-bold">Additional product information</h2>
          <div className="mt-6 overflow-hidden rounded-xl border border-slate-200 bg-white">
            {customFields.map(([key, value]) => (
              <div key={key} className="grid grid-cols-1 gap-2 border-b border-slate-100 p-5 last:border-0 sm:grid-cols-2">
                <span className="text-sm font-semibold capitalize text-slate-500">{key.replaceAll("_", " ")}</span>
                <div className="min-w-0 text-sm font-medium"><StructuredValue value={value} /></div>
              </div>
            ))}
          </div>
        </section>
      )}

      {applications.length > 0 && (
        <section>
          <h2 className="text-2xl font-bold">Applications</h2>
          <div className="mt-6 flex flex-wrap gap-3">
            {applications.map((item, index) => (
              <div key={index} className="rounded-full bg-[#e7edf1] px-5 py-3 text-sm font-medium">
                <StructuredValue value={item} />
              </div>
            ))}
          </div>
        </section>
      )}

      {materials.length > 0 && (
        <section>
          <h2 className="text-2xl font-bold">Supported materials</h2>
          <div className="mt-6 flex flex-wrap gap-3">
            {materials.map((item, index) => (
              <div key={index} className="rounded-full border border-slate-300 bg-white px-5 py-3 text-sm font-medium">
                <StructuredValue value={item} />
              </div>
            ))}
          </div>
        </section>
      )}
    </>
  );
}
