import { useEffect, useState, type FormEvent } from 'react'
import { AlertCircle, Archive, LoaderCircle, Pencil, X } from 'lucide-react'
import {
  archiveProduct,
  getProduct,
  updateProduct,
} from '../../lib/api'
import type { Product, ProductCategory, ProductVersion } from '../../lib/api'
import ProductVersionsPanel from './ProductVersionsPanel'
import ProductMediaPanel from './ProductMediaPanel'
import ProductPagePreview from './ProductPagePreview'

interface Props {
  product: Product
  categories: ProductCategory[]
  onClose: () => void
  onSaved: (product: Product) => void
  onArchived: (productId: string) => void
}

export default function ProductDetailsModal({
  product,
  categories,
  onClose,
  onSaved,
  onArchived,
}: Props) {
  const [current, setCurrent] = useState(product)
  const [versionsRefreshKey, setVersionsRefreshKey] = useState(0)
  const [previewVersion, setPreviewVersion] = useState<ProductVersion | null>(null)
  const [editing, setEditing] = useState(false)
  const [confirmArchive, setConfirmArchive] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [name, setName] = useState(product.name)
  const [sku, setSku] = useState(product.sku)
  const [description, setDescription] = useState(product.short_description ?? '')
  const [categoryId, setCategoryId] = useState(product.category_id ?? '')

  useEffect(() => {
    getProduct(product.id)
      .then((data) => {
        setCurrent(data)
        setName(data.name)
        setSku(data.sku)
        setDescription(data.short_description ?? '')
        setCategoryId(data.category_id ?? '')
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Could not load product.'))
      .finally(() => setLoading(false))
  }, [product.id])

  async function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSaving(true)
    setError('')
    try {
      const updated = await updateProduct(current.id, {
        name: name.trim(),
        sku: sku.trim(),
        short_description: description.trim() || null,
        category_id: categoryId || null,
      })
      setCurrent(updated)
      setEditing(false)
      onSaved(updated)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not update product.')
    } finally {
      setSaving(false)
    }
  }

  async function handleArchive() {
    setSaving(true)
    setError('')
    try {
      await archiveProduct(current.id)
      onArchived(current.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not archive product.')
    } finally {
      setSaving(false)
    }
  }

  async function handleVersionsChanged() {
    setVersionsRefreshKey((key) => key + 1)
    try {
      const updated = await getProduct(current.id)
      setCurrent(updated)
      onSaved(updated)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not refresh product status.')
    }
  }

  const category = categories.find((item) => item.id === current.category_id)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="max-h-[90vh] w-full max-w-xl overflow-y-auto rounded-2xl border border-white/10 bg-[#101827] shadow-2xl">
        <div className="flex items-center justify-between border-b border-white/[0.07] px-6 py-4">
          <div>
            <h3 className="text-sm font-semibold text-white">
              {editing ? 'Edit product' : 'Product details'}
            </h3>
            <p className="mt-1 text-xs text-slate-500">{current.sku}</p>
          </div>
          <button onClick={onClose} className="text-slate-500 hover:text-white" aria-label="Close">
            <X size={18} />
          </button>
        </div>

        {loading ? (
          <div className="flex min-h-48 items-center justify-center gap-2 text-xs text-slate-400">
            <LoaderCircle size={16} className="animate-spin" /> Loading product...
          </div>
        ) : editing ? (
          <form onSubmit={handleSave} className="space-y-4 p-6">
            <label className="block">
              <span className="mb-2 block text-xs text-slate-400">Product name *</span>
              <input required maxLength={255} value={name} onChange={(e) => setName(e.target.value)} className="w-full rounded-lg border border-white/10 bg-[#0b1220] px-3 py-2.5 text-sm text-white outline-none focus:border-blue-500/50" />
            </label>
            <label className="block">
              <span className="mb-2 block text-xs text-slate-400">SKU *</span>
              <input required maxLength={100} value={sku} onChange={(e) => setSku(e.target.value)} className="w-full rounded-lg border border-white/10 bg-[#0b1220] px-3 py-2.5 text-sm text-white outline-none focus:border-blue-500/50" />
            </label>
            <label className="block">
              <span className="mb-2 block text-xs text-slate-400">Category</span>
              <select value={categoryId} onChange={(e) => setCategoryId(e.target.value)} className="w-full rounded-lg border border-white/10 bg-[#0b1220] px-3 py-2.5 text-sm text-slate-300 outline-none">
                <option value="">No category</option>
                {categories.map((item) => <option key={item.id} value={item.id} disabled={!item.is_active && categoryId !== item.id}>{item.name}{item.is_active ? '' : ' (inactive)'}</option>)}
              </select>
            </label>
            <label className="block">
              <span className="mb-2 block text-xs text-slate-400">Short description</span>
              <textarea rows={3} maxLength={1000} value={description} onChange={(e) => setDescription(e.target.value)} className="w-full resize-y rounded-lg border border-white/10 bg-[#0b1220] px-3 py-2.5 text-sm text-white outline-none focus:border-blue-500/50" />
            </label>
            {error && <p className="text-xs text-rose-300">{error}</p>}
            <div className="flex justify-end gap-2">
              <button type="button" onClick={() => { setEditing(false); setError('') }} className="rounded-lg border border-white/10 px-4 py-2.5 text-xs text-slate-300">Cancel</button>
              <button disabled={saving} className="rounded-lg bg-blue-500 px-4 py-2.5 text-xs font-semibold text-white disabled:opacity-50">
                {saving ? 'Saving...' : 'Save changes'}
              </button>
            </div>
          </form>
        ) : (
          <div className="space-y-5 p-6">
            <div>
              <p className="text-lg font-semibold text-white">{current.name}</p>
              <p className="mt-1 text-xs text-slate-400">{current.sku}</p>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-[10px] uppercase tracking-wider text-slate-500">Status</p>
                <p className="mt-1 text-xs text-slate-200">
                  {current.status === 'ACTIVE' ? 'PUBLISHED' : current.status}
                </p>
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-wider text-slate-500">Category</p>
                <p className="mt-1 text-xs text-slate-200">{category ? `${category.name}${category.is_active ? '' : ' (inactive)'}` : 'None'}</p>
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-wider text-slate-500">Created</p>
                <p className="mt-1 text-xs text-slate-200">{new Date(current.created_at).toLocaleString()}</p>
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-wider text-slate-500">Last updated</p>
                <p className="mt-1 text-xs text-slate-200">{new Date(current.updated_at).toLocaleString()}</p>
              </div>
            </div>
            <div>
              <p className="text-[10px] uppercase tracking-wider text-slate-500">Description</p>
              <p className="mt-2 whitespace-pre-wrap text-sm text-slate-300">{current.short_description || 'No description provided.'}</p>
            </div>

            <ProductVersionsPanel
              productId={current.id}
              productStatus={current.status}
              onVersionsChanged={handleVersionsChanged}
              onPreviewVersion={setPreviewVersion}
            />

            <ProductMediaPanel
              productId={current.id}
              productStatus={current.status}
              refreshKey={versionsRefreshKey}
            />

            {previewVersion && (
              <ProductPagePreview
                product={current}
                version={previewVersion}
                onClose={() => setPreviewVersion(null)}
              />
            )}

            {confirmArchive ? (
              <div className="rounded-lg border border-rose-500/20 bg-rose-500/10 p-4">
                <p className="text-sm font-medium text-rose-200">Archive this product?</p>
                <p className="mt-1 text-xs text-rose-200/70">It will no longer be active in the catalogue. This action does not permanently delete its data.</p>
                <div className="mt-3 flex justify-end gap-2">
                  <button onClick={() => setConfirmArchive(false)} className="rounded-lg border border-white/10 px-3 py-2 text-xs text-slate-300">Cancel</button>
                  <button onClick={() => void handleArchive()} disabled={saving} className="rounded-lg bg-rose-500 px-3 py-2 text-xs font-semibold text-white disabled:opacity-50">{saving ? 'Archiving...' : 'Confirm archive'}</button>
                </div>
              </div>
            ) : (
              <div className="flex justify-between border-t border-white/[0.07] pt-4">
                <button
                  onClick={() => setConfirmArchive(true)}
                  disabled={current.status === 'ARCHIVED'}
                  className="flex items-center gap-2 rounded-lg border border-rose-500/20 px-3 py-2 text-xs text-rose-300 hover:bg-rose-500/10 disabled:opacity-30"
                >
                  <Archive size={14} /> Archive
                </button>
                <button onClick={() => setEditing(true)} disabled={current.status === 'ARCHIVED'} className="flex items-center gap-2 rounded-lg bg-blue-500 px-4 py-2 text-xs font-semibold text-white hover:bg-blue-400 disabled:opacity-30">
                  <Pencil size={14} /> Edit product
                </button>
              </div>
            )}
            {error && <p className="flex items-center gap-2 text-xs text-rose-300"><AlertCircle size={14} />{error}</p>}
          </div>
        )}
      </div>
    </div>
  )
}
