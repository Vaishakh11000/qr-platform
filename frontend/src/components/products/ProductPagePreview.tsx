import { useEffect, useState } from 'react'
import {
  Download,
  FileText,
  Image as ImageIcon,
  LoaderCircle,
  X,
} from 'lucide-react'
import {
  getProductMedia,
  getProductMediaFile,
} from '../../lib/api'
import type {
  Product,
  ProductMedia,
  ProductVersion,
} from '../../lib/api'

interface Props {
  product: Product
  version: ProductVersion
  onClose: () => void
}

function stringValue(value: unknown): string {
  return typeof value === 'string' ? value : ''
}

function stringList(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === 'string')
    : []
}

export default function ProductPagePreview({
  product,
  version,
  onClose,
}: Props) {
  const snapshot = version.content_snapshot
  const name = stringValue(snapshot.name) || product.name
  const description = stringValue(snapshot.description)
  const features = stringList(snapshot.features)
  const benefits = stringList(snapshot.benefits)
  const applications = stringList(snapshot.applications)
  const materials = stringList(snapshot.supported_materials)
  const specifications =
    snapshot.specifications &&
    typeof snapshot.specifications === 'object' &&
    !Array.isArray(snapshot.specifications)
      ? Object.entries(snapshot.specifications as Record<string, unknown>)
      : []

  const [media, setMedia] = useState<ProductMedia[]>([])
  const [mediaUrls, setMediaUrls] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState('')

  useEffect(() => {
    let cancelled = false
    const urls: string[] = []

    async function loadMedia() {
      setLoading(true)
      setError('')
      try {
        const result = await getProductMedia(product.id, version.id)
        if (!cancelled) setMedia(result)

        const loaded: Record<string, string> = {}
        for (const item of result) {
          if (item.media_type === 'DOCUMENT') continue
          try {
            const blob = await getProductMediaFile(product.id, item.id)
            if (cancelled) return
            const url = URL.createObjectURL(blob)
            urls.push(url)
            loaded[item.id] = url
            setMediaUrls((current) => ({ ...current, [item.id]: url }))
          } catch {
            // Keep the rest of the gallery available if one file fails.
          }
        }
        if (!cancelled) setMediaUrls(loaded)
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Could not load preview media.')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    void loadMedia()

    return () => {
      cancelled = true
      urls.forEach((url) => URL.revokeObjectURL(url))
    }
  }, [product.id, version.id])

  async function downloadDocument(item: ProductMedia) {
    setBusyId(item.id)
    setError('')
    try {
      const blob = await getProductMediaFile(product.id, item.id)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = item.original_filename
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(url)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not download document.')
    } finally {
      setBusyId('')
    }
  }

  return (
    <div className="fixed inset-0 z-[60] overflow-y-auto bg-slate-950">
      <header className="sticky top-0 z-10 flex items-center justify-between border-b border-white/10 bg-[#101827]/95 px-5 py-4 backdrop-blur">
        <div>
          <p className="text-sm font-semibold text-white">Product page preview</p>
          <p className="mt-1 text-xs text-slate-400">
            Version {version.version_number} · {version.status}
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="flex items-center gap-2 rounded-lg border border-white/10 px-3 py-2 text-xs text-slate-300 hover:bg-white/10"
        >
          <X size={15} /> Close preview
        </button>
      </header>

      <main className="mx-auto max-w-5xl space-y-10 px-5 py-10">
        <section className="rounded-2xl border border-white/10 bg-[#101827] p-8">
          <span className="text-xs uppercase tracking-widest text-blue-300">
            {product.sku}
          </span>
          <h1 className="mt-3 text-3xl font-semibold text-white">{name}</h1>
          <p className="mt-4 max-w-3xl whitespace-pre-wrap text-sm leading-7 text-slate-300">
            {description || 'No product description has been added.'}
          </p>
        </section>

        {media.length > 0 && (
          <section>
            <h2 className="mb-4 text-lg font-semibold text-white">Product gallery</h2>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {media.map((item) => (
                <div
                  key={item.id}
                  className="overflow-hidden rounded-xl border border-white/10 bg-[#101827]"
                >
                  {item.media_type === 'IMAGE' && mediaUrls[item.id] ? (
                    <img
                      src={mediaUrls[item.id]}
                      alt={item.alt_text || item.original_filename}
                      className="h-56 w-full object-contain bg-black/20"
                    />
                  ) : item.media_type === 'VIDEO' && mediaUrls[item.id] ? (
                    <video
                      src={mediaUrls[item.id]}
                      controls
                      className="h-56 w-full bg-black"
                    />
                  ) : item.media_type === 'DOCUMENT' ? (
                    <div className="flex h-56 flex-col items-center justify-center gap-3 text-slate-400">
                      <FileText size={36} />
                      <span className="max-w-full truncate px-3 text-xs">
                        {item.original_filename}
                      </span>
                      <button
                        type="button"
                        onClick={() => void downloadDocument(item)}
                        disabled={busyId === item.id}
                        className="flex items-center gap-2 rounded-lg bg-blue-500/10 px-3 py-2 text-xs text-blue-300 hover:bg-blue-500/20 disabled:opacity-50"
                      >
                        {busyId === item.id
                          ? <LoaderCircle size={14} className="animate-spin" />
                          : <Download size={14} />}
                        Download
                      </button>
                    </div>
                  ) : (
                    <div className="flex h-56 items-center justify-center text-slate-500">
                      <ImageIcon size={28} />
                    </div>
                  )}
                  <p className="truncate border-t border-white/[0.07] px-3 py-2 text-xs text-slate-400">
                    {item.alt_text || item.original_filename}
                  </p>
                </div>
              ))}
            </div>
          </section>
        )}

        {loading && (
          <p className="flex items-center gap-2 text-xs text-slate-400">
            <LoaderCircle size={15} className="animate-spin" />
            Loading product media...
          </p>
        )}
        {error && <p className="text-xs text-rose-300">{error}</p>}

        {features.length > 0 && (
          <section>
            <h2 className="mb-4 text-lg font-semibold text-white">Features</h2>
            <ul className="grid gap-3 sm:grid-cols-2">
              {features.map((item, index) => (
                <li key={index} className="rounded-xl border border-white/10 bg-[#101827] p-4 text-sm text-slate-300">
                  {item}
                </li>
              ))}
            </ul>
          </section>
        )}

        {benefits.length > 0 && (
          <section>
            <h2 className="mb-4 text-lg font-semibold text-white">Benefits</h2>
            <ul className="grid gap-3 sm:grid-cols-2">
              {benefits.map((item, index) => (
                <li key={index} className="rounded-xl border border-white/10 bg-[#101827] p-4 text-sm text-slate-300">
                  {item}
                </li>
              ))}
            </ul>
          </section>
        )}

        {specifications.length > 0 && (
          <section>
            <h2 className="mb-4 text-lg font-semibold text-white">Technical specifications</h2>
            <div className="overflow-hidden rounded-xl border border-white/10">
              {specifications.map(([key, value], index) => (
                <div
                  key={key}
                  className={`grid grid-cols-2 gap-4 px-4 py-3 text-sm ${
                    index % 2 === 0 ? 'bg-[#101827]' : 'bg-white/[0.03]'
                  }`}
                >
                  <span className="text-slate-400">{key}</span>
                  <span className="text-slate-200">{String(value)}</span>
                </div>
              ))}
            </div>
          </section>
        )}

        {applications.length > 0 && (
          <section>
            <h2 className="mb-4 text-lg font-semibold text-white">Applications</h2>
            <div className="flex flex-wrap gap-2">
              {applications.map((item, index) => (
                <span key={index} className="rounded-full border border-white/10 px-3 py-2 text-xs text-slate-300">
                  {item}
                </span>
              ))}
            </div>
          </section>
        )}

        {materials.length > 0 && (
          <section>
            <h2 className="mb-4 text-lg font-semibold text-white">Supported materials</h2>
            <div className="flex flex-wrap gap-2">
              {materials.map((item, index) => (
                <span key={index} className="rounded-full border border-white/10 px-3 py-2 text-xs text-slate-300">
                  {item}
                </span>
              ))}
            </div>
          </section>
        )}

        <section className="rounded-2xl border border-blue-500/20 bg-blue-500/[0.06] p-8 text-center">
          <h2 className="text-xl font-semibold text-white">Interested in this product?</h2>
          <p className="mt-2 text-sm text-slate-400">
            Contact our team to learn more about specifications, pricing and availability.
          </p>
          <p className="mt-5 text-xs text-blue-300">
            Enquiry form will be connected in a later stage.
          </p>
        </section>
      </main>
    </div>
  )
}
