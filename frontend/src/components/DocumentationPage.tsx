import { BookOpen, ChevronRight, X } from 'lucide-react'

type Props = {
  open: boolean
  onClose: () => void
  onNavigate: (page: string) => void
}

const topics = [
  ['#guide-catalogue', 'Catalogue hierarchy'],
  ['#guide-qr', 'QR batches and allocation'],
  ['#guide-regions', 'Regions and boundaries'],
  ['#guide-policies', 'Location policy precedence'],
  ['#guide-forms', 'Forms and assignments'],
  ['#guide-analytics', 'Analytics and audit'],
  ['#guide-settings', 'Settings and integrations'],
  ['#guide-troubleshooting', 'Common checks'],
]

export default function DocumentationPage({ open, onClose, onNavigate }: Props) {
  if (!open) return null

  function goTo(page: string) {
    onClose()
    onNavigate(page)
  }

  const sectionClass = 'scroll-mt-4 rounded-xl border border-white/[0.07] bg-white/[0.02] p-5'
  const headingClass = 'text-sm font-semibold text-white'
  const bodyClass = 'mt-2 text-xs leading-6 text-slate-400'

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/75 p-3 sm:p-6" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose() }}>
      <section role="dialog" aria-modal="true" aria-labelledby="quick-guide-title" className="flex max-h-[94vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl border border-white/10 bg-[#101827] shadow-2xl">
        <header className="flex items-start justify-between gap-4 border-b border-white/[0.08] px-5 py-4 sm:px-7">
          <div>
            <p className="text-xs text-slate-500">Administrator guide</p>
            <h2 id="quick-guide-title" className="mt-1 flex items-center gap-2 text-lg font-semibold text-white"><BookOpen size={18} /> QR Platform workflows and hierarchies</h2>
            <p className="mt-1 text-xs text-slate-400">How catalogue versions, QR allocations, regions, policies, forms, and scans work together.</p>
          </div>
          <button onClick={onClose} aria-label="Close documentation" className="rounded p-1 text-slate-500 hover:bg-white/[0.06] hover:text-white"><X size={18} /></button>
        </header>

        <div className="overflow-y-auto px-5 py-5 sm:px-7 sm:py-6">
          <div className="mb-5 rounded-xl border border-blue-400/15 bg-blue-400/[0.04] p-4">
            <h3 className="text-xs font-semibold text-blue-100">Customer scan path</h3>
            <p className="mt-2 text-xs leading-6 text-slate-300">A product needs a published version. An active QR code needs a current product and region allocation. The scan resolves the location policy from that allocation, then serves the published product page and any applicable forms.</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {[
                ['Products', 'Products'], ['QR Batches', 'QR Batches'], ['Regions', 'Regions'],
                ['Location Policies', 'Location Policies'], ['Forms', 'Forms'],
              ].map(([label, page]) => <button key={page} onClick={() => goTo(page)} className="inline-flex items-center gap-1 rounded-md border border-white/10 px-2.5 py-1.5 text-[10px] text-slate-300 hover:border-blue-400/30 hover:text-white">{label}<ChevronRight size={11} /></button>)}
            </div>
          </div>

          <nav aria-label="Guide topics" className="mb-5 grid gap-2 rounded-xl border border-white/[0.07] p-4 sm:grid-cols-2 lg:grid-cols-4">
            {topics.map(([href, label]) => <a key={href} href={href} className="rounded-md px-2 py-1.5 text-xs text-blue-300 hover:bg-white/[0.04] hover:text-blue-200">{label}</a>)}
          </nav>

          <div className="space-y-4">
            <section id="guide-catalogue" className={sectionClass}>
              <div className="flex flex-wrap items-center justify-between gap-2"><h3 className={headingClass}>1. Catalogue hierarchy</h3><button onClick={() => goTo('Products')} className="text-[10px] text-blue-300 hover:text-blue-200">Open Products →</button></div>
              <div className="mt-3 rounded-lg bg-[#0b1220] p-3 font-mono text-[11px] leading-6 text-slate-300">Category tree → Product → Versions (draft → published → retired)<br />Product media → attached to product or a draft version</div>
              <p className={bodyClass}>Categories can contain child categories, but a product has one direct category assignment. Parent categories organize the catalogue; they do not automatically assign themselves to products in child categories. Category and region hierarchies are separate. Deactivating a category keeps existing product links visible, but prevents new products or reassignment to that category.</p>
              <p className={bodyClass}>Edit a draft product version, review the preview and media, then publish it. Publishing makes that version current and retires the previous published version. Published versions are immutable; create a new version for changes. Customers see published content only, and stored scans keep the product version they showed.</p>
              <button onClick={() => goTo('Categories')} className="mt-3 text-[10px] text-blue-300 hover:text-blue-200">Manage categories →</button>
            </section>

            <section id="guide-qr" className={sectionClass}>
              <div className="flex flex-wrap items-center justify-between gap-2"><h3 className={headingClass}>2. QR batches, codes, and allocations</h3><button onClick={() => goTo('QR Batches')} className="text-[10px] text-blue-300 hover:text-blue-200">Open QR Batches →</button></div>
              <div className="mt-3 rounded-lg bg-[#0b1220] p-3 font-mono text-[11px] leading-6 text-slate-300">Batch → many QR codes → one current allocation per active code → Product + Region</div>
              <p className={bodyClass}>Generate codes in QR Batches. Selecting a product and region during generation allocates the codes immediately; otherwise, use Allocate / reassign on the batch. Batch allocation affects its active codes. Reassignment changes where future scans go and retains allocation history; prior scans keep their original product, version, and region.</p>
              <p className={bodyClass}>Share / export creates a printable PDF or a ZIP of PNG or SVG files. ZIP manifests map each image to its QR token, scan URL, and current product and region. Exports contain active codes only. Treat QR archives as access links and share them only with intended recipients. Retiring a batch revokes its active codes.</p>
              <button onClick={() => goTo('QR Codes')} className="mt-3 text-[10px] text-blue-300 hover:text-blue-200">Review individual QR codes →</button>
            </section>

            <section id="guide-regions" className={sectionClass}>
              <div className="flex flex-wrap items-center justify-between gap-2"><h3 className={headingClass}>3. Region tree and boundaries</h3><button onClick={() => goTo('Regions')} className="text-[10px] text-blue-300 hover:text-blue-200">Open Regions →</button></div>
              <div className="mt-3 rounded-lg bg-[#0b1220] p-3 font-mono text-[11px] leading-6 text-slate-300">Country → State → District → Sales territory</div>
              <p className={bodyClass}>Set Parent region to make a child in the tree. A region can also have a geographic boundary, stored as a valid 2D WGS84 MultiPolygon. Parent links drive policy and form cascading; they do not draw, merge, or constrain geographic boundaries automatically.</p>
              <p className={bodyClass}>GPS classification chooses the deepest active region boundary covering the point. If overlapping sibling regions match at the same deepest level, the result is ambiguous and reported as unknown. GPS accuracy must be present and no worse than 500 metres. A detected region matches the QR's assigned region when it is that region or one of its descendants; a different region outside that subtree is a mismatch.</p>
            </section>

            <section id="guide-policies" className={sectionClass}>
              <div className="flex flex-wrap items-center justify-between gap-2"><h3 className={headingClass}>4. Location policy hierarchy and precedence</h3><button onClick={() => goTo('Location Policies')} className="text-[10px] text-blue-300 hover:text-blue-200">Open Location Policies →</button></div>
              <p className={bodyClass}>Policies can be assigned to a region, product, or globally. For each scan, the allocated region is checked first, then its parent and successive ancestors. The closest matching region policy wins. If no region policy applies, the product policy wins; the global policy is the final fallback. Inactive policies are ignored. Only one assignment can target an exact region, product, or global scope at once.</p>
              <p className={bodyClass}>Priority is stored on assignments, but duplicate assignments for the same exact target are rejected, so priority normally does not change rule selection. Use hierarchy and scope precedence: region specificity comes before product and global. Mandatory policies block access when required location cannot be verified; skippable policies allow access when location is skipped or unavailable.</p>
              <div className="mt-3 rounded-lg border border-amber-400/15 bg-amber-400/[0.04] p-3 text-xs leading-5 text-amber-100">GPS with IP fallback and IP only are listed as policy methods, but this deployment has no IP geolocation provider configured. A private Wi-Fi IP address cannot identify a region. For phone GPS testing, use the HTTPS LAN site, trust its local certificate on the phone, enable device location, and allow this site. A saved denial must be changed in browser settings before starting a new scan.</div>
            </section>

            <section id="guide-forms" className={sectionClass}>
              <div className="flex flex-wrap items-center justify-between gap-2"><h3 className={headingClass}>5. Forms and assignment hierarchy</h3><button onClick={() => goTo('Forms')} className="text-[10px] text-blue-300 hover:text-blue-200">Open Forms →</button></div>
              <div className="mt-3 rounded-lg bg-[#0b1220] p-3 font-mono text-[11px] leading-6 text-slate-300">Form → draft version → published version → assignment scope</div>
              <p className={bodyClass}>Publish a form version before assigning it. Assignments can be global, product-specific, or region-specific; region assignments cascade to child regions. For each form, the closest region assignment takes precedence over product and global assignments. Separate applicable forms can all appear together. Required or optional labels describe expected response collection; the product page stays visible, and required field validation applies when a customer submits. Replacing an assignment at the same form and exact scope deactivates the old assignment while keeping history.</p>
              <p className={bodyClass}>Form submissions are available in the admin form workflow. The page shows submissions in pages and its CSV export includes all matching pages.</p>
            </section>

            <section id="guide-analytics" className={sectionClass}>
              <div className="flex flex-wrap items-center justify-between gap-2"><h3 className={headingClass}>6. Analytics and audit history</h3><div className="flex gap-3"><button onClick={() => goTo('Scan Analytics')} className="text-[10px] text-blue-300 hover:text-blue-200">Scan Analytics →</button><button onClick={() => goTo('Audit Logs')} className="text-[10px] text-blue-300 hover:text-blue-200">Audit Logs →</button></div></div>
              <p className={bodyClass}>Scan Analytics filters stored events by UTC date range, product, QR code, region, scan outcome, and location outcome. The maximum date range is 366 days. Summary totals and daily trends include all matching events; product, region, and QR breakdowns each show up to 100 rows. CSV files include the filters and state this breakdown limit.</p>
              <p className={bodyClass}>Audit Logs record administrator actions, affected entities, timestamps, and before/after values where available. Filtered CSV export includes all matching pages. Date filters and exported timestamps use UTC. Some system-generated events have no administrator account.</p>
            </section>

            <section id="guide-settings" className={sectionClass}>
              <div className="flex flex-wrap items-center justify-between gap-2"><h3 className={headingClass}>7. Administration and deployment settings</h3><button onClick={() => goTo('Administration')} className="text-[10px] text-blue-300 hover:text-blue-200">Open Administration →</button></div>
              <p className={bodyClass}>Set Public QR address to the customer-reachable address. New QR links and exports use it; already printed codes do not change. Check HTTPS, DNS, and phone reachability before distributing a batch. The LAN preview uses a local certificate authority that each phone must trust. For a public release, use a real domain and externally provisioned, trusted TLS certificates.</p>
              <p className={bodyClass}>IP geolocation, outbound email/push, and external monitoring are not connected in this release. The integrations area labels these honestly. Backup, restore, and deployment instructions are in the operations guide.</p>
            </section>

            <section id="guide-troubleshooting" className={sectionClass}>
              <h3 className={headingClass}>8. Common checks</h3>
              <ul className="mt-3 space-y-2 text-xs leading-5 text-slate-400">
                <li><b className="text-slate-200">QR has no product:</b> check the batch's current allocation and confirm the code is active.</li>
                <li><b className="text-slate-200">Product page unavailable:</b> make sure the product is not archived and has a published version.</li>
                <li><b className="text-slate-200">Phone opens localhost:</b> set the Public QR address to a host address the phone can reach or a real HTTPS domain.</li>
                <li><b className="text-slate-200">Location remains denied:</b> allow location for this site in browser settings, then start a new scan.</li>
                <li><b className="text-slate-200">Region result unknown:</b> check boundary coverage, GPS accuracy, active status, and overlapping sibling boundaries.</li>
                <li><b className="text-slate-200">Inactive category:</b> existing products keep their category; choose an active category to make a new assignment.</li>
              </ul>
            </section>
          </div>
        </div>
        <footer className="flex justify-end border-t border-white/[0.08] px-5 py-3 sm:px-7">
          <button onClick={onClose} className="rounded-lg bg-blue-500 px-4 py-2.5 text-xs font-semibold text-white hover:bg-blue-400">Done</button>
        </footer>
      </section>
    </div>
  )
}
