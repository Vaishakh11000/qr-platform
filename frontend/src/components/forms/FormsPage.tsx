import { useEffect, useState, type FormEvent } from 'react'
import { AlertCircle, ArrowDown, ArrowUp, Check, Download, LoaderCircle, Plus, RefreshCw } from 'lucide-react'
import {
  createForm,
  createFormAssignment,
  createFormVersion,
  getFormAssignments,
  getFormSubmissions,
  getFormVersions,
  getForms,
  getAllProducts,
  getAllRegions,
  regionDisplayLabel,
  publishFormVersion,
  updateFormAssignment,
  updateFormVersion,
} from '../../lib/api'
import type {
  FormAssignmentRecord,
  FormFieldDefinition,
  FormFieldType,
  FormRecord,
  FormSubmissionRecord,
  FormVersionRecord,
  Product,
  Region,
} from '../../lib/api'

const inputClass = 'mt-1.5 w-full rounded-lg border border-white/10 bg-[#0b1220] px-3 py-2.5 text-xs text-white outline-none focus:border-blue-500/50'
const SUBMISSIONS_PAGE_SIZE = 25

function downloadSubmissionsCsv(formName: string, rows: FormSubmissionRecord[]) {
  const answerKeys = [...new Set(rows.flatMap((row) => Object.keys(row.answers)))].sort()
  const headers = ['submitted_at', 'scan_event_id', ...answerKeys]
  const escapeCell = (value: unknown) => {
    let cell = value == null ? '' : typeof value === 'string' ? value : JSON.stringify(value)
    // Prevent spreadsheet software from interpreting answer text as a formula.
    if (/^\s*[=+@\-]/.test(cell) || /^[\t\r]/.test(cell)) cell = `'${cell}`
    return `"${cell.replaceAll('"', '""')}"`
  }
  const csv = [headers, ...rows.map((row) => [row.submitted_at, row.scan_event_id, ...answerKeys.map((key) => row.answers[key])])]
    .map((record) => record.map(escapeCell).join(','))
    .join('\r\n')
  const blob = new Blob([`\uFEFF${csv}`], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `${formName.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-') || 'form'}-submissions.csv`
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}

function FormsPage({ searchTargetId, searchTargetNonce }: { searchTargetId?: string; searchTargetNonce: number }) {
  const [forms, setForms] = useState<FormRecord[]>([])
  const [assignments, setAssignments] = useState<FormAssignmentRecord[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [regions, setRegions] = useState<Region[]>([])
  const [selectedFormId, setSelectedFormId] = useState('')
  const [versions, setVersions] = useState<FormVersionRecord[]>([])
  const [submissions, setSubmissions] = useState<FormSubmissionRecord[]>([])
  const [submissionsTotal, setSubmissionsTotal] = useState(0)
  const [submissionOffset, setSubmissionOffset] = useState(0)
  const [submissionsLoading, setSubmissionsLoading] = useState(false)
  const [exportingSubmissions, setExportingSubmissions] = useState(false)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [fields, setFields] = useState<FormFieldDefinition[]>([
    { key: 'email', label: 'Email address', type: 'EMAIL', required: true },
  ])
  const [versionId, setVersionId] = useState('')
  const [editingVersionId, setEditingVersionId] = useState<string | null>(null)
  const [creatingVersion, setCreatingVersion] = useState(false)
  const [previewOpen, setPreviewOpen] = useState(false)
  const [scopeType, setScopeType] = useState<'GLOBAL' | 'PRODUCT' | 'REGION'>('PRODUCT')
  const [productId, setProductId] = useState('')
  const [regionId, setRegionId] = useState('')
  const [requirement, setRequirement] = useState<'OPTIONAL' | 'MANDATORY'>('OPTIONAL')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [updatingAssignmentId, setUpdatingAssignmentId] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  async function load() {
    setLoading(true)
    setError('')
    try {
      const [formRows, assignmentRows, productRows, regionRows] = await Promise.all([
        getForms(), getFormAssignments(), getAllProducts(), getAllRegions({ is_active: true }),
      ])
      setForms(formRows)
      setAssignments(assignmentRows)
      setProducts(productRows.filter((item) => item.status !== 'ARCHIVED'))
      setRegions(regionRows)
      if (!selectedFormId && formRows.length) setSelectedFormId(formRows[0].id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load forms.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void load() }, [])

  useEffect(() => {
    if (!searchTargetId || loading) return
    if (forms.some((form) => form.id === searchTargetId)) {
      setSelectedFormId(searchTargetId)
    } else {
      setError('The searched form is not in the current forms list.')
    }
  }, [forms, loading, searchTargetId, searchTargetNonce])

  useEffect(() => {
    if (!selectedFormId) {
      setVersions([])
      return
    }
    let active = true
    getFormVersions(selectedFormId)
      .then((versionRows) => {
        if (!active) return
        setVersions(versionRows)
        setVersionId((current) => current || versionRows.find((item) => item.published_at)?.id || '')
      })
      .catch((err: unknown) => { if (active) setError(err instanceof Error ? err.message : 'Could not load form versions.') })
    return () => { active = false }
  }, [selectedFormId])

  useEffect(() => {
    setSubmissionOffset(0)
  }, [selectedFormId])

  useEffect(() => {
    if (!selectedFormId) {
      setSubmissions([])
      setSubmissionsTotal(0)
      setSubmissionsLoading(false)
      return
    }
    let active = true
    setSubmissionsLoading(true)
    getFormSubmissions(selectedFormId, { offset: submissionOffset, limit: SUBMISSIONS_PAGE_SIZE })
      .then((page) => {
        if (!active) return
        setSubmissions(page.items)
        setSubmissionsTotal(page.total)
      })
      .catch((err: unknown) => { if (active) setError(err instanceof Error ? err.message : 'Could not load customer submissions.') })
      .finally(() => { if (active) setSubmissionsLoading(false) })
    return () => { active = false }
  }, [selectedFormId, submissionOffset])

  function moveField(index: number, direction: -1 | 1) {
    setFields((current) => {
      const nextIndex = index + direction
      if (nextIndex < 0 || nextIndex >= current.length) return current
      const reordered = [...current]
      const [field] = reordered.splice(index, 1)
      reordered.splice(nextIndex, 0, field)
      return reordered
    })
  }

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSaving(true)
    setError('')
    try {
      const schema = { fields: fields.map((field) => ({
          ...field,
          ...(field.type === 'SELECT' ? { options: (field.options ?? []).filter(Boolean) } : { options: [] }),
        })) }
      if (editingVersionId && selectedFormId) {
        await updateFormVersion(selectedFormId, editingVersionId, schema)
        setEditingVersionId(null)
        setNotice('Draft version updated.')
        setVersions(await getFormVersions(selectedFormId))
      } else if (creatingVersion && selectedFormId) {
        const created = await createFormVersion(selectedFormId, schema)
        setCreatingVersion(false)
        setNotice(`Created draft version ${created.version_number}. Review its fields, then publish it when ready.`)
        setVersions(await getFormVersions(selectedFormId))
      } else {
        const result = await createForm({
          name: name.trim(),
          description: description.trim() || null,
          schema,
        })
        setName('')
        setDescription('')
        setSelectedFormId(result.form.id)
        setNotice(`Created draft form ${result.form.name}. Publish its first version before assigning it.`)
        await load()
      }
      setFields([{ key: 'email', label: 'Email address', type: 'EMAIL', required: true }])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save this form change.')
    } finally {
      setSaving(false)
    }
  }

  async function handlePublish(version: FormVersionRecord) {
    if (!selectedFormId) return
    setSaving(true)
    setError('')
    try {
      await publishFormVersion(selectedFormId, version.id)
      setNotice(`Published version ${version.version_number}.`)
      setVersions(await getFormVersions(selectedFormId))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not publish this version.')
    } finally {
      setSaving(false)
    }
  }

  async function handleAssign(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSaving(true)
    setError('')
    try {
      await createFormAssignment({
        form_version_id: versionId,
        scope_type: scopeType,
        product_id: scopeType === 'PRODUCT' ? productId : null,
        region_id: scopeType === 'REGION' ? regionId : null,
        requirement,
      })
      setNotice('Form assigned. Any previous assignment for this form at the same scope was deactivated; its submission history is retained.')
      setAssignments(await getFormAssignments())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not assign this form.')
    } finally {
      setSaving(false)
    }
  }

  async function handleUpdateAssignment(assignment: FormAssignmentRecord, changes: { is_active?: boolean; requirement?: FormAssignmentRecord['requirement'] }) {
    setUpdatingAssignmentId(assignment.id)
    setError('')
    try {
      const updated = await updateFormAssignment(assignment.id, changes)
      setAssignments((current) => current.map((item) => item.id === updated.id ? updated : item))
      if (changes.is_active !== undefined) {
        setNotice(updated.is_active ? 'Assignment reactivated.' : 'Assignment deactivated. Its history is retained.')
      } else {
        setNotice(updated.requirement === 'DISABLED' ? 'Assignment hidden from customer scans.' : `Assignment requirement changed to ${updated.requirement.toLowerCase()}.`)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not update this assignment.')
    } finally {
      setUpdatingAssignmentId(null)
    }
  }

  const selectedForm = forms.find((form) => form.id === selectedFormId)
  const publishedVersions = versions.filter((version) => version.published_at)
  const formVersionIds = new Set(versions.map((version) => version.id))
  const currentAssignments = assignments.filter((assignment) => formVersionIds.has(assignment.form_version_id))

  async function handleExportSubmissions() {
    if (!selectedForm || submissionsTotal === 0) return
    setExportingSubmissions(true)
    setError('')
    try {
      const allSubmissions: FormSubmissionRecord[] = []
      let offset = 0
      let total = submissionsTotal
      while (offset < total) {
        const page = await getFormSubmissions(selectedForm.id, { offset, limit: 100 })
        if (page.items.length === 0) break
        allSubmissions.push(...page.items)
        total = page.total
        offset += page.items.length
      }
      downloadSubmissionsCsv(selectedForm.name, allSubmissions)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not export customer submissions.')
    } finally {
      setExportingSubmissions(false)
    }
  }

  return (
    <div>
      <div className="mb-7 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div><p className="text-sm text-slate-400">Customer engagement</p><h2 className="mt-2 text-2xl font-semibold text-white">Forms</h2><p className="mt-1 text-sm text-slate-500">Create product enquiry forms and assign them to scans.</p></div>
        <button onClick={() => void load()} aria-label="Refresh forms" className="flex w-fit items-center gap-2 rounded-lg border border-white/10 px-3 py-2 text-xs text-slate-300"><RefreshCw size={14} />Refresh</button>
      </div>
      {notice && <p className="mb-4 rounded-lg border border-emerald-500/20 bg-emerald-500/10 p-3 text-xs text-emerald-300">{notice}</p>}
      {error && <p className="mb-4 flex items-center gap-2 rounded-lg border border-rose-500/20 bg-rose-500/10 p-3 text-xs text-rose-300"><AlertCircle size={14} />{error}</p>}

      <div className="grid gap-5 xl:grid-cols-[1fr_1.2fr]">
        <form onSubmit={(event) => void handleCreate(event)} className="space-y-4 rounded-xl border border-white/[0.07] bg-[#101827] p-5">
          <div><h3 className="text-sm font-semibold text-white">{editingVersionId ? 'Edit draft version' : creatingVersion ? 'Create new version' : 'Create form'}</h3><p className="mt-1 text-xs text-slate-500">{editingVersionId ? 'Published versions are locked; edit this draft before publishing.' : creatingVersion ? 'This starts from the latest version’s fields. Existing published versions remain available.' : 'A new form starts as version 1 in draft.'}</p></div>
          {!editingVersionId && !creatingVersion && <>
            <label className="block text-xs text-slate-400">Form name<input required maxLength={150} value={name} onChange={(event) => setName(event.target.value)} className={inputClass} /></label>
            <label className="block text-xs text-slate-400">Description<input maxLength={2000} value={description} onChange={(event) => setDescription(event.target.value)} className={inputClass} /></label>
          </>}
          <div className="space-y-3">
            <div className="flex items-center justify-between"><span className="text-xs font-medium text-slate-300">Fields</span><div className="flex items-center gap-3"><button type="button" aria-expanded={previewOpen} aria-controls="form-customer-preview" onClick={() => setPreviewOpen((open) => !open)} className="text-[11px] text-slate-300 underline underline-offset-2">{previewOpen ? 'Hide preview' : 'Preview customer view'}</button><button type="button" onClick={() => setFields((items) => [...items, { key: `field_${items.length + 1}`, label: '', type: 'TEXT', required: false }])} className="flex items-center gap-1 text-[11px] text-blue-300"><Plus size={13} />Add field</button></div></div>
            {fields.map((field, index) => <div key={index} className="grid gap-2 rounded-lg border border-white/[0.06] p-3 sm:grid-cols-2">
              <div className="col-span-full flex items-center justify-between"><span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Field {index + 1}</span><div className="flex gap-1"><button type="button" disabled={index === 0} aria-label={`Move field ${index + 1} up`} onClick={() => moveField(index, -1)} className="rounded border border-white/10 p-1.5 text-slate-300 hover:bg-white/5 disabled:opacity-30"><ArrowUp size={13} /></button><button type="button" disabled={index === fields.length - 1} aria-label={`Move field ${index + 1} down`} onClick={() => moveField(index, 1)} className="rounded border border-white/10 p-1.5 text-slate-300 hover:bg-white/5 disabled:opacity-30"><ArrowDown size={13} /></button></div></div>
              <label className="text-[11px] text-slate-500">Field key<input required value={field.key} onChange={(event) => setFields((items) => items.map((item, i) => i === index ? { ...item, key: event.target.value } : item))} className={inputClass} /></label>
              <label className="text-[11px] text-slate-500">Label<input required value={field.label} onChange={(event) => setFields((items) => items.map((item, i) => i === index ? { ...item, label: event.target.value } : item))} className={inputClass} /></label>
              <label className="text-[11px] text-slate-500">Type<select value={field.type} onChange={(event) => setFields((items) => items.map((item, i) => i === index ? { ...item, type: event.target.value as FormFieldType, options: [] } : item))} className={inputClass}>{(['TEXT', 'EMAIL', 'PHONE', 'TEXTAREA', 'SELECT', 'CHECKBOX'] as FormFieldType[]).map((type) => <option key={type} value={type}>{type === 'PHONE' ? 'Phone number' : type}</option>)}</select></label>
              {field.type === 'SELECT' && <label className="text-[11px] text-slate-500">Options, comma separated<input required value={(field.options ?? []).join(', ')} onChange={(event) => setFields((items) => items.map((item, i) => i === index ? { ...item, options: event.target.value.split(',').map((option) => option.trim()).filter(Boolean) } : item))} className={inputClass} /></label>}
              <label className="flex items-center gap-2 text-[11px] text-slate-400"><input type="checkbox" checked={field.required} onChange={(event) => setFields((items) => items.map((item, i) => i === index ? { ...item, required: event.target.checked } : item))} />Required</label>
              {fields.length > 1 && <button type="button" onClick={() => setFields((items) => items.filter((_, i) => i !== index))} className="text-left text-[11px] text-rose-300">Remove field</button>}
            </div>)}
            {previewOpen && <section id="form-customer-preview" aria-label="Customer form preview" className="rounded-xl border border-blue-400/20 bg-[#0b1220] p-4 sm:p-5">
              <p className="text-[10px] font-bold tracking-[0.18em] text-blue-300">CUSTOMER PREVIEW</p>
              <h4 className="mt-2 text-lg font-semibold text-white">{(editingVersionId || creatingVersion ? selectedForm?.name : name.trim()) || 'Your form'}</h4>
              {(editingVersionId || creatingVersion ? selectedForm?.description : description.trim()) && <p className="mt-1 text-xs leading-5 text-slate-400">{editingVersionId || creatingVersion ? selectedForm?.description : description.trim()}</p>}
              <div className="mt-4 space-y-3">{fields.map((field, index) => <div key={`${field.key}-${index}`}>
                {field.type === 'CHECKBOX' ? <label className="flex items-start gap-2 text-xs text-slate-300"><input type="checkbox" disabled className="mt-0.5" /><span>{field.label || 'Checkbox label'}{field.required && <span className="text-rose-300"> *</span>}</span></label> : <label className="block text-xs text-slate-300">{field.label || `Field ${index + 1}`}{field.required && <span className="text-rose-300"> *</span>}{field.type === 'TEXTAREA' ? <textarea disabled rows={2} placeholder="Customer response" className={inputClass} /> : field.type === 'SELECT' ? <select disabled className={inputClass}><option>Choose an option</option>{(field.options ?? []).map((option, optionIndex) => <option key={`${option}-${optionIndex}`}>{option}</option>)}</select> : <input disabled type={field.type === 'EMAIL' ? 'email' : field.type === 'PHONE' ? 'tel' : 'text'} placeholder={field.type === 'EMAIL' ? 'name@example.com' : field.type === 'PHONE' ? 'Phone number' : 'Customer response'} className={inputClass} />}</label>}
              </div>)}</div>
              <p className="mt-3 text-[10px] text-slate-500">Preview only. Customer responses are not submitted here.</p>
            </section>}
          </div>
          <div className="flex gap-2"><button disabled={saving || !fields.length || ((editingVersionId !== null || creatingVersion) && selectedFormId === '')} className="flex items-center gap-2 rounded-lg bg-blue-500 px-4 py-2.5 text-xs font-semibold text-white disabled:opacity-50">{saving && <LoaderCircle size={13} className="animate-spin" />}{editingVersionId ? 'Save draft version' : creatingVersion ? 'Create version' : 'Create draft'}</button>{(editingVersionId || creatingVersion) && <button type="button" onClick={() => { setEditingVersionId(null); setCreatingVersion(false); setFields([{ key: 'email', label: 'Email address', type: 'EMAIL', required: true }]) }} className="rounded-lg border border-white/10 px-4 py-2.5 text-xs text-slate-300">Cancel</button>}</div>
        </form>

        <div className="space-y-5">
          <section className="rounded-xl border border-white/[0.07] bg-[#101827] p-5">
            <label className="block text-xs text-slate-400">Selected form<select value={selectedFormId} onChange={(event) => { setSelectedFormId(event.target.value); setVersionId(''); setEditingVersionId(null); setCreatingVersion(false); setFields([{ key: 'email', label: 'Email address', type: 'EMAIL', required: true }]) }} className={inputClass}><option value="">Choose form</option>{forms.map((form) => <option key={form.id} value={form.id}>{form.name} · {form.status}</option>)}</select></label>
            {loading ? <LoaderCircle size={16} className="mt-5 animate-spin text-slate-500" /> : !selectedForm ? <p className="mt-4 text-xs text-slate-500">Create a form to manage versions and assignments.</p> : <>
              <div className="mt-5 flex items-center justify-between gap-3"><h3 className="text-sm font-semibold text-white">Versions · {selectedForm.name}</h3><button type="button" disabled={saving || versions.length === 0 || versions.some((version) => !version.published_at)} onClick={() => { const latest = versions[0]; setEditingVersionId(null); setCreatingVersion(true); setFields(latest?.schema.fields ?? [{ key: 'email', label: 'Email address', type: 'EMAIL', required: true }]) }} className="rounded border border-white/10 px-2.5 py-1.5 text-[10px] text-blue-300 disabled:opacity-50">New version</button></div>
              <div className="mt-3 space-y-2">{versions.map((version) => <div key={version.id} className="flex items-center justify-between rounded-lg border border-white/[0.06] p-3"><div><p className="text-xs text-slate-200">Version {version.version_number}</p><p className="mt-1 text-[10px] text-slate-500">{version.published_at ? `Published ${new Date(version.published_at).toLocaleString()}` : 'Draft'}</p></div>{version.published_at ? <Check size={15} className="text-emerald-300" /> : <div className="flex gap-2"><button disabled={saving} onClick={() => { setCreatingVersion(false); setEditingVersionId(version.id); setFields(version.schema.fields) }} className="rounded border border-white/10 px-2.5 py-1.5 text-[10px] text-slate-300">Edit fields</button><button disabled={saving} onClick={() => void handlePublish(version)} className="rounded border border-white/10 px-2.5 py-1.5 text-[10px] text-blue-300">Publish</button></div>}</div>)}</div>
            </>}
          </section>

          {selectedForm && <form onSubmit={(event) => void handleAssign(event)} className="space-y-3 rounded-xl border border-white/[0.07] bg-[#101827] p-5">
            <div><h3 className="text-sm font-semibold text-white">Assign form</h3><p className="mt-1 text-xs text-slate-500">Only published versions can be assigned. A new assignment for this form and exact scope deactivates its previous assignment while retaining history. Separate forms may appear together. Region assignments cascade to child regions; the closest region takes priority, followed by product, then global.</p></div>
            <label className="block text-xs text-slate-400">Published version<select required value={versionId} onChange={(event) => setVersionId(event.target.value)} className={inputClass}><option value="">Choose version</option>{publishedVersions.map((version) => <option key={version.id} value={version.id}>Version {version.version_number}</option>)}</select></label>
            <label className="block text-xs text-slate-400">Scope<select value={scopeType} onChange={(event) => setScopeType(event.target.value as typeof scopeType)} className={inputClass}><option value="PRODUCT">Product</option><option value="REGION">Region</option><option value="GLOBAL">Global</option></select></label>
            {scopeType === 'PRODUCT' && <label className="block text-xs text-slate-400">Product<select required value={productId} onChange={(event) => setProductId(event.target.value)} className={inputClass}><option value="">Choose product</option>{products.map((product) => <option key={product.id} value={product.id}>{product.name} ({product.sku})</option>)}</select></label>}
            {scopeType === 'REGION' && <label className="block text-xs text-slate-400">Region<select required value={regionId} onChange={(event) => setRegionId(event.target.value)} className={inputClass}><option value="">Choose region</option>{regions.map((region) => <option key={region.id} value={region.id}>{regionDisplayLabel(region, regions)}</option>)}</select></label>}
            <label className="block text-xs text-slate-400">Requirement<select value={requirement} onChange={(event) => setRequirement(event.target.value as typeof requirement)} className={inputClass}><option value="OPTIONAL">Optional</option><option value="MANDATORY">Required for the customer</option></select></label>
            <button disabled={saving || !versionId} className="rounded-lg bg-blue-500 px-4 py-2.5 text-xs font-semibold text-white disabled:opacity-50">Assign</button>
            {currentAssignments.length > 0 && <div className="space-y-2 border-t border-white/[0.06] pt-3">
              <p className="text-[10px] text-slate-500">{currentAssignments.length} assignment(s) for this form.</p>
              {currentAssignments.map((assignment) => {
                const scopeLabel = assignment.scope_type === 'GLOBAL' ? 'Global' : assignment.scope_type === 'PRODUCT'
                  ? products.find((item) => item.id === assignment.product_id)?.name ?? 'Product'
                  : (() => {
                    const region = regions.find((item) => item.id === assignment.region_id)
                    return region ? regionDisplayLabel(region, regions) : 'Region'
                  })()
                return <div key={assignment.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-white/[0.06] px-3 py-2.5">
                  <div><p className="text-xs text-slate-200">{scopeLabel} · {assignment.scope_type}</p><p className="mt-1 text-[10px] text-slate-500">Version {versions.find((item) => item.id === assignment.form_version_id)?.version_number ?? '—'} · {assignment.requirement === 'MANDATORY' ? 'Required' : 'Optional'} · {assignment.is_active ? 'Active' : 'Inactive'}</p></div>
                  <div className="flex items-center gap-2">
                    <select aria-label={`Requirement for ${scopeLabel} assignment`} disabled={updatingAssignmentId === assignment.id} value={assignment.requirement} onChange={(event) => void handleUpdateAssignment(assignment, { requirement: event.target.value as FormAssignmentRecord['requirement'] })} className="rounded border border-white/10 bg-[#0b1220] px-2 py-1.5 text-[10px] text-slate-300 disabled:opacity-50"><option value="OPTIONAL">Optional</option><option value="MANDATORY">Required</option><option value="DISABLED">Hidden from scans</option></select>
                    <button type="button" disabled={updatingAssignmentId === assignment.id} onClick={() => void handleUpdateAssignment(assignment, { is_active: !assignment.is_active })} className="rounded border border-white/10 px-2.5 py-1.5 text-[10px] text-slate-300 disabled:opacity-50">{updatingAssignmentId === assignment.id ? 'Saving…' : assignment.is_active ? 'Deactivate' : 'Reactivate'}</button>
                  </div>
                </div>
              })}
            </div>}
          </form>}
        </div>
      </div>

      {selectedForm && <section className="mt-5 rounded-xl border border-white/[0.07] bg-[#101827] p-5">
        <div className="flex flex-wrap items-center justify-between gap-3"><div><h3 className="text-sm font-semibold text-white">Customer submissions</h3><p className="mt-1 text-[10px] text-slate-500">{submissionsTotal.toLocaleString()} total · most recent first</p></div><button type="button" disabled={submissionsTotal === 0 || exportingSubmissions || submissionsLoading} onClick={() => void handleExportSubmissions()} className="flex items-center gap-2 rounded-lg border border-white/10 px-3 py-2 text-xs text-slate-300 disabled:cursor-not-allowed disabled:opacity-40">{exportingSubmissions ? <LoaderCircle size={13} className="animate-spin" /> : <Download size={13} />}{exportingSubmissions ? 'Preparing CSV…' : 'Download all CSV'}</button></div>
        {submissionsLoading ? <LoaderCircle size={18} className="mx-auto mt-5 animate-spin text-slate-500" /> : submissionsTotal === 0 ? <p className="mt-3 text-xs text-slate-500">No submissions yet.</p> : <div className="mt-4 space-y-3">{submissions.map((submission) => <article key={submission.id} className="rounded-lg border border-white/[0.06] p-4"><p className="text-[10px] text-slate-500">{new Date(submission.submitted_at).toLocaleString()} · scan {submission.scan_event_id.slice(0, 8)}</p><dl className="mt-3 grid gap-3 sm:grid-cols-2">{Object.entries(submission.answers).map(([key, value]) => <div key={key}><dt className="text-[10px] capitalize text-slate-500">{key.replaceAll('_', ' ')}</dt><dd className="mt-1 break-words text-xs text-slate-200">{typeof value === 'string' ? value : JSON.stringify(value)}</dd></div>)}</dl></article>)}</div>}
        {submissionsTotal > SUBMISSIONS_PAGE_SIZE && <div className="mt-4 flex items-center justify-between border-t border-white/[0.06] pt-3 text-[10px] text-slate-500"><span>Showing {submissionOffset + 1}–{Math.min(submissionOffset + submissions.length, submissionsTotal)} of {submissionsTotal}</span><div className="flex gap-2"><button type="button" disabled={submissionOffset === 0 || submissionsLoading} onClick={() => setSubmissionOffset((current) => Math.max(0, current - SUBMISSIONS_PAGE_SIZE))} className="rounded border border-white/10 px-2.5 py-1.5 disabled:opacity-30">Previous</button><button type="button" disabled={submissionOffset + SUBMISSIONS_PAGE_SIZE >= submissionsTotal || submissionsLoading} onClick={() => setSubmissionOffset((current) => current + SUBMISSIONS_PAGE_SIZE)} className="rounded border border-white/10 px-2.5 py-1.5 disabled:opacity-30">Next</button></div></div>}
      </section>}
    </div>
  )
}

export default FormsPage
