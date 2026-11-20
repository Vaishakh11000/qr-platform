import { useEffect, useRef, useState, type ChangeEvent } from 'react'
import {
  AlertCircle,
  Download,
  FileText,
  Image as ImageIcon,
  LoaderCircle,
  Trash2,
  Upload,
  Video,
} from 'lucide-react'
import {
  deleteProductMedia,
  getProductMedia,
  getProductMediaFile,
  getProductVersions,
  uploadProductMedia,
} from '../../lib/api'
import type {
  MediaType,
  ProductMedia,
  ProductVersion,
} from '../../lib/api'

interface Props {
  productId: string
  productStatus: string
  refreshKey: number
}

interface MediaPreview {
  url: string
  mediaType: MediaType
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export default function ProductMediaPanel({
  productId,
  productStatus,
  refreshKey,
}: Props) {
  const [versions, setVersions] = useState<ProductVersion[]>([])
  const [media, setMedia] = useState<ProductMedia[]>([])
  const [selectedVersion, setSelectedVersion] = useState('')
  const [filterVersion, setFilterVersion] = useState('ALL')
  const [mediaType, setMediaType] = useState<MediaType>('IMAGE')
  const [altText, setAltText] = useState('')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [previews, setPreviews] = useState<Record<string, MediaPreview>>({})
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [busyMediaId, setBusyMediaId] = useState('')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  const draftVersions = versions.filter((version) => version.status === 'DRAFT')

  async function loadData() {
    setLoading(true)
    setError('')
    try {
      const [versionData, mediaData] = await Promise.all([
        getProductVersions(productId),
        getProductMedia(productId),
      ])
      setVersions(versionData)
      setMedia(mediaData)
      setSelectedVersion((current) =>
        current && versionData.some(
          (version) => version.id === current && version.status === 'DRAFT',
        )
          ? current
          : versionData.find((version) => version.status === 'DRAFT')?.id ?? '',
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load product media.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadData()
  }, [productId, refreshKey])

  const previewUrlsRef = useRef<string[]>([])

  useEffect(() => {
    return () => {
      previewUrlsRef.current.forEach((url) => URL.revokeObjectURL(url))
      previewUrlsRef.current = []
    }
  }, [])

  const visibleMedia = media.filter((item) =>
    filterVersion === 'ALL'
      ? true
      : filterVersion === 'UNASSIGNED'
        ? item.version_id === null
        : item.version_id === filterVersion,
  )

  async function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] ?? null
    setSelectedFile(file)
    setError('')
    setMessage('')

    if (!file) return

    if (file.type.startsWith('image/')) {
      setMediaType('IMAGE')
    } else if (file.type.startsWith('video/')) {
      setMediaType('VIDEO')
    } else {
      setMediaType('DOCUMENT')
    }
  }

  async function handleUpload() {
    if (!selectedFile) {
      setError('Choose a file first.')
      return
    }
    if (!selectedVersion) {
      setError('Create or select a draft version before uploading media.')
      return
    }
    if (!draftVersions.some((version) => version.id === selectedVersion)) {
      setError('Media can only be attached to a draft version.')
      return
    }

    setUploading(true)
    setError('')
    setMessage('')

    try {
      await uploadProductMedia(productId, selectedFile, mediaType, {
        version_id: selectedVersion,
        alt_text: altText.trim() || undefined,
      })
      setSelectedFile(null)
      setAltText('')
      const fileInput = document.getElementById(
        `media-file-${productId}`,
      ) as HTMLInputElement | null
      if (fileInput) fileInput.value = ''
      await loadData()
      setMessage('Media uploaded successfully.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not upload media.')
    } finally {
      setUploading(false)
    }
  }

  async function loadPreview(item: ProductMedia) {
    if (previews[item.id]) return

    setBusyMediaId(item.id)
    setError('')
    try {
      const blob = await getProductMediaFile(productId, item.id)
      const url = URL.createObjectURL(blob)
      previewUrlsRef.current.push(url)
      setPreviews((current) => ({
        ...current,
        [item.id]: { url, mediaType: item.media_type },
      }))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load media preview.')
    } finally {
      setBusyMediaId('')
    }
  }

  async function handleDownload(item: ProductMedia) {
    setBusyMediaId(item.id)
    setError('')
    try {
      const blob = await getProductMediaFile(productId, item.id)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = item.original_filename
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(url)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not download media.')
    } finally {
      setBusyMediaId('')
    }
  }

  async function handleDelete(item: ProductMedia) {
    if (!window.confirm(`Delete "${item.original_filename}"? This cannot be undone.`)) {
      return
    }

    setBusyMediaId(item.id)
    setError('')
    setMessage('')
    try {
      await deleteProductMedia(productId, item.id)
      setPreviews((current) => {
        const next = { ...current }
        if (next[item.id]) {
          URL.revokeObjectURL(next[item.id].url)
          previewUrlsRef.current = previewUrlsRef.current.filter(
            (url) => url !== next[item.id].url,
          )
        }
        delete next[item.id]
        return next
      })
      setMedia((current) => current.filter((entry) => entry.id !== item.id))
      setMessage('Media deleted.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not delete media.')
    } finally {
      setBusyMediaId('')
    }
  }

  function versionLabel(versionId: string | null): string {
    if (!versionId) return 'Not attached to a version'
    const version = versions.find((item) => item.id === versionId)
    return version ? `Version ${version.version_number} · ${version.status}` : 'Unknown version'
  }

  return (
    <section className="space-y-4 border-t border-white/[0.07] pt-5">
      <div className="flex items-center justify-between">
        <div>
          <h4 className="text-sm font-semibold text-white">Product media</h4>
          <p className="mt-1 text-xs text-slate-500">
            Images, videos and documents attached to product versions
          </p>
        </div>
        <span className="rounded-full bg-white/[0.06] px-2.5 py-1 text-[10px] text-slate-400">
          {media.length} files
        </span>
      </div>

      {productStatus === 'ARCHIVED' ? (
        <p className="text-xs text-slate-500">
          This product is archived. Media uploads are disabled.
        </p>
      ) : (
        <div className="space-y-3 rounded-xl border border-white/[0.08] bg-[#0b1220] p-4">
          <p className="text-xs font-medium text-slate-300">Upload media to a draft version</p>

          <label className="block">
            <span className="mb-1.5 block text-[11px] text-slate-500">Draft version *</span>
            <select
              value={selectedVersion}
              onChange={(event) => setSelectedVersion(event.target.value)}
              className="w-full rounded-lg border border-white/10 bg-[#101827] px-3 py-2 text-xs text-slate-200 outline-none"
            >
              <option value="">Select a draft version</option>
              {draftVersions.map((version) => (
                <option key={version.id} value={version.id}>
                  Version {version.version_number}
                </option>
              ))}
            </select>
          </label>

          <label className="block">
            <span className="mb-1.5 block text-[11px] text-slate-500">File *</span>
            <input
              id={`media-file-${productId}`}
              type="file"
              accept="image/*,video/*,.pdf,.doc,.docx,.xls,.xlsx,.txt"
              onChange={(event) => void handleFileChange(event)}
              className="block w-full text-xs text-slate-400 file:mr-3 file:rounded-lg file:border-0 file:bg-white/10 file:px-3 file:py-2 file:text-xs file:text-slate-200 hover:file:bg-white/15"
            />
          </label>

          {selectedFile && (
            <div className="flex items-center justify-between gap-3 text-[11px] text-slate-400">
              <span className="min-w-0 truncate">{selectedFile.name}</span>
              <span className="shrink-0">{formatSize(selectedFile.size)}</span>
            </div>
          )}

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <label className="block">
              <span className="mb-1.5 block text-[11px] text-slate-500">Media type</span>
              <select
                value={mediaType}
                onChange={(event) => setMediaType(event.target.value as MediaType)}
                className="w-full rounded-lg border border-white/10 bg-[#101827] px-3 py-2 text-xs text-slate-200 outline-none"
              >
                <option value="IMAGE">Image</option>
                <option value="VIDEO">Video</option>
                <option value="DOCUMENT">Document</option>
              </select>
            </label>

            <label className="block">
              <span className="mb-1.5 block text-[11px] text-slate-500">Alt text (optional)</span>
              <input
                value={altText}
                onChange={(event) => setAltText(event.target.value)}
                maxLength={500}
                placeholder="Describe the image"
                className="w-full rounded-lg border border-white/10 bg-[#101827] px-3 py-2 text-xs text-white outline-none"
              />
            </label>
          </div>

          <button
            type="button"
            onClick={() => void handleUpload()}
            disabled={uploading || !selectedFile || !selectedVersion || productStatus === 'ARCHIVED'}
            className="flex items-center gap-2 rounded-lg bg-blue-500 px-4 py-2.5 text-xs font-semibold text-white hover:bg-blue-400 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {uploading ? <LoaderCircle size={14} className="animate-spin" /> : <Upload size={14} />}
            {uploading ? 'Uploading...' : 'Upload media'}
          </button>

          {draftVersions.length === 0 && (
            <p className="text-[11px] text-amber-300/80">
              No draft version available. Create a draft in Product versions first.
            </p>
          )}
        </div>
      )}

      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-medium text-slate-300">Media library</p>
        <select
          value={filterVersion}
          onChange={(event) => setFilterVersion(event.target.value)}
          className="max-w-[65%] rounded-lg border border-white/10 bg-[#0b1220] px-2.5 py-2 text-[11px] text-slate-300 outline-none"
        >
          <option value="ALL">All versions</option>
          <option value="UNASSIGNED">Not attached to a version</option>
          {versions.map((version) => (
            <option key={version.id} value={version.id}>
              Version {version.version_number} · {version.status}
            </option>
          ))}
        </select>
      </div>

      {loading ? (
        <div className="flex items-center justify-center gap-2 py-8 text-xs text-slate-400">
          <LoaderCircle size={15} className="animate-spin" /> Loading media...
        </div>
      ) : visibleMedia.length === 0 ? (
        <div className="rounded-xl border border-dashed border-white/10 py-8 text-center">
          <FileText size={22} className="mx-auto text-slate-600" />
          <p className="mt-2 text-xs text-slate-400">No media found for this selection.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {visibleMedia.map((item) => {
            const preview = previews[item.id]
            const icon = item.media_type === 'IMAGE'
              ? <ImageIcon size={16} />
              : item.media_type === 'VIDEO'
                ? <Video size={16} />
                : <FileText size={16} />

            return (
              <article
                key={item.id}
                className="rounded-xl border border-white/[0.08] bg-[#0b1220] p-3"
              >
                <div className="flex items-start gap-3">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-white/[0.06] text-slate-400">
                    {icon}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-medium text-slate-200">
                      {item.original_filename}
                    </p>
                    <p className="mt-1 text-[10px] text-slate-500">
                      {item.media_type} · {formatSize(item.file_size_bytes)}
                    </p>
                    <p className="mt-1 text-[10px] text-slate-500">
                      {versionLabel(item.version_id)}
                    </p>
                    {item.alt_text && (
                      <p className="mt-1 text-[10px] text-slate-400">
                        Alt: {item.alt_text}
                      </p>
                    )}
                  </div>
                  <div className="flex shrink-0 items-center gap-1">
                    {item.media_type !== 'DOCUMENT' && (
                      <button
                        type="button"
                        title="Preview"
                        onClick={() => void loadPreview(item)}
                        disabled={Boolean(busyMediaId)}
                        className="rounded-md p-2 text-slate-400 hover:bg-white/10 hover:text-white disabled:opacity-40"
                      >
                        {busyMediaId === item.id
                          ? <LoaderCircle size={14} className="animate-spin" />
                          : <ImageIcon size={14} />}
                      </button>
                    )}
                    <button
                      type="button"
                      title="Download"
                      onClick={() => void handleDownload(item)}
                      disabled={Boolean(busyMediaId)}
                      className="rounded-md p-2 text-slate-400 hover:bg-white/10 hover:text-white disabled:opacity-40"
                    >
                      <Download size={14} />
                    </button>
                    <button
                      type="button"
                      title="Delete"
                      onClick={() => void handleDelete(item)}
                      disabled={Boolean(busyMediaId)}
                      className="rounded-md p-2 text-rose-400 hover:bg-rose-500/10 disabled:opacity-40"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>

                {preview && (
                  <div className="mt-3 overflow-hidden rounded-lg border border-white/10 bg-black/20">
                    {preview.mediaType === 'IMAGE' ? (
                      <img
                        src={preview.url}
                        alt={item.alt_text || item.original_filename}
                        className="max-h-64 w-full object-contain"
                      />
                    ) : (
                      <video
                        src={preview.url}
                        controls
                        className="max-h-64 w-full"
                      />
                    )}
                  </div>
                )}
              </article>
            )
          })}
        </div>
      )}

      {error && (
        <p className="flex items-center gap-2 text-xs text-rose-300">
          <AlertCircle size={14} /> {error}
        </p>
      )}
      {message && <p className="text-xs text-emerald-300">{message}</p>}
    </section>
  )
}
