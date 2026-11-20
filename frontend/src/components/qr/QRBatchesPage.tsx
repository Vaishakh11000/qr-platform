import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import { AlertCircle, Boxes, ChevronLeft, ChevronRight, Download, LoaderCircle, Plus, RefreshCw, Share2, X } from 'lucide-react'
import {
  allocateQRBatch,
  createQRBatch,
  exportQRBatchForSharing,
  getAllProducts,
  getAllRegions,
  getQRBatch,
  getQRBatches,
  regionDisplayLabel,
  retireQRBatch,
} from '../../lib/api'
import type { Product, QRBatch, Region } from '../../lib/api'

const PAGE_SIZE = 50

function QRBatchesPage({ searchTargetId, searchTargetNonce }: { searchTargetId?: string; searchTargetNonce: number }) {
  const [batches, setBatches] = useState<QRBatch[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [regions, setRegions] = useState<Region[]>([])
  const [offset, setOffset] = useState(0)
  const [reloadNonce, setReloadNonce] = useState(0)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [sharingBatchId, setSharingBatchId] = useState<string | null>(null)
  const [shareBatch, setShareBatch] = useState<QRBatch | null>(null)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [formError, setFormError] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [quantity, setQuantity] = useState('100')
  const [batchCode, setBatchCode] = useState('')
  const [productId, setProductId] = useState('')
  const [regionId, setRegionId] = useState('')
  const [allocationBatch, setAllocationBatch] = useState<QRBatch | null>(null)
  const [allocationProductId, setAllocationProductId] = useState('')
  const [allocationRegionId, setAllocationRegionId] = useState('')
  const [allocationReason, setAllocationReason] = useState('')
  const requestSequence = useRef(0)

  const loadBatches = useCallback(async () => {
    const requestId = ++requestSequence.current
    setLoading(true)
    setError('')
    try {
      const page = await getQRBatches({ offset, limit: PAGE_SIZE })
      if (searchTargetId) {
        const target = await getQRBatch(searchTargetId)
        if (requestId === requestSequence.current) setBatches([target, ...page.filter((batch) => batch.id !== target.id)].slice(0, PAGE_SIZE))
      } else {
        if (requestId === requestSequence.current) setBatches(page)
      }
    } catch (err) {
      if (requestId === requestSequence.current) setError(err instanceof Error ? err.message : 'Could not load QR batches.')
    } finally {
      if (requestId === requestSequence.current) setLoading(false)
    }
  }, [offset, searchTargetId])

  useEffect(() => { void loadBatches() }, [loadBatches, searchTargetNonce, reloadNonce])

  useEffect(() => {
    Promise.all([
      getAllProducts(),
      getAllRegions({ is_active: true }),
    ]).then(([productList, regionList]) => {
      setProducts(productList.filter((product) => product.status !== 'ARCHIVED'))
      setRegions(regionList)
    }).catch((err: unknown) => {
      setFormError(err instanceof Error ? err.message : 'Could not load product and region options.')
    })
  }, [])

  const productNames = useMemo(
    () => new Map(products.map((product) => [product.id, `${product.name} (${product.sku})`] as const)),
    [products],
  )
  const regionNames = useMemo(
    () => new Map(regions.map((region) => [region.id, regionDisplayLabel(region, regions)] as const)),
    [regions],
  )

  function openCreate() {
    setQuantity('100')
    setBatchCode('')
    setProductId('')
    setRegionId('')
    setFormError('')
    setSuccess('')
    setShowCreate(true)
  }

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSaving(true)
    setFormError('')
    setError('')
    setSuccess('')
    try {
      const created = await createQRBatch({
        quantity: Number(quantity),
        ...(batchCode.trim() ? { batch_code: batchCode.trim() } : {}),
        requested_product_id: productId || null,
        requested_region_id: regionId || null,
      })
      setShowCreate(false)
      setOffset(0)
      setSuccess(productId && regionId
        ? `Batch ${created.batch_code} generated and allocated with ${created.quantity.toLocaleString()} QR codes.`
        : `Batch ${created.batch_code} generated with ${created.quantity.toLocaleString()} QR codes. Assign its codes before scanning.`)
      if (offset === 0) setReloadNonce((value) => value + 1)
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Could not generate QR batch.')
    } finally {
      setSaving(false)
    }
  }

  async function handleRetire(batch: QRBatch) {
    if (!window.confirm(`Retire batch ${batch.batch_code}? Its active QR codes will be revoked and can no longer be scanned.`)) return
    setError('')
    setSuccess('')
    try {
      const result = await retireQRBatch(batch.id)
      setBatches((current) => current.map((item) => item.id === batch.id ? {
        ...item,
        retired_at: result.retired_at,
        active_code_count: 0,
        allocated_code_count: 0,
        allocation_status: 'NO_ACTIVE_CODES',
      } : item))
      setSuccess(result.revoked_count
        ? `Retired ${result.batch_code}; ${result.revoked_count.toLocaleString()} active QR codes were revoked.`
        : `Batch ${result.batch_code} has no active QR codes to revoke.`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not retire QR batch.')
    }
  }

  async function handleBatchAllocation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!allocationBatch) return
    setSaving(true)
    setFormError('')
    try {
      const result = await allocateQRBatch(allocationBatch.id, {
        product_id: allocationProductId,
        region_id: allocationRegionId,
        reason: allocationReason.trim() || null,
      })
      setAllocationBatch(null)
      await loadBatches()
      setSuccess(`Updated ${result.batch_code}: ${result.allocated_count} allocated, ${result.reassigned_count} reassigned, ${result.unchanged_count} unchanged.`)
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Could not allocate this batch.')
    } finally {
      setSaving(false)
    }
  }

  async function handleShareBatch(batch: QRBatch, format: 'svg-zip' | 'pdf' | 'png-zip') {
    setSharingBatchId(batch.id)
    setError('')
    setSuccess('')
    try {
      const archive = await exportQRBatchForSharing(batch.id, format)
      const extension = format === 'pdf' ? 'pdf' : 'zip'
      const filename = `${batch.batch_code}-${format === 'pdf' ? 'qr-codes' : format === 'png-zip' ? 'pngs' : 'svgs'}.${extension}`
      const mimeType = format === 'pdf' ? 'application/pdf' : 'application/zip'
      const file = new File([archive], filename, { type: mimeType })
      const shareApi = navigator as unknown as {
        share?: (data: ShareData) => Promise<void>
        canShare?: (data?: ShareData) => boolean
      }
      if (typeof shareApi.share === 'function'
        && typeof shareApi.canShare === 'function'
        && shareApi.canShare({ files: [file] })) {
        await shareApi.share({
          files: [file],
          title: `QR batch ${batch.batch_code}`,
          text: `Active QR codes for batch ${batch.batch_code}`,
        })
        setSuccess(`Shared ${filename}.`)
        setShareBatch(null)
      } else {
        const objectUrl = URL.createObjectURL(archive)
        const link = document.createElement('a')
        link.href = objectUrl
        link.download = filename
        document.body.appendChild(link)
        link.click()
        link.remove()
        window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000)
        setSuccess(`Downloaded ${filename}.`)
        setShareBatch(null)
      }
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') return
      setError(err instanceof Error ? err.message : 'Could not prepare this batch for sharing.')
    } finally {
      setSharingBatchId(null)
    }
  }

  return (
    <div>
      <div className="mb-7 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="text-sm text-slate-400">QR inventory</p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight text-white">QR Batches</h2>
          <p className="mt-1 text-sm text-slate-500">Generate and review QR code batches.</p>
        </div>
        <button onClick={openCreate} className="flex w-fit items-center gap-2 rounded-lg bg-blue-500 px-4 py-2.5 text-xs font-semibold text-white transition hover:bg-blue-400">
          <Plus size={15} /> Generate batch
        </button>
      </div>

      {success && <p className="mb-4 rounded-lg border border-emerald-500/20 bg-emerald-500/10 p-3 text-xs text-emerald-300">{success}</p>}
      {error && <p className="mb-4 flex items-center gap-2 rounded-lg border border-rose-500/20 bg-rose-500/10 p-3 text-xs text-rose-300"><AlertCircle size={14} />{error}</p>}

      <div className="mb-5 flex flex-col gap-3 rounded-xl border border-white/[0.07] bg-[#101827] p-4 sm:flex-row sm:items-center">
        <div className="flex items-center gap-2 text-xs text-slate-400"><Boxes size={15} /> Batch directory</div>
        <span className="text-[10px] text-slate-500 sm:ml-auto">Newest batches first</span>
        <button onClick={() => void loadBatches()} aria-label="Refresh QR batches" className="rounded-lg border border-white/10 p-2.5 text-slate-400 hover:text-white"><RefreshCw size={14} /></button>
      </div>

      <div className="overflow-hidden rounded-xl border border-white/[0.07] bg-[#101827]">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[800px] text-left text-xs">
            <thead className="border-b border-white/[0.07] text-[10px] uppercase tracking-wider text-slate-500">
              <tr><th className="px-5 py-4 font-medium">Batch</th><th className="px-5 py-4 font-medium">Product</th><th className="px-5 py-4 font-medium">Region</th><th className="px-5 py-4 font-medium">Codes</th><th className="px-5 py-4 font-medium">Status</th><th className="px-5 py-4 font-medium">Created</th><th className="px-5 py-4 text-right font-medium">Actions</th></tr>
            </thead>
            <tbody className="divide-y divide-white/[0.05] text-slate-300">
              {loading ? <tr><td colSpan={7} className="px-5 py-12 text-center text-slate-500"><LoaderCircle size={18} className="mx-auto animate-spin" /></td></tr>
                : batches.length === 0 ? <tr><td colSpan={7} className="px-5 py-12 text-center text-slate-500">No QR batches yet. Generate a batch to add codes.</td></tr>
                  : batches.map((batch) => <tr key={batch.id} className={searchTargetId === batch.id ? 'bg-blue-500/[0.08]' : 'hover:bg-white/[0.02]'}>
                    <td className="px-5 py-4 font-mono font-medium text-white">{batch.batch_code}</td>
                    <td className="px-5 py-4">{batch.allocation_status === 'MIXED' ? `Mixed assignments (${batch.allocated_code_count}/${batch.active_code_count})` : batch.current_product_id ? productNames.get(batch.current_product_id) ?? 'Product unavailable' : '—'}</td>
                    <td className="px-5 py-4">{batch.allocation_status === 'MIXED' ? 'Mixed assignments' : batch.current_region_id ? regionNames.get(batch.current_region_id) ?? 'Region unavailable' : '—'}</td>
                    <td className="px-5 py-4 tabular-nums">{batch.quantity.toLocaleString()}</td>
                    <td className="px-5 py-4"><span className={`rounded-full border px-2 py-1 text-[10px] ${batch.retired_at ? 'border-rose-500/20 bg-rose-500/10 text-rose-300' : batch.active_code_count === 0 ? 'border-slate-500/20 bg-slate-500/10 text-slate-400' : batch.generation_status === 'GENERATED' ? 'border-emerald-500/20 bg-emerald-500/10 text-emerald-300' : 'border-amber-500/20 bg-amber-500/10 text-amber-300'}`}>{batch.retired_at ? 'RETIRED' : batch.active_code_count === 0 ? 'NO ACTIVE CODES' : batch.generation_status}</span></td>
                    <td className="px-5 py-4 text-slate-400">{new Date(batch.created_at).toLocaleString()}</td>
                    <td className="px-5 py-4 text-right"><div className="flex justify-end gap-2">{!batch.retired_at && <>{batch.active_code_count > 0 && <><button onClick={() => setShareBatch(batch)} disabled={sharingBatchId !== null} className="flex items-center gap-1 rounded-md border border-white/10 px-2.5 py-2 text-[10px] text-slate-300 hover:text-white disabled:opacity-50"><Share2 size={12} /><Download size={12} />Share / export</button><button onClick={() => { setAllocationBatch(batch); setAllocationProductId(batch.current_product_id ?? ''); setAllocationRegionId(batch.current_region_id ?? ''); setAllocationReason(''); setFormError('') }} className="rounded-md border border-white/10 px-2.5 py-2 text-[10px] text-slate-300 hover:text-white">Allocate / reassign</button></>}<button onClick={() => void handleRetire(batch)} className="rounded-md border border-white/10 px-2.5 py-2 text-[10px] text-slate-400 hover:border-rose-500/30 hover:text-rose-300">Retire</button></>}</div></td>
                  </tr>)}
            </tbody>
          </table>
        </div>
        <div className="flex items-center justify-between border-t border-white/[0.06] px-5 py-3 text-[10px] text-slate-500">
          <span>{batches.length ? `Showing ${offset + 1}–${offset + batches.length}` : 'No batches on this page'}</span>
          <div className="flex gap-2">
            <button disabled={offset === 0 || loading} onClick={() => setOffset((current) => Math.max(0, current - PAGE_SIZE))} className="rounded-md border border-white/10 p-1.5 disabled:opacity-30"><ChevronLeft size={14} /></button>
            <button disabled={batches.length < PAGE_SIZE || loading} onClick={() => setOffset((current) => current + PAGE_SIZE)} className="rounded-md border border-white/10 p-1.5 disabled:opacity-30"><ChevronRight size={14} /></button>
          </div>
        </div>
      </div>

      {showCreate && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" onMouseDown={(event) => { if (event.target === event.currentTarget) setShowCreate(false) }}>
        <section className="w-full max-w-lg rounded-2xl border border-white/10 bg-[#101827] p-6 shadow-2xl">
          <div className="mb-5 flex items-center justify-between"><div><h3 className="text-lg font-semibold text-white">Generate QR batch</h3><p className="mt-1 text-xs text-slate-500">Each code gets a unique public scan token.</p></div><button onClick={() => setShowCreate(false)} aria-label="Close dialog" className="text-slate-500 hover:text-white"><X size={18} /></button></div>
          <form onSubmit={(event) => void handleCreate(event)} className="space-y-4">
            <label className="block text-xs text-slate-400">Quantity<input required type="number" min={1} max={5000} value={quantity} onChange={(event) => setQuantity(event.target.value)} className="mt-2 w-full rounded-lg border border-white/10 bg-[#0b1220] px-3 py-2.5 text-sm text-white outline-none focus:border-blue-500/50" /><span className="mt-1 block text-[10px] text-slate-600">Choose between 1 and 5,000 QR codes.</span></label>
            <label className="block text-xs text-slate-400">Batch code <span className="text-slate-600">(optional)</span><input maxLength={100} value={batchCode} onChange={(event) => setBatchCode(event.target.value)} placeholder="Generated automatically if blank" className="mt-2 w-full rounded-lg border border-white/10 bg-[#0b1220] px-3 py-2.5 text-sm text-white outline-none placeholder:text-slate-600 focus:border-blue-500/50" /></label>
            <label className="block text-xs text-slate-400">Requested product <span className="text-slate-600">(optional)</span><select value={productId} onChange={(event) => setProductId(event.target.value)} className="mt-2 w-full rounded-lg border border-white/10 bg-[#0b1220] px-3 py-2.5 text-sm text-white outline-none focus:border-blue-500/50"><option value="">No product</option>{products.map((product) => <option key={product.id} value={product.id}>{product.name} ({product.sku}) · {product.status}</option>)}</select></label>
            <label className="block text-xs text-slate-400">Requested region <span className="text-slate-600">(optional)</span><select value={regionId} onChange={(event) => setRegionId(event.target.value)} className="mt-2 w-full rounded-lg border border-white/10 bg-[#0b1220] px-3 py-2.5 text-sm text-white outline-none focus:border-blue-500/50"><option value="">No region</option>{regions.map((region) => <option key={region.id} value={region.id}>{regionDisplayLabel(region, regions)}</option>)}</select></label>
            <p className="rounded-lg border border-blue-500/20 bg-blue-500/10 p-3 text-[11px] leading-5 text-blue-200">Select both a product and region to allocate every generated code immediately. Leave both blank to allocate codes later from the QR Codes page.</p>
            {formError && <p className="flex items-center gap-2 rounded-lg border border-rose-500/20 bg-rose-500/10 p-3 text-xs text-rose-300"><AlertCircle size={14} />{formError}</p>}
            <div className="flex justify-end gap-2 pt-2"><button type="button" onClick={() => setShowCreate(false)} className="rounded-lg border border-white/10 px-4 py-2.5 text-xs text-slate-300">Cancel</button><button disabled={saving || !quantity} className="flex items-center gap-2 rounded-lg bg-blue-500 px-4 py-2.5 text-xs font-semibold text-white disabled:opacity-60">{saving && <LoaderCircle size={13} className="animate-spin" />}{saving ? 'Generating…' : 'Generate batch'}</button></div>
          </form>
        </section>
      </div>}

      {shareBatch && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" onMouseDown={(event) => { if (event.target === event.currentTarget && !sharingBatchId) setShareBatch(null) }}>
        <section className="w-full max-w-md rounded-2xl border border-white/10 bg-[#101827] p-6 shadow-2xl">
          <div className="mb-5 flex items-center justify-between"><div><h3 className="text-lg font-semibold text-white">Share QR batch</h3><p className="mt-1 text-xs text-slate-500">{shareBatch.batch_code} · active codes</p></div><button onClick={() => setShareBatch(null)} disabled={sharingBatchId !== null} aria-label="Close dialog" className="text-slate-500 hover:text-white"><X size={18} /></button></div>
          <div className="space-y-3">
            <button onClick={() => void handleShareBatch(shareBatch, 'pdf')} disabled={sharingBatchId !== null} className="flex w-full items-center justify-between rounded-lg border border-white/10 p-4 text-left hover:border-blue-400/40 disabled:opacity-50"><span><span className="block text-sm font-medium text-white">Printable PDF</span><span className="mt-1 block text-xs text-slate-500">All active QR codes, laid out for printing.</span></span>{sharingBatchId === shareBatch.id ? <LoaderCircle size={16} className="animate-spin text-blue-300" /> : <Download size={16} className="text-slate-400" />}</button>
            <button onClick={() => void handleShareBatch(shareBatch, 'png-zip')} disabled={sharingBatchId !== null} className="flex w-full items-center justify-between rounded-lg border border-white/10 p-4 text-left hover:border-blue-400/40 disabled:opacity-50"><span><span className="block text-sm font-medium text-white">PNG folder (ZIP)</span><span className="mt-1 block text-xs text-slate-500">A folder containing individual PNG image files.</span></span>{sharingBatchId === shareBatch.id ? <LoaderCircle size={16} className="animate-spin text-blue-300" /> : <Download size={16} className="text-slate-400" />}</button>
            <button onClick={() => void handleShareBatch(shareBatch, 'svg-zip')} disabled={sharingBatchId !== null} className="flex w-full items-center justify-between rounded-lg border border-white/10 p-4 text-left hover:border-blue-400/40 disabled:opacity-50"><span><span className="block text-sm font-medium text-white">SVG package (ZIP)</span><span className="mt-1 block text-xs text-slate-500">Scalable QR images inside a folder, with a scan link list.</span></span>{sharingBatchId === shareBatch.id ? <LoaderCircle size={16} className="animate-spin text-blue-300" /> : <Download size={16} className="text-slate-400" />}</button>
          </div>
          <p className="mt-4 text-[11px] leading-5 text-slate-500">On supported phones, the share sheet opens. Otherwise the file downloads to this device.</p>
        </section>
      </div>}

      {allocationBatch && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" onMouseDown={(event) => { if (event.target === event.currentTarget) setAllocationBatch(null) }}>
        <section className="w-full max-w-lg rounded-2xl border border-white/10 bg-[#101827] p-6 shadow-2xl">
          <div className="mb-5 flex items-center justify-between"><div><h3 className="text-lg font-semibold text-white">Allocate / reassign batch</h3><p className="mt-1 text-xs text-slate-500">{allocationBatch.batch_code} · all active codes</p></div><button onClick={() => setAllocationBatch(null)} aria-label="Close dialog" className="text-slate-500 hover:text-white"><X size={18} /></button></div>
          <form onSubmit={(event) => void handleBatchAllocation(event)} className="space-y-4">
            <label className="block text-xs text-slate-400">Product<select required value={allocationProductId} onChange={(event) => setAllocationProductId(event.target.value)} className="mt-2 w-full rounded-lg border border-white/10 bg-[#0b1220] px-3 py-2.5 text-sm text-white outline-none"><option value="">Choose product</option>{products.filter((product) => product.status !== 'ARCHIVED').map((product) => <option key={product.id} value={product.id}>{product.name} ({product.sku}) · {product.status}</option>)}</select></label>
            <label className="block text-xs text-slate-400">Region<select required value={allocationRegionId} onChange={(event) => setAllocationRegionId(event.target.value)} className="mt-2 w-full rounded-lg border border-white/10 bg-[#0b1220] px-3 py-2.5 text-sm text-white outline-none"><option value="">Choose region</option>{regions.map((region) => <option key={region.id} value={region.id}>{regionDisplayLabel(region, regions)}</option>)}</select></label>
            <label className="block text-xs text-slate-400">Reason <span className="text-slate-600">(optional)</span><textarea maxLength={2000} rows={2} value={allocationReason} onChange={(event) => setAllocationReason(event.target.value)} className="mt-2 w-full rounded-lg border border-white/10 bg-[#0b1220] px-3 py-2.5 text-sm text-white outline-none" /></label>
            {formError && <p className="flex items-center gap-2 rounded-lg border border-rose-500/20 bg-rose-500/10 p-3 text-xs text-rose-300"><AlertCircle size={14} />{formError}</p>}
            <div className="flex justify-end gap-2"><button type="button" onClick={() => setAllocationBatch(null)} className="rounded-lg border border-white/10 px-4 py-2.5 text-xs text-slate-300">Cancel</button><button disabled={saving} className="flex items-center gap-2 rounded-lg bg-blue-500 px-4 py-2.5 text-xs font-semibold text-white disabled:opacity-60">{saving && <LoaderCircle size={13} className="animate-spin" />}Apply to batch</button></div>
          </form>
        </section>
      </div>}
    </div>
  )
}

export default QRBatchesPage
