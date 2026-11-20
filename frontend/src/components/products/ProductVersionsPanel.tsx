import { useEffect, useState, type FormEvent } from 'react'
import {
  AlertCircle,
  Check,
  Clock,
  FilePlus2,
  Eye,
  LoaderCircle,
  Pencil,
  Upload,
} from 'lucide-react'
import {
  createProductVersion,
  getProductVersions,
  publishProductVersion,
  updateProductVersion,
} from '../../lib/api'
import type { ProductVersion } from '../../lib/api'
import VersionSnapshotView from './VersionSnapshotView'

interface ProductVersionsPanelProps {
  productId: string
  productStatus: string
  onVersionsChanged: () => void | Promise<void>
  onPreviewVersion: (version: ProductVersion) => void
}

const statusStyles: Record<string, string> = {
  DRAFT: 'border-amber-500/20 bg-amber-500/10 text-amber-300',
  PUBLISHED: 'border-emerald-500/20 bg-emerald-500/10 text-emerald-300',
  RETIRED: 'border-slate-500/20 bg-slate-500/10 text-slate-400',
}

function ProductVersionsPanel({
  productId,
  productStatus,
  onVersionsChanged,
  onPreviewVersion,
}: ProductVersionsPanelProps) {
  const [versions, setVersions] = useState<ProductVersion[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [editingVersion, setEditingVersion] = useState<string | null>(null)
  const [editorOpen, setEditorOpen] = useState(false)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [featuresText, setFeaturesText] = useState('')
  const [benefitsText, setBenefitsText] = useState('')
  const [applicationsText, setApplicationsText] = useState('')
  const [supportedMaterialsText, setSupportedMaterialsText] = useState('')
  const [specificationsText, setSpecificationsText] = useState('')
  const [customFieldsText, setCustomFieldsText] = useState('{}')

  async function loadVersions() {
    setLoading(true)
    setError('')
    try {
      const result = await getProductVersions(productId)
      setVersions(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load versions.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadVersions()
  }, [productId])

  function startNewDraft() {
    setEditingVersion(null)
    setName('')
    setDescription('')
    setFeaturesText('')
    setBenefitsText('')
    setApplicationsText('')
    setSupportedMaterialsText('')
    setSpecificationsText('')
    setCustomFieldsText('{}')
    setEditorOpen(true)
    setError('')
  }

  function startEditing(version: ProductVersion) {
    const snapshot = version.content_snapshot
    const standardFields = [
      'name', 'description', 'features', 'benefits',
      'applications', 'supported_materials', 'specifications',
    ]
    const customFields = Object.fromEntries(
      Object.entries(snapshot).filter(([key]) => !standardFields.includes(key)),
    )

    setEditingVersion(version.id)
    setName(typeof snapshot.name === 'string' ? snapshot.name : '')
    setDescription(typeof snapshot.description === 'string' ? snapshot.description : '')
    setFeaturesText(
      Array.isArray(snapshot.features)
        ? snapshot.features.map(String).join('\n')
        : '',
    )
    setBenefitsText(
      Array.isArray(snapshot.benefits)
        ? snapshot.benefits.map(String).join('\n')
        : '',
    )
    setApplicationsText(
      Array.isArray(snapshot.applications)
        ? snapshot.applications.map(String).join('\n')
        : '',
    )
    setSupportedMaterialsText(
      Array.isArray(snapshot.supported_materials)
        ? snapshot.supported_materials.map(String).join('\n')
        : '',
    )
    setSpecificationsText(
      snapshot.specifications &&
      typeof snapshot.specifications === 'object' &&
      !Array.isArray(snapshot.specifications)
        ? Object.entries(snapshot.specifications as Record<string, unknown>)
            .map(([key, value]) => `${key}=${String(value)}`)
            .join('\n')
        : '',
    )
    setCustomFieldsText(JSON.stringify(customFields, null, 2))
    setEditorOpen(true)
    setError('')
  }

  async function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')

    let customFields: Record<string, unknown>
    try {
      const parsed: unknown = JSON.parse(customFieldsText)
      if (
        parsed === null ||
        typeof parsed !== 'object' ||
        Array.isArray(parsed)
      ) {
        throw new Error('Custom fields must be a JSON object.')
      }
      customFields = parsed as Record<string, unknown>
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Invalid custom fields JSON.')
      return
    }

    const specifications: Record<string, string> = {}
    for (const line of specificationsText.split('\n')) {
      const trimmed = line.trim()
      if (!trimmed) continue
      const separator = trimmed.indexOf('=')
      if (separator <= 0) {
        setError(`Invalid specification: "${trimmed}". Use key=value.`)
        return
      }
      const key = trimmed.slice(0, separator).trim()
      const value = trimmed.slice(separator + 1).trim()
      if (!key) {
        setError('Specification keys cannot be empty.')
        return
      }
      specifications[key] = value
    }

    const parsedContent: Record<string, unknown> = {
      ...customFields,
      name: name.trim(),
      description: description.trim(),
      features: featuresText
        .split('\n')
        .map((feature) => feature.trim())
        .filter(Boolean),
      benefits: benefitsText
        .split('\n')
        .map((item) => item.trim())
        .filter(Boolean),
      applications: applicationsText
        .split('\n')
        .map((item) => item.trim())
        .filter(Boolean),
      supported_materials: supportedMaterialsText
        .split('\n')
        .map((item) => item.trim())
        .filter(Boolean),
      specifications,
    }

    setSaving(true)
    try {
      if (editingVersion) {
        await updateProductVersion(productId, editingVersion, parsedContent)
      } else {
        await createProductVersion(productId, parsedContent)
      }
      setEditingVersion(null)
      setEditorOpen(false)
      await loadVersions()
      await onVersionsChanged()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save version.')
    } finally {
      setSaving(false)
    }
  }

  async function handlePublish(versionId: string) {
    setSaving(true)
    setError('')
    try {
      await publishProductVersion(productId, versionId)
      await loadVersions()
      await onVersionsChanged()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not publish version.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="mt-6 border-t border-white/10 pt-5">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-white">Product versions</h3>
          <p className="mt-1 text-xs text-slate-400">
            Manage draft content and published snapshots.
          </p>
        </div>
        <button
          type="button"
          onClick={startNewDraft}
          disabled={productStatus === 'ARCHIVED' || saving}
          className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/[0.05] px-3 py-2 text-xs font-medium text-slate-200 transition hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <FilePlus2 size={14} />
          New draft
        </button>
      </div>

      {error && (
        <p className="mb-3 flex items-center gap-2 rounded-lg border border-rose-500/20 bg-rose-500/10 p-3 text-xs text-rose-300">
          <AlertCircle size={14} />
          {error}
        </p>
      )}

      {editorOpen ? (
        <form
          onSubmit={handleSave}
          className="mb-5 rounded-xl border border-white/10 bg-slate-950/50 p-4"
        >
          <div className="mb-3 flex items-center justify-between">
            <p className="text-xs font-semibold text-slate-200">
              {editingVersion ? 'Edit draft content' : 'Create draft content'}
            </p>
            <button
              type="button"
              onClick={() => {
                setEditingVersion(null)
                setEditorOpen(false)
                setError('')
              }}
              className="text-xs text-slate-400 hover:text-white"
            >
              Cancel
            </button>
          </div>
          <div className="space-y-4">
            <div>
              <label className="mb-1 block text-xs text-slate-400">Product name</label>
              <input
                value={name}
                onChange={(event) => setName(event.target.value)}
                className="w-full rounded-lg border border-white/10 bg-slate-900 px-3 py-2 text-sm text-slate-200 outline-none focus:border-indigo-400/50"
                placeholder="Product name"
              />
            </div>

            <div>
              <label className="mb-1 block text-xs text-slate-400">Description</label>
              <textarea
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                rows={3}
                className="w-full rounded-lg border border-white/10 bg-slate-900 p-3 text-sm text-slate-200 outline-none focus:border-indigo-400/50"
                placeholder="Describe the product"
              />
            </div>

            <div>
              <label className="mb-1 block text-xs text-slate-400">Features</label>
              <textarea
                value={featuresText}
                onChange={(event) => setFeaturesText(event.target.value)}
                rows={4}
                className="w-full rounded-lg border border-white/10 bg-slate-900 p-3 text-sm text-slate-200 outline-none focus:border-indigo-400/50"
                placeholder={'One feature per line\nDurable construction\nEnergy efficient'}
              />
              <p className="mt-1 text-[10px] text-slate-500">Enter one feature per line.</p>
            </div>

            <div>
              <label className="mb-1 block text-xs text-slate-400">Benefits</label>
              <textarea
                value={benefitsText}
                onChange={(event) => setBenefitsText(event.target.value)}
                rows={3}
                className="w-full rounded-lg border border-white/10 bg-slate-900 p-3 text-sm text-slate-200 outline-none focus:border-indigo-400/50"
                placeholder={'One benefit per line\nReduced operating costs\nFaster production'}
              />
            </div>

            <div>
              <label className="mb-1 block text-xs text-slate-400">Applications</label>
              <textarea
                value={applicationsText}
                onChange={(event) => setApplicationsText(event.target.value)}
                rows={3}
                className="w-full rounded-lg border border-white/10 bg-slate-900 p-3 text-sm text-slate-200 outline-none focus:border-indigo-400/50"
                placeholder={'One application per line\nLabel converting\nFlexible packaging'}
              />
            </div>

            <div>
              <label className="mb-1 block text-xs text-slate-400">Supported materials</label>
              <textarea
                value={supportedMaterialsText}
                onChange={(event) => setSupportedMaterialsText(event.target.value)}
                rows={3}
                className="w-full rounded-lg border border-white/10 bg-slate-900 p-3 text-sm text-slate-200 outline-none focus:border-indigo-400/50"
                placeholder={'One material per line\nPaper\nFilm\nFoil'}
              />
            </div>

            <div>
              <label className="mb-1 block text-xs text-slate-400">Specifications</label>
              <textarea
                value={specificationsText}
                onChange={(event) => setSpecificationsText(event.target.value)}
                rows={4}
                className="w-full rounded-lg border border-white/10 bg-slate-900 p-3 font-mono text-xs text-slate-200 outline-none focus:border-indigo-400/50"
                placeholder={'Material=Aluminium\nWeight=250g\nModel=AX-100'}
              />
              <p className="mt-1 text-[10px] text-slate-500">Enter one key=value pair per line.</p>
            </div>

            <details className="rounded-lg border border-white/10 p-3">
              <summary className="cursor-pointer text-xs font-medium text-slate-300">
                Custom fields (advanced)
              </summary>
              <textarea
                value={customFieldsText}
                onChange={(event) => setCustomFieldsText(event.target.value)}
                spellCheck={false}
                rows={5}
                className="mt-3 w-full rounded-lg border border-white/10 bg-slate-900 p-3 font-mono text-xs leading-5 text-slate-200 outline-none focus:border-indigo-400/50"
                placeholder={'{\n  "warranty": "2 years"\n}'}
              />
              <p className="mt-1 text-[10px] text-slate-500">
                Add valid JSON properties not covered by the standard fields.
              </p>
            </details>
          </div>
          <button
            type="submit"
            disabled={saving}
            className="mt-3 flex items-center gap-2 rounded-lg bg-indigo-500 px-4 py-2 text-xs font-semibold text-white transition hover:bg-indigo-400 disabled:opacity-50"
          >
            {saving ? <LoaderCircle size={14} className="animate-spin" /> : <Check size={14} />}
            Save draft
          </button>
        </form>
      ) : null}

      {loading ? (
        <div className="flex items-center gap-2 py-5 text-xs text-slate-400">
          <LoaderCircle size={15} className="animate-spin" />
          Loading versions...
        </div>
      ) : versions.length === 0 ? (
        <div className="rounded-xl border border-dashed border-white/10 px-4 py-6 text-center">
          <Clock size={20} className="mx-auto mb-2 text-slate-500" />
          <p className="text-xs text-slate-400">No versions created yet.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {versions.map((version) => (
            <div
              key={version.id}
              className="rounded-xl border border-white/10 bg-white/[0.02] p-3"
            >
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-slate-200">
                      Version {version.version_number}
                    </span>
                    <span
                      className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${
                        statusStyles[version.status] ?? statusStyles.RETIRED
                      }`}
                    >
                      {version.status}
                    </span>
                  </div>
                  <p className="mt-1 text-[11px] text-slate-500">
                    Created {new Date(version.created_at).toLocaleString()}
                    {version.published_at
                      ? ` · Published ${new Date(version.published_at).toLocaleString()}`
                      : ''}
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => onPreviewVersion(version)}
                    className="flex items-center gap-1 rounded-md px-2 py-1.5 text-xs text-blue-300 hover:bg-blue-500/10"
                  >
                    <Eye size={13} />
                    Preview
                  </button>
                  {version.status === 'DRAFT' && (
                    <>
                      <button
                        type="button"
                        onClick={() => startEditing(version)}
                        disabled={saving}
                        className="flex items-center gap-1 rounded-md px-2 py-1.5 text-xs text-slate-300 hover:bg-white/10"
                      >
                        <Pencil size={13} />
                        Edit
                      </button>
                      <button
                        type="button"
                        onClick={() => void handlePublish(version.id)}
                        disabled={saving}
                        className="flex items-center gap-1 rounded-md bg-emerald-500/10 px-2 py-1.5 text-xs text-emerald-300 hover:bg-emerald-500/20 disabled:opacity-50"
                      >
                        <Upload size={13} />
                        Publish
                      </button>
                    </>
                  )}
                </div>
              </div>
              <details className="mt-3">
                <summary className="cursor-pointer text-[11px] text-slate-500 hover:text-slate-300">
                  View content snapshot
                </summary>
                <VersionSnapshotView content={version.content_snapshot} />
              </details>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

export default ProductVersionsPanel
