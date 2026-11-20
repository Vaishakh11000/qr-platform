import QrLookupForm from "../components/qr-lookup-form";

const steps = [
  {
    number: "01",
    title: "Scan the product QR",
    description: "Use your phone camera to open the link attached to the product.",
  },
  {
    number: "02",
    title: "Verify access",
    description: "If the product has a location rule, the page will explain what it needs.",
  },
  {
    number: "03",
    title: "View product details",
    description: "See the product information and files made available for that code.",
  },
];

export default function Home() {
  return (
    <main className="relative isolate flex flex-1 flex-col overflow-hidden bg-[#f4f6f7] text-[#202a32]">
      <div aria-hidden="true" className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-[34rem] bg-[radial-gradient(ellipse_at_top,_rgba(63,95,112,0.13),_transparent_65%)]" />

      <header className="border-b border-slate-200/80 bg-white/80">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-5 sm:px-8">
          <div>
            <p className="text-sm font-bold tracking-[0.16em] text-[#243b4a]">PRODUCT INFORMATION</p>
            <p className="mt-1 text-[10px] tracking-[0.2em] text-slate-500">QR PRODUCT EXPERIENCE</p>
          </div>
          <span className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">
            Scan to connect
          </span>
        </div>
      </header>

      <section className="mx-auto grid w-full max-w-6xl flex-1 items-center gap-12 px-5 py-14 sm:px-8 sm:py-20 lg:grid-cols-[1.1fr_0.9fr] lg:gap-16">
        <div className="max-w-2xl">
          <p className="inline-flex items-center gap-2 rounded-full border border-[#cbd7dd] bg-white/80 px-3 py-1.5 text-xs font-medium text-[#3d5868]">
            <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
            Product details, one scan away
          </p>
          <h1 className="mt-6 text-4xl font-semibold leading-[1.1] tracking-tight text-[#1d2b34] sm:text-5xl lg:text-6xl">
            The right product information, right where you need it.
          </h1>
          <p className="mt-5 max-w-xl text-base leading-7 text-slate-600 sm:text-lg sm:leading-8">
            Scan the QR code on your product to open its current information, specifications and available files.
          </p>

          <div className="mt-9 rounded-2xl border border-slate-200 bg-white p-5 shadow-[0_18px_55px_-38px_rgba(26,47,60,0.4)] sm:p-6">
            <QrLookupForm />
          </div>

          <p className="mt-4 text-xs leading-5 text-slate-500">
            Access may depend on the product’s configured location policy.
          </p>
        </div>

        <aside className="rounded-3xl border border-[#dce4e8] bg-white/85 p-6 shadow-[0_28px_70px_-48px_rgba(26,47,60,0.55)] sm:p-8">
          <div className="flex items-start justify-between gap-4 border-b border-slate-100 pb-6">
            <div>
              <p className="text-[10px] font-bold tracking-[0.2em] text-slate-500">HOW IT WORKS</p>
              <h2 className="mt-2 text-xl font-semibold tracking-tight text-[#223440]">From QR code to product details</h2>
            </div>
            <div aria-hidden="true" className="grid h-12 w-12 shrink-0 grid-cols-3 gap-1 rounded-xl bg-[#edf2f4] p-2.5">
              <span className="rounded-sm bg-[#2c4656]" />
              <span className="rounded-sm bg-[#2c4656]" />
              <span className="rounded-sm bg-[#2c4656]" />
              <span className="rounded-sm bg-[#2c4656]" />
              <span className="rounded-sm bg-[#9bb0bb]" />
              <span className="rounded-sm bg-[#2c4656]" />
              <span className="rounded-sm bg-[#2c4656]" />
              <span className="rounded-sm bg-[#2c4656]" />
              <span className="rounded-sm bg-[#2c4656]" />
            </div>
          </div>

          <ol className="mt-2 divide-y divide-slate-100">
            {steps.map((step) => (
              <li key={step.number} className="flex gap-4 py-5">
                <span className="pt-0.5 font-mono text-xs font-semibold text-[#78909d]">{step.number}</span>
                <div>
                  <h3 className="text-sm font-semibold text-slate-800">{step.title}</h3>
                  <p className="mt-1 text-sm leading-6 text-slate-500">{step.description}</p>
                </div>
              </li>
            ))}
          </ol>
        </aside>
      </section>

      <footer className="border-t border-slate-200/80 bg-white/70">
        <div className="mx-auto flex max-w-6xl flex-col gap-2 px-5 py-5 text-xs text-slate-500 sm:flex-row sm:items-center sm:justify-between sm:px-8">
          <span>Digital Product Catalogue</span>
          <span>Use the product’s QR code for version-specific information.</span>
        </div>
      </footer>
    </main>
  );
}
