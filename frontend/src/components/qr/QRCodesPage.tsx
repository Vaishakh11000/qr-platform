import { useCallback, useEffect, useRef, useState } from 'react'
import { AlertCircle, ChevronLeft, ChevronRight, Download, Eye, History, LoaderCircle, QrCode, RefreshCw, X } from 'lucide-react'
import {
  getQRAllocationHistory,
  getQRBatchCodes,
  getAllQRBatches,
  getProduct,
  getRegion,
  getQRCode,
  getQRCodeImage,
} from '../../lib/api'
import type { QRAllocation, QRBatch, QRCode } from '../../lib/api'

const PAGE_SIZE = 100

function QRCodesPage({ searchTargetId, searchTargetNonce }: { searchTargetId?: string; searchTargetNonce: number }) {
  const [batches, setBatches] = useState<QRBatch[]>([])
  const [batchId, setBatchId] = useState('')
  const [codes, setCodes] = useState<QRCode[]>([])
  const [offset, setOffset] = useState(0)
  const [loadingBatches, setLoadingBatches] = useState(true)
  const [loadingCodes, setLoadingCodes] = useState(false)
  const [error, setError] = useState('')
  const [selectedCode, setSelectedCode] = useState<QRCode | null>(null)
  const [imageUrl, setImageUrl] = useState('')
  const [imageLoading, setImageLoading] = useState(false)
  const [imageError, setImageError] = useState('')
  const [allocationHistory, setAllocationHistory] = useState<QRAllocation[]>([])
  const [allocationLabels, setAllocationLabels] = useState<Record<string, string>>({})
  const [allocationHistoryLoading, setAllocationHistoryLoading] = useState(false)
  const [allocationHistoryError, setAllocationHistoryError] = useState('')
  const batchRequestSequence = useRef(0)

  const loadBatches = useCallback(async () => {
    const requestId = ++batchRequestSequence.current
    setLoadingBatches(true)
    setError('')
    try {
      const list = await getAllQRBatches()
      if (requestId !== batchRequestSequence.current) return
      setBatches(list)
      setBatchId((current) => current || list[0]?.id || '')
    } catch (err) {
      if (requestId === batchRequestSequence.current) setError(err instanceof Error ? err.message : 'Could not load QR batches.')
    } finally {
      if (requestId === batchRequestSequence.current) setLoadingBatches(false)
    }
  }, [])

  useEffect(() => { void loadBatches() }, [loadBatches])

  useEffect(() => {
    if (!searchTargetId) return
    let active = true
    getQRCode(searchTargetId)
      .then((code) => {
        if (!active) return
        setBatchId(code.batch_id)
        setOffset(0)
        setSelectedCode(code)
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : 'Could not open the searched QR code.')
      })
    return () => { active = false }
  }, [searchTargetId, searchTargetNonce])

  useEffect(() => {
    if (!batchId) {
      setCodes([])
      return
    }
    let cancelled = false
    setLoadingCodes(true)
    setError('')
    getQRBatchCodes({ batchId, offset, limit: PAGE_SIZE })
      .then((list) => { if (!cancelled) setCodes(list) })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Could not load QR codes.')
      })
      .finally(() => { if (!cancelled) setLoadingCodes(false) })
    return () => { cancelled = true }
  }, [batchId, offset])

  useEffect(() => {
    if (!selectedCode) {
      setImageUrl('')
      return
    }
    let cancelled = false
    let objectUrl = ''
    setImageLoading(true)
    setImageError('')
    getQRCodeImage(selectedCode.id)
      .then((blob) => {
        objectUrl = URL.createObjectURL(blob)
        if (!cancelled) setImageUrl(objectUrl)
        else URL.revokeObjectURL(objectUrl)
      })
      .catch((err: unknown) => {
        if (!cancelled) setImageError(err instanceof Error ? err.message : 'Could not load QR image.')
      })
      .finally(() => { if (!cancelled) setImageLoading(false) })
    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [selectedCode])

  useEffect(() => {
    if (!selectedCode) {
      setAllocationHistory([])
      setAllocationLabels({})
      return
    }
    let cancelled = false
    setAllocationHistoryLoading(true)
    setAllocationHistoryError('')
    setAllocationHistory([])
    setAllocationLabels({})
    getQRAllocationHistory(selectedCode.id).then((history) => {
      if (cancelled) return
      setAllocationHistory(history)
    }).catch((err: unknown) => {
      if (!cancelled) setAllocationHistoryError(err instanceof Error ? err.message : 'Could not load allocation history.')
    }).finally(() => { if (!cancelled) setAllocationHistoryLoading(false) })
    return () => { cancelled = true }
  }, [selectedCode])

  useEffect(() => {
    if (!allocationHistory.length) return
    let cancelled = false
    const productIds = [...new Set(allocationHistory.map((item) => item.product_id))]
    const regionIds = [...new Set(allocationHistory.map((item) => item.region_id))]
    Promise.all([
      ...productIds.map(async (id) => {
        try {
          const product = await getProduct(id)
          return [`product:${id}`, `${product.name} (${product.sku})`] as const
        } catch { return [`product:${id}`, id] as const }
      }),
      ...regionIds.map(async (id) => {
        try {
          const region = await getRegion(id)
          return [`region:${id}`, `${region.name} · ${region.region_code}`] as const
        } catch { return [`region:${id}`, id] as const }
      }),
    ]).then((entries) => {
      if (!cancelled) setAllocationLabels(Object.fromEntries(entries))
    })
    return () => { cancelled = true }
  }, [allocationHistory])

  const selectedBatch = batches.find((batch) => batch.id === batchId)

  return (
    <div>
      <div className="mb-7 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="text-sm text-slate-400">QR inventory</p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight text-white">QR Codes</h2>
          <p className="mt-1 text-sm text-slate-500">Browse codes and preview their images. Allocate or reassign codes from QR Batches.</p>
        </div>
      </div>

      {error && <p className="mb-4 flex items-center gap-2 rounded-lg border border-rose-500/20 bg-rose-500/10 p-3 text-xs text-rose-300"><AlertCircle size={14} />{error}</p>}

      <div className="mb-5 flex flex-col gap-3 rounded-xl border border-white/[0.07] bg-[#101827] p-4 sm:flex-row sm:items-center">
        <label className="flex min-w-0 flex-1 items-center gap-3 text-xs text-slate-400"><QrCode size={15} /><span className="shrink-0">Batch</span><select disabled={loadingBatches || batches.length === 0} value={batchId} onChange={(event) => { setOffset(0); setBatchId(event.target.value) }} className="min-w-0 flex-1 rounded-lg border border-white/10 bg-[#0b1220] px-3 py-2.5 text-xs text-white outline-none"><option value="">Select a batch</option>{batches.map((batch) => <option key={batch.id} value={batch.id}>{batch.batch_code} · {batch.quantity.toLocaleString()} codes</option>)}</select></label>
        <span className="text-[10px] text-slate-500">{selectedBatch ? `${selectedBatch.generation_status} · ${selectedBatch.quantity.toLocaleString()} codes` : 'Select a batch to browse codes'}</span>
        <button onClick={() => void loadBatches()} aria-label="Refresh batches" className="rounded-lg border border-white/10 p-2.5 text-slate-400 hover:text-white"><RefreshCw size={14} /></button>
      </div>

      <div className="overflow-hidden rounded-xl border border-white/[0.07] bg-[#101827]">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px] text-left text-xs">
            <thead className="border-b border-white/[0.07] text-[10px] uppercase tracking-wider text-slate-500">
              <tr><th className="px-5 py-4 font-medium">Token</th><th className="px-5 py-4 font-medium">Status</th><th className="px-5 py-4 font-medium">Scan URL</th><th className="px-5 py-4 font-medium">Created</th><th className="px-5 py-4 text-right font-medium">Actions</th></tr>
            </thead>
            <tbody className="divide-y divide-white/[0.05] text-slate-300">
              {loadingCodes || loadingBatches ? <tr><td colSpan={5} className="px-5 py-12 text-center text-slate-500"><LoaderCircle size={18} className="mx-auto animate-spin" /></td></tr>
                : !batchId ? <tr><td colSpan={5} className="px-5 py-12 text-center text-slate-500">No batches available. Generate a QR batch first.</td></tr>
                  : codes.length === 0 ? <tr><td colSpan={5} className="px-5 py-12 text-center text-slate-500">No QR codes on this page.</td></tr>
                    : codes.map((code) => <tr key={code.id} className="hover:bg-white/[0.02]">
                      <td className="max-w-[260px] px-5 py-4 font-mono text-[10px] text-slate-300"><span className="block truncate" title={code.token}>{code.token}</span></td>
                      <td className="px-5 py-4"><span className="rounded-full border border-white/10 bg-white/[0.03] px-2 py-1 text-[10px] text-slate-300">{code.status}</span></td>
                      <td className="max-w-[260px] px-5 py-4"><a href={code.scan_url} target="_blank" rel="noreferrer" className="block truncate text-blue-300 hover:text-blue-200" title={code.scan_url}>{code.scan_url}</a></td>
                      <td className="px-5 py-4 text-slate-400">{new Date(code.created_at).toLocaleString()}</td>
                      <td className="px-5 py-4"><div className="flex justify-end"><button onClick={() => setSelectedCode(code)} className="flex items-center gap-2 rounded-md border border-white/10 px-3 py-2 text-[10px] text-slate-300 hover:text-white"><Eye size={13} /> Preview / download</button></div></td>
                    </tr>)}
            </tbody>
          </table>
        </div>
        <div className="flex items-center justify-between border-t border-white/[0.06] px-5 py-3 text-[10px] text-slate-500">
          <span>{codes.length ? `Showing ${offset + 1}–${offset + codes.length}${selectedBatch ? ` of ${selectedBatch.quantity.toLocaleString()}` : ''}` : 'No codes on this page'}</span>
          <div className="flex gap-2"><button disabled={offset === 0 || loadingCodes} onClick={() => setOffset((current) => Math.max(0, current - PAGE_SIZE))} className="rounded-md border border-white/10 p-1.5 disabled:opacity-30"><ChevronLeft size={14} /></button><button disabled={codes.length < PAGE_SIZE || loadingCodes} onClick={() => setOffset((current) => current + PAGE_SIZE)} className="rounded-md border border-white/10 p-1.5 disabled:opacity-30"><ChevronRight size={14} /></button></div>
        </div>
      </div>

      {selectedCode && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" onMouseDown={(event) => { if (event.target === event.currentTarget) setSelectedCode(null) }}>
        <section className="max-h-[90vh] w-full max-w-xl overflow-y-auto rounded-2xl border border-white/10 bg-[#101827] p-6 shadow-2xl">
          <div className="mb-5 flex items-center justify-between"><div><h3 className="text-lg font-semibold text-white">QR code image</h3><p className="mt-1 max-w-[290px] truncate font-mono text-[10px] text-slate-500">{selectedCode.token}</p></div><button onClick={() => setSelectedCode(null)} aria-label="Close preview" className="text-slate-500 hover:text-white"><X size={18} /></button></div>
          <div className="flex min-h-[280px] items-center justify-center rounded-xl border border-white/[0.07] bg-white p-5">
            {imageLoading ? <LoaderCircle size={22} className="animate-spin text-slate-500" />
              : imageError ? <p className="text-xs text-rose-700">{imageError}</p>
                : imageUrl ? <img src={imageUrl} alt={`QR code ${selectedCode.token}`} className="h-64 w-64 object-contain" /> : null}
          </div>
          <div className="mt-5 flex justify-end gap-2"><button onClick={() => setSelectedCode(null)} className="rounded-lg border border-white/10 px-4 py-2.5 text-xs text-slate-300">Close</button><a aria-disabled={!imageUrl} href={imageUrl || undefined} download={`qr-${selectedCode.id}.png`} className={`flex items-center gap-2 rounded-lg bg-blue-500 px-4 py-2.5 text-xs font-semibold text-white ${!imageUrl ? 'pointer-events-none opacity-50' : 'hover:bg-blue-400'}`}><Download size={14} /> Download PNG</a></div>
          <div className="mt-6 border-t border-white/[0.07] pt-5">
            <h4 className="mb-3 flex items-center gap-2 text-xs font-semibold text-slate-300"><History size={14} /> Allocation history</h4>
            {allocationHistoryLoading ? <LoaderCircle size={16} className="animate-spin text-slate-500" />
              : allocationHistoryError ? <p className="text-xs text-rose-300">{allocationHistoryError}</p>
                : allocationHistory.length === 0 ? <p className="text-xs text-slate-500">No allocation history.</p>
              : <div className="max-h-48 space-y-2 overflow-y-auto">{allocationHistory.map((allocation) => <div key={allocation.id} className="rounded-lg border border-white/[0.06] bg-[#0b1220] p-3 text-[10px] text-slate-400"><div className="flex flex-wrap justify-between gap-2"><span>{allocationLabels[`product:${allocation.product_id}`] ?? allocation.product_id} · {allocationLabels[`region:${allocation.region_id}`] ?? allocation.region_id}</span><span>{allocation.ended_at ? 'Ended' : 'Active'}</span></div><p className="mt-1">{new Date(allocation.assigned_at).toLocaleString()}{allocation.ended_at ? ` → ${new Date(allocation.ended_at).toLocaleString()}` : ''}</p>{allocation.reason && <p className="mt-1 text-slate-500">{allocation.reason}</p>}</div>)}</div>}
            <p className="mt-3 text-[10px] text-slate-500">To assign or reassign codes, use QR Batches.</p>
          </div>
        </section>
      </div>}
    </div>
  )
}

export default QRCodesPage
