import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { AlertCircle, LoaderCircle, Plus, RefreshCw, ShieldCheck, Trash2, X } from 'lucide-react'
import {
  createLocationPolicy,
  createLocationPolicyAssignment,
  deactivateLocationPolicy,
  deleteLocationPolicyAssignment,
  getLocationPolicy,
  getLocationPolicies,
  getLocationPolicyAssignments,
  getAllProducts,
  getAllRegions,
  regionDisplayLabel,
  permanentlyDeleteLocationPolicy,
  updateLocationPolicy,
} from '../../lib/api'
import type { LocationPolicy, LocationPolicyAssignment, Product, Region } from '../../lib/api'

function LocationPoliciesPage({ searchTargetId, searchTargetNonce }: { searchTargetId?: string; searchTargetNonce: number }) {
  const [policies, setPolicies] = useState<LocationPolicy[]>([])
  const [assignments, setAssignments] = useState<LocationPolicyAssignment[]>([])
  const [assignmentsForPolicyId, setAssignmentsForPolicyId] = useState<string | null>(null)
  const [products, setProducts] = useState<Product[]>([])
  const [regions, setRegions] = useState<Region[]>([])
  const [selected, setSelected] = useState<LocationPolicy | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [formError, setFormError] = useState('')
  const [editing, setEditing] = useState<LocationPolicy | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [name, setName] = useState('')
  const [requirement, setRequirement] = useState<'MANDATORY' | 'SKIPPABLE'>('MANDATORY')
  const [method, setMethod] = useState<LocationPolicy['method']>('GPS_REQUIRED')
  const [scope, setScope] = useState<LocationPolicyAssignment['scope_type']>('PRODUCT')
  const [targetId, setTargetId] = useState('')
  const [priority, setPriority] = useState('0')

  const loadPolicies = useCallback(async (showLoading = true) => {
    if (showLoading) {
      setLoading(true)
      setError('')
    }
    try {
      const list = await getLocationPolicies()
      setPolicies(list)
      setSelected((current) => current
        ? list.find((policy) => policy.id === current.id) ?? list[0] ?? null
        : list[0] ?? null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load location policies.')
    } finally { setLoading(false) }
  }, [])

  useEffect(() => {
    let active = true
    getLocationPolicies()
      .then((list) => {
        if (!active) return
        setPolicies(list)
        setSelected(list[0] ?? null)
        setError('')
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : 'Could not load location policies.')
      })
      .finally(() => { if (active) setLoading(false) })
    Promise.all([getAllProducts(), getAllRegions({ is_active: true })])
      .then(([productList, regionList]) => {
        if (!active) return
        setProducts(productList.filter((product) => product.status !== 'ARCHIVED'))
        setRegions(regionList)
      }).catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : 'Could not load assignment options.')
      })
    return () => { active = false }
  }, [])

  useEffect(() => {
    if (!searchTargetId || loading) return
    const listedPolicy = policies.find((item) => item.id === searchTargetId)
    if (listedPolicy) {
      setSelected(listedPolicy)
      return
    }
    let active = true
    getLocationPolicy(searchTargetId)
      .then((policy) => {
        if (!active) return
        setPolicies((current) => [policy, ...current.filter((item) => item.id !== policy.id)])
        setSelected(policy)
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : 'Could not open the searched location policy.')
      })
    return () => { active = false }
  }, [loading, policies, searchTargetId, searchTargetNonce])

  useEffect(() => {
    const policyId = selected?.id
    if (!policyId) return
    let active = true
    getLocationPolicyAssignments(policyId)
      .then((rows) => {
        if (!active) return
        setAssignments(rows)
        setAssignmentsForPolicyId(policyId)
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : 'Could not load assignments.')
      })
    return () => { active = false }
  }, [selected?.id])

  function openCreate() {
    setEditing(null); setName(''); setRequirement('MANDATORY'); setMethod('GPS_REQUIRED')
    setFormError(''); setShowForm(true)
  }

  function openEdit(policy: LocationPolicy) {
    setEditing(policy); setName(policy.name); setRequirement(policy.requirement); setMethod(policy.method)
    setFormError(''); setShowForm(true)
  }

  async function savePolicy(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setSaving(true); setFormError('')
    try {
      const data = { name: name.trim(), requirement, method }
      const saved = editing ? await updateLocationPolicy(editing.id, data) : await createLocationPolicy(data)
      setShowForm(false); await loadPolicies(); setSelected(saved)
    } catch (err) { setFormError(err instanceof Error ? err.message : 'Could not save policy.') }
    finally { setSaving(false) }
  }

  async function addAssignment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!selected) return
    setSaving(true); setError('')
    try {
      await createLocationPolicyAssignment({
        policy_id: selected.id,
        scope_type: scope,
        ...(scope === 'PRODUCT' ? { product_id: targetId } : {}),
        ...(scope === 'REGION' ? { region_id: targetId } : {}),
        priority: Number(priority),
      })
      setTargetId(''); setPriority('0')
      setAssignments(await getLocationPolicyAssignments(selected.id))
      setAssignmentsForPolicyId(selected.id)
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not add assignment.') }
    finally { setSaving(false) }
  }

  async function removeAssignment(assignment: LocationPolicyAssignment) {
    if (!window.confirm('Remove this policy assignment?')) return
    try {
      await deleteLocationPolicyAssignment(assignment.id)
      if (selected) setAssignments(await getLocationPolicyAssignments(selected.id))
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not remove assignment.') }
  }

  async function deactivate(policy: LocationPolicy) {
    if (!window.confirm(`Deactivate location policy “${policy.name}”?`)) return
    try { await deactivateLocationPolicy(policy.id); await loadPolicies() }
    catch (err) { setError(err instanceof Error ? err.message : 'Could not deactivate policy.') }
  }

  async function reactivate(policy: LocationPolicy) {
    if (!window.confirm(`Reactivate “${policy.name}”? Its existing assignments will apply to scans again.`)) return
    try {
      await updateLocationPolicy(policy.id, { is_active: true })
      await loadPolicies()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not reactivate policy.')
    }
  }

  async function permanentlyDelete(policy: LocationPolicy) {
    if (!window.confirm(`Permanently delete “${policy.name}”? Its assignments will be removed. Existing scan history will remain, without a link to this policy. This cannot be undone.`)) return
    try {
      await permanentlyDeleteLocationPolicy(policy.id)
      await loadPolicies()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not delete policy.')
    }
  }

  const targetName = (assignment: LocationPolicyAssignment) => {
    if (assignment.scope_type === 'GLOBAL') return 'All scans'
    if (assignment.scope_type === 'PRODUCT') return products.find((product) => product.id === assignment.product_id)?.name ?? 'Product'
    const region = regions.find((item) => item.id === assignment.region_id)
    return region ? regionDisplayLabel(region, regions) : 'Region'
  }

  const regionOptionName = (region: Region) => {
    return regionDisplayLabel(region, regions)
  }

  const visibleAssignments = selected?.id === assignmentsForPolicyId ? assignments : []

  return <div>
    <div className="mb-7 flex flex-col justify-between gap-4 sm:flex-row sm:items-end"><div><p className="text-sm text-slate-400">Scan controls</p><h2 className="mt-2 text-2xl font-semibold tracking-tight text-white">Location Policies</h2><p className="mt-1 text-sm text-slate-500">Set location requirements and apply them globally or to products and regions.</p></div><button onClick={openCreate} className="flex w-fit items-center gap-2 rounded-lg bg-blue-500 px-4 py-2.5 text-xs font-semibold text-white"><Plus size={15} /> New policy</button></div>
    {error && <p className="mb-4 flex items-center gap-2 rounded-lg border border-rose-500/20 bg-rose-500/10 p-3 text-xs text-rose-300"><AlertCircle size={14} />{error}</p>}
    <div className="grid gap-5 xl:grid-cols-[0.9fr_1.1fr]">
      <section className="overflow-hidden rounded-xl border border-white/[0.07] bg-[#101827]"><div className="flex items-center justify-between border-b border-white/[0.07] px-5 py-4"><h3 className="flex items-center gap-2 text-xs font-semibold text-slate-200"><ShieldCheck size={15} /> Policies</h3><button onClick={() => void loadPolicies()} aria-label="Refresh policies" className="text-slate-500 hover:text-white"><RefreshCw size={14} /></button></div>
        {loading ? <div className="p-10 text-center text-slate-500"><LoaderCircle size={18} className="mx-auto animate-spin" /></div> : policies.length === 0 ? <p className="p-10 text-center text-xs text-slate-500">No location policies yet.</p> : <div className="divide-y divide-white/[0.05]">{policies.map((policy) => <div key={policy.id} className={`p-4 transition ${selected?.id === policy.id ? 'bg-blue-500/[0.08]' : 'hover:bg-white/[0.02]'}`}>
          <button type="button" onClick={() => setSelected(policy)} aria-pressed={selected?.id === policy.id} className="w-full text-left">
            <span className="flex items-start justify-between gap-3"><span className="text-sm font-medium text-white">{policy.name}</span><span className={`rounded-full border px-2 py-1 text-[9px] ${policy.is_active ? 'border-emerald-500/20 bg-emerald-500/10 text-emerald-300' : 'border-slate-500/20 bg-slate-500/10 text-slate-400'}`}>{policy.is_active ? 'Active' : 'Inactive'}</span></span>
            <span className="mt-2 block text-[10px] text-slate-500">{policy.requirement} · {policy.method.replaceAll('_', ' ')}</span>
          </button>
          <div className="mt-3 flex gap-2">
            <button type="button" onClick={() => openEdit(policy)} className="rounded-md border border-white/10 px-2.5 py-1.5 text-[10px] text-slate-400 hover:text-white">Edit</button>
            {policy.is_active ? <button type="button" onClick={() => void deactivate(policy)} className="rounded-md border border-white/10 px-2.5 py-1.5 text-[10px] text-slate-400 hover:text-rose-300">Deactivate</button> : <><button type="button" onClick={() => void reactivate(policy)} className="rounded-md border border-emerald-500/20 bg-emerald-500/10 px-2.5 py-1.5 text-[10px] text-emerald-300 hover:bg-emerald-500/20">Reactivate</button><button type="button" onClick={() => void permanentlyDelete(policy)} className="rounded-md border border-rose-500/20 bg-rose-500/10 px-2.5 py-1.5 text-[10px] text-rose-300 hover:bg-rose-500/20">Delete</button></>}
          </div>
        </div>)}</div>}
      </section>
      <section className="overflow-hidden rounded-xl border border-white/[0.07] bg-[#101827]"><div className="border-b border-white/[0.07] px-5 py-4"><h3 className="text-sm font-semibold text-slate-200">{selected ? `Assignments · ${selected.name}` : 'Assignments'}</h3><p className="mt-1 text-xs leading-5 text-slate-500">{selected ? 'A region assignment applies to that region and its descendants. The nearest matching region wins. Region policies take precedence over product and global policies; priority does not override this order.' : 'Select a policy to manage its scope assignments.'}</p></div>
        {selected ? <div className="p-5"><form onSubmit={(event) => void addAssignment(event)} className="mb-5 grid gap-3 sm:grid-cols-[1fr_1.5fr_auto]"><label className="text-xs text-slate-400">Scope<select value={scope} onChange={(event) => { setScope(event.target.value as typeof scope); setTargetId('') }} className="mt-1.5 w-full rounded-lg border border-white/10 bg-[#0b1220] px-3 py-2.5 text-sm text-white"><option value="PRODUCT">Product</option><option value="REGION">Region and descendants</option><option value="GLOBAL">Global (all scans)</option></select></label><label className="text-xs text-slate-400">Target{scope === 'GLOBAL' ? <span className="mt-1.5 block py-2.5 text-sm text-slate-500">All scans</span> : <select required value={targetId} onChange={(event) => setTargetId(event.target.value)} className="mt-1.5 w-full rounded-lg border border-white/10 bg-[#0b1220] px-3 py-2.5 text-sm text-white"><option value="">Choose {scope.toLowerCase()}</option>{scope === 'PRODUCT' ? products.map((product) => <option key={product.id} value={product.id}>{product.name} ({product.sku})</option>) : regions.map((region) => <option key={region.id} value={region.id}>{regionOptionName(region)}</option>)}</select>}</label><button disabled={saving || !selected.is_active} className="self-end rounded-lg bg-blue-500 px-3 py-2.5 text-xs font-semibold text-white disabled:opacity-50"><Plus size={13} className="inline" /> Assign</button><label className="text-xs text-slate-400 sm:col-span-3">Priority<input type="number" min={0} value={priority} onChange={(event) => setPriority(event.target.value)} className="mt-1.5 w-24 rounded-lg border border-white/10 bg-[#0b1220] px-3 py-2.5 text-sm text-white" /></label></form>
          {selected.id !== assignmentsForPolicyId ? <p className="py-8 text-center text-sm text-slate-500">Loading assignments…</p> : visibleAssignments.length === 0 ? <p className="py-8 text-center text-sm text-slate-500">No assignments for this policy.</p> : <div className="space-y-2">{visibleAssignments.map((assignment) => <div key={assignment.id} className="flex items-center justify-between gap-3 rounded-lg border border-white/[0.06] bg-[#0b1220] px-3 py-3"><div><p className="text-sm text-white">{targetName(assignment)}</p><p className="mt-1 text-xs text-slate-500">{assignment.scope_type} scope · priority {assignment.priority}</p></div><button onClick={() => void removeAssignment(assignment)} aria-label="Remove assignment" className="rounded-md p-2 text-slate-500 hover:text-rose-300"><Trash2 size={14} /></button></div>)}</div>}
        </div> : <p className="p-10 text-center text-xs text-slate-500">Choose a policy to view or add assignments.</p>}
      </section>
    </div>
    {showForm && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" onMouseDown={(event) => { if (event.target === event.currentTarget) setShowForm(false) }}><section className="w-full max-w-lg rounded-2xl border border-white/10 bg-[#101827] p-6"><div className="mb-5 flex items-center justify-between"><h3 className="text-lg font-semibold text-white">{editing ? 'Edit policy' : 'Create location policy'}</h3><button onClick={() => setShowForm(false)} aria-label="Close dialog" className="text-slate-500"><X size={18} /></button></div><form onSubmit={(event) => void savePolicy(event)} className="space-y-4"><label className="block text-xs text-slate-400">Name<input required maxLength={150} value={name} onChange={(event) => setName(event.target.value)} className="mt-2 w-full rounded-lg border border-white/10 bg-[#0b1220] px-3 py-2.5 text-sm text-white" /></label><label className="block text-xs text-slate-400">Requirement<select value={requirement} onChange={(event) => setRequirement(event.target.value as typeof requirement)} className="mt-2 w-full rounded-lg border border-white/10 bg-[#0b1220] px-3 py-2.5 text-sm text-white"><option value="MANDATORY">Mandatory</option><option value="SKIPPABLE">Skippable</option></select></label><label className="block text-xs text-slate-400">Method<select value={method} onChange={(event) => setMethod(event.target.value as typeof method)} className="mt-2 w-full rounded-lg border border-white/10 bg-[#0b1220] px-3 py-2.5 text-sm text-white"><option value="GPS_REQUIRED">GPS required</option><option value="GPS_IP_FALLBACK">GPS with IP fallback (provider not configured)</option><option value="IP_ONLY">IP only (provider not configured)</option></select></label>{method !== 'GPS_REQUIRED' && <p className="rounded-lg border border-amber-500/20 bg-amber-500/10 p-3 text-xs leading-5 text-amber-200">IP geolocation is not configured, so these methods cannot verify location when GPS is unavailable. On local Wi-Fi, use the site over HTTPS and allow GPS. For a temporary development test, a Skippable policy allows access without verifying the region.</p>}{formError && <p className="text-xs text-rose-300">{formError}</p>}<div className="flex justify-end gap-2"><button type="button" onClick={() => setShowForm(false)} className="rounded-lg border border-white/10 px-4 py-2.5 text-xs text-slate-300">Cancel</button><button disabled={saving} className="rounded-lg bg-blue-500 px-4 py-2.5 text-xs font-semibold text-white">{saving ? 'Saving…' : 'Save policy'}</button></div></form></section></div>}
  </div>
}

export default LocationPoliciesPage
