import { useCallback, useEffect, useMemo, useRef, useState, type ChangeEvent, type FormEvent } from 'react'
import { AlertCircle, LoaderCircle, Map as MapIcon, MapPin, Pencil, Plus, RefreshCw, X } from 'lucide-react'
import { createRegion, deactivateRegion, deleteRegionBoundary, getAllRegions, getRegion, getRegionBoundary, getRegions, regionDisplayLabel, saveRegionBoundary, updateRegion } from '../../lib/api'
import type { Region, RegionBoundaryGeometry } from '../../lib/api'

const PAGE_SIZE = 100

function regionDescendants(rootId: string, regions: Region[]) {
  const excluded = new Set([rootId])
  let changed = true
  while (changed) {
    changed = false
    for (const region of regions) {
      if (region.parent_id && excluded.has(region.parent_id) && !excluded.has(region.id)) {
        excluded.add(region.id)
        changed = true
      }
    }
  }
  return excluded
}

function normalizeGeoJsonBoundary(value: unknown): RegionBoundaryGeometry {
  if (!value || typeof value !== 'object') {
    throw new Error('Choose a GeoJSON Polygon, MultiPolygon, Feature, or FeatureCollection.')
  }
  const object = value as Record<string, unknown>
  if (object.type === 'Feature') return normalizeGeoJsonBoundary(object.geometry)

  if (object.type === 'FeatureCollection') {
    if (!Array.isArray(object.features) || object.features.length === 0) {
      throw new Error('The GeoJSON FeatureCollection has no features.')
    }
    const polygons: unknown[][] = []
    for (const feature of object.features) {
      const geometry = normalizeGeoJsonBoundary(
        feature && typeof feature === 'object' ? (feature as Record<string, unknown>).geometry : feature,
      )
      if (geometry.type === 'Polygon') polygons.push(geometry.coordinates)
      else polygons.push(...geometry.coordinates as unknown[][])
    }
    return { type: 'MultiPolygon', coordinates: polygons }
  }

  if ((object.type === 'Polygon' || object.type === 'MultiPolygon') && Array.isArray(object.coordinates)) {
    return { type: object.type, coordinates: object.coordinates }
  }
  throw new Error('The GeoJSON must contain Polygon or MultiPolygon geometry.')
}

function RegionsPage({ searchTargetId, searchTargetNonce }: { searchTargetId?: string; searchTargetNonce: number }) {
  const [regions, setRegions] = useState<Region[]>([])
  const [parentOptions, setParentOptions] = useState<Region[]>([])
  const [regionOffset, setRegionOffset] = useState(0)
  const [filter, setFilter] = useState<'active' | 'inactive' | 'all'>(searchTargetId ? 'all' : 'active')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [formError, setFormError] = useState('')
  const [editing, setEditing] = useState<Region | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [name, setName] = useState('')
  const [code, setCode] = useState('')
  const [regionType, setRegionType] = useState('')
  const [parentId, setParentId] = useState('')
  const [boundaryRegion, setBoundaryRegion] = useState<Region | null>(null)
  const [boundaryJson, setBoundaryJson] = useState('')
  const [boundaryExists, setBoundaryExists] = useState(false)
  const [boundaryLoading, setBoundaryLoading] = useState(false)
  const [boundarySaving, setBoundarySaving] = useState(false)
  const [boundaryError, setBoundaryError] = useState('')
  const lastSearchTargetNonce = useRef(0)

  const queryRegions = useCallback(() => {
    const is_active = filter === 'all' ? undefined : filter === 'active'
    return getRegions({ offset: regionOffset, limit: PAGE_SIZE, is_active }).then(async (rows) => {
      if (!searchTargetId || rows.some((region) => region.id === searchTargetId)) return rows
      try {
        const target = await getRegion(searchTargetId)
        return [target, ...rows].slice(0, PAGE_SIZE)
      } catch {
        return rows
      }
    })
  }, [filter, regionOffset, searchTargetId])

  const loadRegions = useCallback(async (showLoading = false) => {
    if (showLoading) setLoading(true)
    try {
      setRegions(await queryRegions())
      setError('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load regions.')
    } finally {
      setLoading(false)
    }
  }, [queryRegions])

  useEffect(() => {
    let active = true
    queryRegions()
      .then((rows) => { if (active) { setRegions(rows); setError('') } })
      .catch((err: unknown) => { if (active) setError(err instanceof Error ? err.message : 'Could not load regions.') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [queryRegions])

  useEffect(() => {
    let active = true
    getAllRegions({ is_active: true }).then((all) => {
      if (active) setParentOptions(all)
    }).catch((err: unknown) => {
      if (active) setError(err instanceof Error ? err.message : 'Could not load parent region options.')
    })
    return () => { active = false }
  }, [])

  useEffect(() => {
    if (!searchTargetId || lastSearchTargetNonce.current === searchTargetNonce) return
    lastSearchTargetNonce.current = searchTargetNonce
    if (filter !== 'all' || regionOffset !== 0) {
      setLoading(true)
      setFilter('all')
      setRegionOffset(0)
    }
  }, [filter, regionOffset, searchTargetId, searchTargetNonce])

  useEffect(() => {
    if (!searchTargetId || loading) return
    const region = regions.find((item) => item.id === searchTargetId)
    if (!region) {
      setError('The searched region is not in the current region list.')
      return
    }
    document.getElementById(`region-${searchTargetId}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, [loading, regions, searchTargetId, searchTargetNonce])

  const parentNames = useMemo(
    () => new Map([...parentOptions, ...regions].map((region) => [region.id, regionDisplayLabel(region, [...parentOptions, ...regions])])),
    [parentOptions, regions],
  )
  const excludedParentIds = editing ? regionDescendants(editing.id, parentOptions) : new Set<string>()

  function openCreate() {
    setEditing(null)
    setName('')
    setCode('')
    setRegionType('')
    setParentId('')
    setFormError('')
    setShowForm(true)
  }

  function openEdit(region: Region) {
    setEditing(region)
    setName(region.name)
    setCode(region.region_code)
    setRegionType(region.region_type)
    setParentId(region.parent_id ?? '')
    setFormError('')
    setShowForm(true)
  }

  async function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSaving(true)
    setFormError('')
    const data = {
      name: name.trim(),
      region_code: code.trim(),
      region_type: regionType.trim(),
      parent_id: parentId || null,
    }
    try {
      if (editing) await updateRegion(editing.id, data)
      else await createRegion(data)
      setShowForm(false)
      await loadRegions(true)
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Could not save region.')
    } finally {
      setSaving(false)
    }
  }

  async function handleDeactivate(region: Region) {
    if (!window.confirm(`Deactivate “${region.name}”?`)) return
    setError('')
    try {
      await deactivateRegion(region.id)
      await loadRegions(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not deactivate region.')
    }
  }

  async function handleReactivate(region: Region) {
    setError('')
    try {
      await updateRegion(region.id, { is_active: true })
      await loadRegions(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not reactivate region.')
    }
  }

  async function openBoundaryEditor(region: Region) {
    setBoundaryRegion(region)
    setBoundaryJson('')
    setBoundaryExists(false)
    setBoundaryError('')
    setBoundaryLoading(true)
    try {
      const result = await getRegionBoundary(region.id)
      setBoundaryExists(result.geometry !== null)
      setBoundaryJson(result.geometry ? JSON.stringify(result.geometry, null, 2) : '')
    } catch (err) {
      setBoundaryError(err instanceof Error ? err.message : 'Could not load region boundary.')
    } finally {
      setBoundaryLoading(false)
    }
  }

  async function handleSaveBoundary(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!boundaryRegion) return
    setBoundarySaving(true)
    setBoundaryError('')
    try {
      const geometry = JSON.parse(boundaryJson) as RegionBoundaryGeometry
      const result = await saveRegionBoundary(boundaryRegion.id, geometry)
      setBoundaryExists(true)
      setBoundaryJson(JSON.stringify(result.geometry, null, 2))
    } catch (err) {
      setBoundaryError(err instanceof Error ? err.message : 'Enter a valid Polygon or MultiPolygon GeoJSON object.')
    } finally {
      setBoundarySaving(false)
    }
  }

  async function importBoundaryFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.currentTarget.files?.[0]
    event.currentTarget.value = ''
    if (!file) return
    setBoundaryError('')
    try {
      const normalized = normalizeGeoJsonBoundary(JSON.parse(await file.text()))
      setBoundaryJson(JSON.stringify(normalized, null, 2))
    } catch (err) {
      setBoundaryError(err instanceof Error ? err.message : 'Could not read the GeoJSON file.')
    }
  }

  function downloadBoundary() {
    if (!boundaryRegion || !boundaryJson.trim()) return
    try {
      const parsed = JSON.parse(boundaryJson)
      const blobUrl = URL.createObjectURL(new Blob([`${JSON.stringify(parsed, null, 2)}\n`], { type: 'application/geo+json;charset=utf-8' }))
      const link = document.createElement('a')
      const safeCode = boundaryRegion.region_code.toLowerCase().replace(/[^a-z0-9_-]+/g, '-')
      link.href = blobUrl
      link.download = `${safeCode}-boundary.geojson`
      link.click()
      window.setTimeout(() => URL.revokeObjectURL(blobUrl), 1000)
    } catch {
      setBoundaryError('Enter valid JSON before downloading the boundary.')
    }
  }

  async function handleDeleteBoundary() {
    if (!boundaryRegion || !window.confirm(`Remove the scan boundary for “${boundaryRegion.name}”?`)) return
    setBoundarySaving(true)
    setBoundaryError('')
    try {
      await deleteRegionBoundary(boundaryRegion.id)
      setBoundaryExists(false)
      setBoundaryJson('')
    } catch (err) {
      setBoundaryError(err instanceof Error ? err.message : 'Could not remove region boundary.')
    } finally {
      setBoundarySaving(false)
    }
  }

  return (
    <div>
      <div className="mb-7 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="text-sm text-slate-400">Geography and scan coverage</p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight text-white">Regions</h2>
          <p className="mt-1 text-sm text-slate-500">Manage regions and their parent-child relationships.</p>
        </div>
        <button onClick={openCreate} className="flex w-fit items-center gap-2 rounded-lg bg-blue-500 px-4 py-2.5 text-xs font-semibold text-white transition hover:bg-blue-400">
          <Plus size={15} /> New region
        </button>
      </div>

      <div className="mb-5 flex flex-col gap-3 rounded-xl border border-white/[0.07] bg-[#101827] p-4 sm:flex-row sm:items-center">
        <div className="flex items-center gap-2 text-xs text-slate-400"><MapPin size={15} /> Region directory</div>
        <select value={filter} onChange={(event) => { setLoading(true); setRegionOffset(0); setFilter(event.target.value as typeof filter) }} className="rounded-lg border border-white/10 bg-[#0b1220] px-3 py-2.5 text-xs text-slate-300 outline-none sm:ml-auto">
          <option value="active">Active regions</option>
          <option value="inactive">Inactive regions</option>
          <option value="all">All regions</option>
        </select>
        <button onClick={() => void loadRegions(true)} aria-label="Refresh regions" className="rounded-lg border border-white/10 p-2.5 text-slate-400 hover:text-white"><RefreshCw size={14} /></button>
      </div>

      {error && <p className="mb-4 flex items-center gap-2 rounded-lg border border-rose-500/20 bg-rose-500/10 p-3 text-xs text-rose-300"><AlertCircle size={14} />{error}</p>}

      <div className="overflow-hidden rounded-xl border border-white/[0.07] bg-[#101827]">
        <div className="overflow-x-auto">
            <table className="w-full min-w-[820px] text-left text-xs">
            <thead className="border-b border-white/[0.07] text-[10px] uppercase tracking-wider text-slate-500">
              <tr><th className="px-5 py-4 font-medium">Region</th><th className="px-5 py-4 font-medium">Code</th><th className="px-5 py-4 font-medium">Type</th><th className="px-5 py-4 font-medium">Parent</th><th className="px-5 py-4 font-medium">Status</th><th className="px-5 py-4 font-medium">Boundary</th><th className="px-5 py-4 text-right font-medium">Actions</th></tr>
            </thead>
            <tbody className="divide-y divide-white/[0.05] text-slate-300">
              {loading ? <tr><td colSpan={7} className="px-5 py-12 text-center text-slate-500"><LoaderCircle size={18} className="mx-auto animate-spin" /></td></tr>
                : regions.length === 0 ? <tr><td colSpan={7} className="px-5 py-12 text-center text-slate-500">No regions match this filter.</td></tr>
                  : regions.map((region) => <tr id={`region-${region.id}`} key={region.id} className={searchTargetId === region.id ? 'bg-blue-500/[0.08]' : 'hover:bg-white/[0.02]'}>
                    <td className="px-5 py-4 font-medium text-white">{region.name}</td>
                    <td className="px-5 py-4 font-mono text-slate-400">{region.region_code}</td>
                    <td className="px-5 py-4">{region.region_type}</td>
                    <td className="px-5 py-4 text-slate-400">{region.parent_id ? parentNames.get(region.parent_id) ?? 'Parent not in this view' : '—'}</td>
                    <td className="px-5 py-4"><span className={`rounded-full border px-2 py-1 text-[10px] ${region.is_active ? 'border-emerald-500/20 bg-emerald-500/10 text-emerald-300' : 'border-slate-500/20 bg-slate-500/10 text-slate-400'}`}>{region.is_active ? 'Active' : 'Inactive'}</span></td>
                    <td className="px-5 py-4"><button onClick={() => void openBoundaryEditor(region)} className="flex items-center gap-1.5 rounded-md border border-white/10 px-2.5 py-2 text-[10px] text-slate-300 hover:text-white"><MapIcon size={12} />Manage</button></td>
                    <td className="px-5 py-4"><div className="flex justify-end gap-2">
                      <button onClick={() => openEdit(region)} aria-label={`Edit ${region.name}`} className="rounded-md border border-white/10 p-2 text-slate-400 hover:text-white"><Pencil size={13} /></button>
                      {region.is_active
                        ? <button onClick={() => void handleDeactivate(region)} className="rounded-md border border-white/10 px-2.5 py-2 text-[10px] text-slate-400 hover:border-rose-500/30 hover:text-rose-300">Deactivate</button>
                        : <button onClick={() => void handleReactivate(region)} className="rounded-md border border-white/10 px-2.5 py-2 text-[10px] text-slate-400 hover:border-emerald-500/30 hover:text-emerald-300">Reactivate</button>}
                    </div></td>
                  </tr>)}
            </tbody>
          </table>
        </div>
        <div className="flex items-center justify-between border-t border-white/[0.06] px-5 py-3 text-[10px] text-slate-500"><span>Page {Math.floor(regionOffset / PAGE_SIZE) + 1} · {regions.length ? `Showing ${regionOffset + 1}–${regionOffset + regions.length}` : 'No regions on this page'}</span><div className="flex gap-2"><button disabled={regionOffset === 0 || loading} onClick={() => { setLoading(true); setRegionOffset((value) => Math.max(0, value - PAGE_SIZE)) }} className="rounded-md border border-white/10 px-2.5 py-1.5 disabled:opacity-30">Previous</button><button disabled={regions.length < PAGE_SIZE || loading} onClick={() => { setLoading(true); setRegionOffset((value) => value + PAGE_SIZE) }} className="rounded-md border border-white/10 px-2.5 py-1.5 disabled:opacity-30">Next</button></div></div>
      </div>

      {showForm && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" onMouseDown={(event) => { if (event.target === event.currentTarget) setShowForm(false) }}>
        <section className="w-full max-w-lg rounded-2xl border border-white/10 bg-[#101827] p-6 shadow-2xl">
          <div className="mb-5 flex items-center justify-between"><div><h3 className="text-lg font-semibold text-white">{editing ? 'Edit region' : 'Create region'}</h3><p className="mt-1 text-xs text-slate-500">Region codes must be unique.</p></div><button onClick={() => setShowForm(false)} aria-label="Close dialog" className="text-slate-500 hover:text-white"><X size={18} /></button></div>
          <form onSubmit={(event) => void handleSave(event)} className="space-y-4">
            {[['Name', name, setName], ['Region code', code, setCode], ['Region type', regionType, setRegionType]].map(([label, value, setter]) => <label key={label as string} className="block text-xs text-slate-400">{label as string}<input required maxLength={label === 'Name' ? 150 : 50} value={value as string} onChange={(event) => (setter as (value: string) => void)(event.target.value)} className="mt-2 w-full rounded-lg border border-white/10 bg-[#0b1220] px-3 py-2.5 text-sm text-white outline-none focus:border-blue-500/50" /></label>)}
            <label className="block text-xs text-slate-400">Parent region<select value={parentId} onChange={(event) => setParentId(event.target.value)} className="mt-2 w-full rounded-lg border border-white/10 bg-[#0b1220] px-3 py-2.5 text-sm text-white outline-none focus:border-blue-500/50"><option value="">No parent</option>{parentOptions.filter((region) => !excludedParentIds.has(region.id)).map((region) => <option key={region.id} value={region.id}>{regionDisplayLabel(region, parentOptions)}</option>)}</select></label>
            {formError && <p className="flex items-center gap-2 rounded-lg border border-rose-500/20 bg-rose-500/10 p-3 text-xs text-rose-300"><AlertCircle size={14} />{formError}</p>}
            <div className="flex justify-end gap-2 pt-2"><button type="button" onClick={() => setShowForm(false)} className="rounded-lg border border-white/10 px-4 py-2.5 text-xs text-slate-300">Cancel</button><button disabled={saving} className="flex items-center gap-2 rounded-lg bg-blue-500 px-4 py-2.5 text-xs font-semibold text-white disabled:opacity-60">{saving && <LoaderCircle size={13} className="animate-spin" />}{editing ? 'Save changes' : 'Create region'}</button></div>
          </form>
        </section>
      </div>}

      {boundaryRegion && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" onMouseDown={(event) => { if (event.target === event.currentTarget) setBoundaryRegion(null) }}>
        <section className="w-full max-w-2xl rounded-2xl border border-white/10 bg-[#101827] p-6 shadow-2xl">
          <div className="mb-4 flex items-start justify-between gap-4"><div><h3 className="text-lg font-semibold text-white">Scan boundary · {boundaryRegion.name}</h3><p className="mt-1 text-xs text-slate-400">Paste a GeoJSON Polygon or MultiPolygon. Coordinates must be longitude, latitude pairs in WGS84.</p></div><button onClick={() => setBoundaryRegion(null)} aria-label="Close boundary editor" className="text-slate-500 hover:text-white"><X size={18} /></button></div>
          {boundaryLoading ? <div className="flex items-center gap-2 py-10 text-sm text-slate-400"><LoaderCircle size={16} className="animate-spin" />Loading boundary…</div> : <form onSubmit={(event) => void handleSaveBoundary(event)}>
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-white/[0.06] bg-[#0b1220] p-3"><label className="text-xs text-slate-400">Import GeoJSON<input type="file" accept=".geojson,.json,application/geo+json,application/json" onChange={(event) => void importBoundaryFile(event)} className="mt-1.5 block max-w-full text-[10px] text-slate-400 file:mr-3 file:rounded-md file:border-0 file:bg-white/10 file:px-3 file:py-2 file:text-[10px] file:text-slate-200" /></label><button type="button" disabled={!boundaryJson.trim()} onClick={downloadBoundary} className="rounded-md border border-white/10 px-3 py-2 text-[10px] text-slate-300 disabled:opacity-40">Download GeoJSON</button></div>
            <label className="block text-xs text-slate-400">GeoJSON geometry<textarea required rows={14} value={boundaryJson} onChange={(event) => setBoundaryJson(event.target.value)} placeholder={'{\n  "type": "Polygon",\n  "coordinates": [[[72.8, 18.9], [73.0, 18.9], [73.0, 19.1], [72.8, 19.1], [72.8, 18.9]]] \n}'} className="mt-2 w-full rounded-lg border border-white/10 bg-[#0b1220] px-3 py-3 font-mono text-xs leading-relaxed text-slate-200 outline-none focus:border-blue-500/50" /></label>
            <p className="mt-2 text-[10px] text-slate-500">The polygon ring must be closed. Valid boundaries are used to resolve GPS scan regions; overlapping sibling regions remain ambiguous.</p>
            {boundaryExists && <p className="mt-2 text-[10px] text-emerald-300">A boundary is currently saved for this region.</p>}
            {boundaryError && <p role="alert" className="mt-3 flex items-center gap-2 rounded-lg border border-rose-500/20 bg-rose-500/10 p-3 text-xs text-rose-300"><AlertCircle size={14} />{boundaryError}</p>}
            <div className="mt-5 flex flex-wrap justify-between gap-2"><div>{boundaryExists && <button type="button" disabled={boundarySaving} onClick={() => void handleDeleteBoundary()} className="rounded-lg border border-rose-500/30 px-4 py-2.5 text-xs text-rose-300 hover:bg-rose-500/10 disabled:opacity-50">Remove boundary</button>}</div><div className="flex gap-2"><button type="button" onClick={() => setBoundaryRegion(null)} className="rounded-lg border border-white/10 px-4 py-2.5 text-xs text-slate-300">Close</button><button disabled={boundarySaving || boundaryLoading} className="rounded-lg bg-blue-500 px-4 py-2.5 text-xs font-semibold text-white disabled:opacity-50">{boundarySaving ? 'Saving…' : 'Save boundary'}</button></div></div>
          </form>}
        </section>
      </div>}
    </div>
  )
}

export default RegionsPage
