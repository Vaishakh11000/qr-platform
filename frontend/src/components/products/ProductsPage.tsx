import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import {
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  LoaderCircle,
  Package,
  Plus,
  Search,
  X,
} from 'lucide-react'
import {
  createProduct,
  getAllCategories,
  getProduct,
  getProducts,
} from '../../lib/api'
import type {
  Product,
  ProductCategory,
  ProductStatus,
} from '../../lib/api'
import ProductDetailsModal from './ProductDetailsModal'

const PAGE_SIZE = 50

const statusStyles: Record<ProductStatus, string> = {
  DRAFT: 'bg-amber-500/10 text-amber-300 border-amber-500/20',
  ACTIVE: 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20',
  ARCHIVED: 'bg-slate-500/10 text-slate-400 border-slate-500/20',
}

function ProductsPage({ searchTargetId, searchTargetNonce }: { searchTargetId?: string; searchTargetNonce: number }) {
  const [products, setProducts] = useState<Product[]>([])
  const [categories, setCategories] = useState<ProductCategory[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState<ProductStatus | ''>('')
  const [categoryId, setCategoryId] = useState('')
  const [offset, setOffset] = useState(0)
  const [reloadNonce, setReloadNonce] = useState(0)
  const [showCreate, setShowCreate] = useState(false)
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')

  const [sku, setSku] = useState('')
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [newCategoryId, setNewCategoryId] = useState('')
  const requestSequence = useRef(0)

  const loadProducts = useCallback(async () => {
    const requestId = ++requestSequence.current
    setLoading(true)
    setError('')
    try {
      const data = await getProducts({
        offset,
        limit: PAGE_SIZE,
        status: status || undefined,
        category_id: categoryId || undefined,
      })
      if (requestId === requestSequence.current) setProducts(data)
    } catch (err) {
      if (requestId === requestSequence.current) setError(err instanceof Error ? err.message : 'Could not load products.')
    } finally {
      if (requestId === requestSequence.current) setLoading(false)
    }
  }, [offset, status, categoryId])

  useEffect(() => {
    getAllCategories(null)
      .then(setCategories)
      .catch(() => setCategories([]))
  }, [])

  useEffect(() => { void loadProducts() }, [loadProducts, reloadNonce])

  useEffect(() => {
    if (!searchTargetId) return
    let active = true
    getProduct(searchTargetId)
      .then((product) => { if (active) setSelectedProduct(product) })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : 'Could not open the searched product.')
      })
    return () => { active = false }
  }, [searchTargetId, searchTargetNonce])

  const filteredProducts = useMemo(() => {
    const term = search.trim().toLowerCase()
    if (!term) return products
    return products.filter((product) =>
      [product.name, product.sku, product.short_description ?? '']
        .some((value) => value.toLowerCase().includes(term)),
    )
  }, [products, search])

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSaving(true)
    setFormError('')
    try {
      await createProduct({
        sku: sku.trim(),
        name: name.trim(),
        short_description: description.trim() || null,
        category_id: newCategoryId || null,
      })
      setShowCreate(false)
      setSku('')
      setName('')
      setDescription('')
      setNewCategoryId('')
      setOffset(0)
      setReloadNonce((value) => value + 1)
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Could not create product.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div>
      <div className="mb-7 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="text-sm text-slate-400">Catalogue management</p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight text-white">
            Products
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            Create, organise and manage your product catalogue.
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex w-fit items-center gap-2 rounded-lg bg-blue-500 px-4 py-2.5 text-xs font-semibold text-white transition hover:bg-blue-400"
        >
          <Plus size={15} />
          New product
        </button>
      </div>

      <div className="mb-5 flex flex-col gap-3 rounded-xl border border-white/[0.07] bg-[#101827] p-4 sm:flex-row">
        <div className="relative min-w-0 flex-1">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search this page by name, SKU or description..."
            className="w-full rounded-lg border border-white/10 bg-[#0b1220] py-2.5 pl-9 pr-3 text-xs text-white outline-none placeholder:text-slate-600 focus:border-blue-500/50"
          />
        </div>
        <select
          value={status}
          onChange={(event) => {
            setStatus(event.target.value as ProductStatus | '')
            setOffset(0)
          }}
          className="rounded-lg border border-white/10 bg-[#0b1220] px-3 py-2.5 text-xs text-slate-300 outline-none"
        >
          <option value="">All statuses</option>
          <option value="DRAFT">Draft</option>
          <option value="ACTIVE">Published</option>
          <option value="ARCHIVED">Archived</option>
        </select>
        <select
          value={categoryId}
          onChange={(event) => {
            setCategoryId(event.target.value)
            setOffset(0)
          }}
          className="rounded-lg border border-white/10 bg-[#0b1220] px-3 py-2.5 text-xs text-slate-300 outline-none"
        >
          <option value="">All categories</option>
          {categories.map((category) => (
            <option key={category.id} value={category.id}>
              {category.name}{category.is_active ? '' : ' (inactive)'}
            </option>
          ))}
        </select>
      </div>

      <div className="overflow-hidden rounded-xl border border-white/[0.07] bg-[#101827]">
        <div className="flex items-center justify-between border-b border-white/[0.06] px-5 py-4">
          <div>
            <h3 className="text-sm font-semibold text-white">Product catalogue</h3>
            <p className="mt-1 text-[11px] text-slate-500">
              {filteredProducts.length} product{filteredProducts.length === 1 ? '' : 's'} on this page
            </p>
          </div>
          <Package size={18} className="text-slate-500" />
        </div>

        {error && (
          <div className="m-5 flex items-center gap-2 rounded-lg border border-rose-500/20 bg-rose-500/10 p-3 text-xs text-rose-300">
            <AlertCircle size={15} />
            {error}
            <button onClick={() => void loadProducts()} className="ml-auto underline">
              Retry
            </button>
          </div>
        )}

        {loading ? (
          <div className="flex min-h-56 items-center justify-center gap-2 text-xs text-slate-500">
            <LoaderCircle size={17} className="animate-spin" />
            Loading products...
          </div>
        ) : filteredProducts.length === 0 ? (
          <div className="flex min-h-56 flex-col items-center justify-center px-5 text-center">
            <Package size={28} className="text-slate-600" />
            <p className="mt-3 text-sm font-medium text-slate-300">
              {search ? 'No matching products' : 'No products found'}
            </p>
            <p className="mt-1 text-xs text-slate-500">
              {search ? 'Try another search term.' : 'Create your first product to get started.'}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[700px] text-left">
              <thead className="bg-white/[0.02] text-[10px] uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="px-5 py-3 font-medium">Product</th>
                  <th className="px-5 py-3 font-medium">SKU</th>
                  <th className="px-5 py-3 font-medium">Category</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium">Created</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.05]">
                {filteredProducts.map((product) => {
                  const category = categories.find((item) => item.id === product.category_id)
                  return (
                    <tr
                      key={product.id}
                      onClick={() => setSelectedProduct(product)}
                      className="cursor-pointer transition hover:bg-white/[0.04]"
                    >
                      <td className="px-5 py-4">
                        <p className="text-xs font-medium text-slate-200">{product.name}</p>
                        <p className="mt-1 max-w-xs truncate text-[10px] text-slate-500">
                          {product.short_description || 'No description'}
                        </p>
                      </td>
                      <td className="px-5 py-4 font-mono text-[11px] text-slate-400">
                        {product.sku}
                      </td>
                      <td className="px-5 py-4 text-xs text-slate-400">
                        {category ? `${category.name}${category.is_active ? '' : ' (inactive)'}` : '—'}
                      </td>
                      <td className="px-5 py-4">
                        <span className={`rounded-md border px-2 py-1 text-[10px] font-medium ${statusStyles[product.status]}`}>
                          {product.status === 'ACTIVE' ? 'PUBLISHED' : product.status}
                        </span>
                      </td>
                      <td className="px-5 py-4 text-[11px] text-slate-500">
                        {new Date(product.created_at).toLocaleDateString()}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}

        <div className="flex items-center justify-between border-t border-white/[0.06] px-5 py-3">
          <p className="text-[11px] text-slate-500">
            Showing {offset + (products.length ? 1 : 0)}–{offset + products.length}
          </p>
          <div className="flex gap-2">
            <button
              disabled={offset === 0 || loading}
              onClick={() => setOffset((value) => Math.max(0, value - PAGE_SIZE))}
              className="rounded-lg border border-white/10 p-2 text-slate-400 transition hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-30"
              aria-label="Previous page"
            >
              <ChevronLeft size={15} />
            </button>
            <button
              disabled={products.length < PAGE_SIZE || loading}
              onClick={() => setOffset((value) => value + PAGE_SIZE)}
              className="rounded-lg border border-white/10 p-2 text-slate-400 transition hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-30"
              aria-label="Next page"
            >
              <ChevronRight size={15} />
            </button>
          </div>
        </div>
      </div>

      {selectedProduct && (
        <ProductDetailsModal
          product={selectedProduct}
          categories={categories}
          onClose={() => setSelectedProduct(null)}
          onSaved={(updated) => {
            setProducts((current) =>
              current.map((item) => item.id === updated.id ? updated : item),
            )
            setSelectedProduct(updated)
          }}
          onArchived={() => {
            setSelectedProduct(null)
            void loadProducts()
          }}
        />
      )}

      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
          <div className="w-full max-w-lg rounded-2xl border border-white/10 bg-[#101827] shadow-2xl">
            <div className="flex items-center justify-between border-b border-white/[0.07] px-6 py-4">
              <div>
                <h3 className="text-sm font-semibold text-white">Create product</h3>
                <p className="mt-1 text-xs text-slate-500">Add a new draft to your catalogue.</p>
              </div>
              <button onClick={() => setShowCreate(false)} className="text-slate-500 hover:text-white" aria-label="Close">
                <X size={18} />
              </button>
            </div>
            <form onSubmit={handleCreate} className="space-y-4 p-6">
              <label className="block">
                <span className="mb-2 block text-xs text-slate-400">Product name *</span>
                <input required maxLength={255} value={name} onChange={(event) => setName(event.target.value)} className="w-full rounded-lg border border-white/10 bg-[#0b1220] px-3 py-2.5 text-sm text-white outline-none focus:border-blue-500/50" />
              </label>
              <label className="block">
                <span className="mb-2 block text-xs text-slate-400">SKU *</span>
                <input required maxLength={100} value={sku} onChange={(event) => setSku(event.target.value)} className="w-full rounded-lg border border-white/10 bg-[#0b1220] px-3 py-2.5 text-sm text-white outline-none focus:border-blue-500/50" />
              </label>
              <label className="block">
                <span className="mb-2 block text-xs text-slate-400">Category</span>
                <select value={newCategoryId} onChange={(event) => setNewCategoryId(event.target.value)} className="w-full rounded-lg border border-white/10 bg-[#0b1220] px-3 py-2.5 text-sm text-slate-300 outline-none">
                  <option value="">No category</option>
                  {categories.filter((category) => category.is_active).map((category) => (
                    <option key={category.id} value={category.id}>{category.name}</option>
                  ))}
                </select>
              </label>
              <label className="block">
                <span className="mb-2 block text-xs text-slate-400">Short description</span>
                <textarea rows={3} maxLength={1000} value={description} onChange={(event) => setDescription(event.target.value)} className="w-full resize-y rounded-lg border border-white/10 bg-[#0b1220] px-3 py-2.5 text-sm text-white outline-none focus:border-blue-500/50" />
              </label>
              {formError && <p className="text-xs text-rose-300">{formError}</p>}
              <div className="flex justify-end gap-2 pt-2">
                <button type="button" onClick={() => setShowCreate(false)} className="rounded-lg border border-white/10 px-4 py-2.5 text-xs text-slate-300 hover:bg-white/5">
                  Cancel
                </button>
                <button type="submit" disabled={saving} className="flex items-center gap-2 rounded-lg bg-blue-500 px-4 py-2.5 text-xs font-semibold text-white hover:bg-blue-400 disabled:opacity-50">
                  {saving && <LoaderCircle size={14} className="animate-spin" />}
                  Create product
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

export default ProductsPage
