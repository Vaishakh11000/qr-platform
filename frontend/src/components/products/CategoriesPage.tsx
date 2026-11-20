import { useEffect, useState, type FormEvent } from 'react'
import { AlertCircle, Check, Edit2, LoaderCircle, Plus, RefreshCw, Tags, X } from 'lucide-react'
import { createCategory, getAllCategories, updateCategory } from '../../lib/api'
import type { ProductCategory } from '../../lib/api'

function categoryDescendants(rootId: string, categories: ProductCategory[]) {
  const excluded = new Set([rootId])
  let changed = true
  while (changed) {
    changed = false
    for (const category of categories) {
      if (category.parent_id && excluded.has(category.parent_id) && !excluded.has(category.id)) {
        excluded.add(category.id)
        changed = true
      }
    }
  }
  return excluded
}

function CategoriesPage({ searchTargetId, searchTargetNonce }: { searchTargetId?: string; searchTargetNonce: number }) {
  const [categories, setCategories] = useState<ProductCategory[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [editing, setEditing] = useState<ProductCategory | null>(null)
  const [modalOpen, setModalOpen] = useState(false)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [parentId, setParentId] = useState('')

  async function loadCategories(showLoading = true) {
    if (showLoading) {
      setLoading(true)
      setError('')
    }
    try {
      setCategories(await getAllCategories(null))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load categories.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void loadCategories(false) }, [])

  useEffect(() => {
    if (!searchTargetId || loading) return
    const category = categories.find((item) => item.id === searchTargetId)
    if (!category) {
      setError('The searched category is not in the current category list.')
      return
    }
    document.getElementById(`category-${searchTargetId}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, [categories, loading, searchTargetId, searchTargetNonce])

  function openCreate() {
    setModalOpen(true)
    setEditing(null)
    setName('')
    setDescription('')
    setParentId('')
    setError('')
    setSuccess('')
  }

  function openEdit(category: ProductCategory) {
    setModalOpen(true)
    setEditing(category)
    setName(category.name)
    setDescription(category.description ?? '')
    setParentId(category.parent_id ?? '')
    setError('')
    setSuccess('')
  }

  async function saveCategory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSaving(true)
    setError('')
    try {
      const data = {
        name: name.trim(),
        description: description.trim() || null,
        parent_id: parentId || null,
      }
      if (editing) await updateCategory(editing.id, data)
      else await createCategory(data)
      setModalOpen(false)
      setEditing(null)
      setSuccess(editing ? 'Category updated.' : 'Category created.')
      await loadCategories()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save category.')
    } finally {
      setSaving(false)
    }
  }

  async function toggleActive(category: ProductCategory) {
    setError('')
    setSuccess('')
    try {
      await updateCategory(category.id, { is_active: !category.is_active })
      setSuccess(category.is_active ? 'Category deactivated.' : 'Category reactivated.')
      await loadCategories()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not update category status.')
    }
  }

  const parentName = (id: string | null) => categories.find((item) => item.id === id)?.name ?? '—'
  const excludedParentIds = editing ? categoryDescendants(editing.id, categories) : new Set<string>()

  return (
    <div>
      <div className="mb-7 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="text-sm text-slate-400">Product organization</p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight text-white">Categories</h2>
          <p className="mt-1 text-sm text-slate-500">Organize products with parent and child categories.</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => void loadCategories()} aria-label="Refresh categories" className="rounded-lg border border-white/10 p-2.5 text-slate-400 hover:text-white"><RefreshCw size={14} /></button>
          <button onClick={openCreate} className="flex items-center gap-2 rounded-lg bg-blue-500 px-4 py-2.5 text-xs font-semibold text-white hover:bg-blue-400"><Plus size={14} />New category</button>
        </div>
      </div>

      {error && <p role="alert" className="mb-4 flex items-center gap-2 rounded-lg border border-rose-500/20 bg-rose-500/10 p-3 text-xs text-rose-300"><AlertCircle size={14} />{error}</p>}
      {success && <p role="status" className="mb-4 flex items-center gap-2 rounded-lg border border-emerald-500/20 bg-emerald-500/10 p-3 text-xs text-emerald-300"><Check size={14} />{success}</p>}

      <div className="mb-4 rounded-lg border border-blue-500/15 bg-blue-500/[0.06] p-3 text-xs leading-5 text-slate-400">Inactive categories remain attached to existing products. New products can only be assigned to active categories.</div>

      <section className="overflow-hidden rounded-xl border border-white/[0.07] bg-[#101827]">
        <div className="flex items-center justify-between border-b border-white/[0.07] px-5 py-4">
          <h3 className="flex items-center gap-2 text-xs font-semibold text-slate-200"><Tags size={15} />Category list</h3>
          <span className="text-[10px] text-slate-500">{categories.length} total</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[700px] text-left text-xs">
            <thead className="border-b border-white/[0.07] text-[10px] uppercase tracking-wider text-slate-500"><tr><th className="px-5 py-4">Name</th><th className="px-5 py-4">Parent</th><th className="px-5 py-4">Description</th><th className="px-5 py-4">Status</th><th className="px-5 py-4 text-right">Actions</th></tr></thead>
            <tbody className="divide-y divide-white/[0.05] text-slate-300">
              {loading ? <tr><td colSpan={5} className="px-5 py-12 text-center text-slate-500"><LoaderCircle size={18} className="mx-auto animate-spin" /></td></tr>
                : categories.length === 0 ? <tr><td colSpan={5} className="px-5 py-12 text-center text-slate-500">No categories yet. Create one to organize products.</td></tr>
                  : categories.map((category) => <tr id={`category-${category.id}`} key={category.id} className={searchTargetId === category.id ? 'bg-blue-500/[0.08]' : 'hover:bg-white/[0.02]'}>
                    <td className="px-5 py-4 font-medium text-white">{category.name}</td>
                    <td className="px-5 py-4 text-slate-400">{parentName(category.parent_id)}</td>
                    <td className="max-w-[320px] truncate px-5 py-4 text-slate-400" title={category.description ?? ''}>{category.description || '—'}</td>
                    <td className="px-5 py-4"><span className={`rounded-full border px-2 py-1 text-[10px] ${category.is_active ? 'border-emerald-500/20 bg-emerald-500/10 text-emerald-300' : 'border-slate-500/20 bg-slate-500/10 text-slate-400'}`}>{category.is_active ? 'ACTIVE' : 'INACTIVE'}</span></td>
                    <td className="px-5 py-4"><div className="flex justify-end gap-2"><button onClick={() => openEdit(category)} className="flex items-center gap-1 rounded-md border border-white/10 px-2.5 py-2 text-[10px] text-slate-300 hover:text-white"><Edit2 size={12} />Edit</button><button onClick={() => void toggleActive(category)} className="rounded-md border border-white/10 px-2.5 py-2 text-[10px] text-slate-300 hover:text-white">{category.is_active ? 'Deactivate' : 'Reactivate'}</button></div></td>
                  </tr>)}
            </tbody>
          </table>
        </div>
      </section>

      {modalOpen && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" onMouseDown={(event) => { if (event.target === event.currentTarget) setModalOpen(false) }}>
        <section className="w-full max-w-lg rounded-2xl border border-white/10 bg-[#101827] p-6 shadow-2xl">
          <div className="mb-5 flex items-center justify-between"><div><h3 className="text-lg font-semibold text-white">{editing ? 'Edit category' : 'New category'}</h3><p className="mt-1 text-xs text-slate-500">Set its name, description, and optional parent.</p></div><button onClick={() => setModalOpen(false)} aria-label="Close dialog" className="text-slate-500 hover:text-white"><X size={18} /></button></div>
          <form onSubmit={(event) => void saveCategory(event)} className="space-y-4">
            <label className="block text-xs text-slate-400">Name<input required maxLength={150} value={name} onChange={(event) => setName(event.target.value)} className="mt-2 w-full rounded-lg border border-white/10 bg-[#0b1220] px-3 py-2.5 text-sm text-white outline-none focus:border-blue-500/50" /></label>
            <label className="block text-xs text-slate-400">Description <span className="text-slate-600">(optional)</span><textarea maxLength={2000} rows={3} value={description} onChange={(event) => setDescription(event.target.value)} className="mt-2 w-full rounded-lg border border-white/10 bg-[#0b1220] px-3 py-2.5 text-sm text-white outline-none focus:border-blue-500/50" /></label>
            <label className="block text-xs text-slate-400">Parent category <span className="text-slate-600">(optional)</span><select value={parentId} onChange={(event) => setParentId(event.target.value)} className="mt-2 w-full rounded-lg border border-white/10 bg-[#0b1220] px-3 py-2.5 text-sm text-white outline-none focus:border-blue-500/50"><option value="">No parent</option>{categories.filter((category) => !excludedParentIds.has(category.id) && (editing !== null || category.is_active)).map((category) => <option key={category.id} value={category.id}>{category.name}{category.is_active ? '' : ' (inactive)'}</option>)}</select></label>
            {error && <p role="alert" className="flex items-center gap-2 rounded-lg border border-rose-500/20 bg-rose-500/10 p-3 text-xs text-rose-300"><AlertCircle size={14} />{error}</p>}
            <div className="flex justify-end gap-2"><button type="button" onClick={() => setModalOpen(false)} className="rounded-lg border border-white/10 px-4 py-2.5 text-xs text-slate-300">Cancel</button><button disabled={saving} className="flex items-center gap-2 rounded-lg bg-blue-500 px-4 py-2.5 text-xs font-semibold text-white disabled:opacity-50">{saving && <LoaderCircle size={13} className="animate-spin" />}{editing ? 'Save changes' : 'Create category'}</button></div>
          </form>
        </section>
      </div>}
    </div>
  )
}

export default CategoriesPage
