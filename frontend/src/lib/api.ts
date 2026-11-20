
const API_BASE = '/api/v1'
const TOKEN_KEY = 'qr_admin_access_token'

export interface AdminIdentity {
  id: string
  name: string
  email: string
  role: string
}

export interface AdminUser extends AdminIdentity {
  is_active: boolean
  last_login_at: string | null
  created_at: string
}

export interface PlatformSettings {
  public_base_url: string
}

export interface GlobalSearchResult {
  id: string
  kind: string
  title: string
  detail: string | null
  page: string
  target_key?: string | null
}

export interface LoginResponse {
  access_token: string
  token_type: string
  expires_in: number
  admin_id: string
  name: string
  email: string
  role: string
}

export interface DashboardOverview {
  products: {
    total: number
    active: number
    draft: number
    archived: number
  }
  qr_codes: {
    total: number
    active: number
    inactive: number
    revoked: number
    allocated: number
  }
  batches: {
    total: number
    generated: number
    pending: number
    failed: number
  }
  scans: {
    total: number
    pending: number
    allowed: number
    blocked: number
    error: number
  }
}

export interface ScanTrend {
  date: string
  total: number
  pending: number
  allowed: number
  blocked: number
  error: number
}

export interface ScanAnalytics {
  from_date: string
  to_date: string
  summary: { total: number; pending: number; allowed: number; blocked: number; error: number }
  location_analytics: LocationAnalytics
  daily: ScanTrend[]
  products: { product_id: string | null; name: string; sku: string | null; scans: number }[]
  regions: { region_id: string | null; name: string; region_code: string | null; scans: number }[]
  qr_codes: { qr_code_id: string; batch_code: string; token_suffix: string; scans: number }[]
}

export interface LocationAnalytics {
  location_statuses: Record<string, number>
  classifications: Record<string, number>
}

export interface RecentActivity {
  id: string
  admin_id: string | null
  action: string
  entity_type: string
  entity_id: string | null
  created_at: string
}

export type ProductStatus = 'DRAFT' | 'ACTIVE' | 'ARCHIVED'
export type VersionStatus = 'DRAFT' | 'PUBLISHED' | 'RETIRED'
export type MediaType = 'IMAGE' | 'VIDEO' | 'DOCUMENT'

export interface Product {
  id: string
  sku: string
  name: string
  category_id: string | null
  short_description: string | null
  status: ProductStatus
  created_at: string
  updated_at: string
}

export interface ProductCategory {
  id: string
  name: string
  description: string | null
  parent_id: string | null
  is_active: boolean
  created_at: string
}

export interface ProductVersion {
  id: string
  product_id: string
  version_number: number
  content_snapshot: Record<string, unknown>
  status: VersionStatus
  created_at: string
  published_at: string | null
}

export interface ProductMedia {
  id: string
  product_id: string
  version_id: string | null
  media_type: MediaType
  original_filename: string
  mime_type: string
  file_size_bytes: number
  checksum_sha256: string | null
  display_order: number
  alt_text: string | null
  created_at: string
}

export interface Region {
  id: string
  name: string
  region_code: string
  region_type: string
  parent_id: string | null
  is_active: boolean
  created_at: string
}

export function regionDisplayLabel(region: Region, regions: Region[]): string {
  const regionsById = new Map(regions.map((item) => [item.id, item]))
  const names: string[] = []
  const visited = new Set<string>()
  let current: Region | undefined = region
  while (current && !visited.has(current.id)) {
    visited.add(current.id)
    names.push(current.name)
    current = current.parent_id ? regionsById.get(current.parent_id) : undefined
  }
  return `${names.reverse().join(' / ')} · ${region.region_code}`
}

export interface RegionBoundaryGeometry {
  type: 'Polygon' | 'MultiPolygon'
  coordinates: unknown[]
}

export interface RegionBoundary {
  region_id: string
  geometry: RegionBoundaryGeometry | null
}

export type FormFieldType = 'TEXT' | 'EMAIL' | 'PHONE' | 'TEXTAREA' | 'SELECT' | 'CHECKBOX'

export interface FormFieldDefinition {
  key: string
  label: string
  type: FormFieldType
  required: boolean
  options?: string[]
  max_length?: number
}

export interface FormVersionRecord {
  id: string
  form_id: string
  version_number: number
  schema: { fields: FormFieldDefinition[] }
  published_at: string | null
  created_at: string
}

export interface FormRecord {
  id: string
  name: string
  description: string | null
  status: string
  created_at: string
}

export interface FormAssignmentRecord {
  id: string
  form_version_id: string
  scope_type: 'GLOBAL' | 'PRODUCT' | 'REGION'
  product_id: string | null
  region_id: string | null
  requirement: 'MANDATORY' | 'OPTIONAL' | 'DISABLED'
  is_active: boolean
  created_at: string
}

export interface FormSubmissionRecord {
  id: string
  scan_event_id: string
  submitted_at: string
  answers: Record<string, unknown>
}

export interface FormSubmissionPage {
  items: FormSubmissionRecord[]
  total: number
  offset: number
  limit: number
}

export interface QRBatch {
  id: string
  batch_code: string
  requested_product_id: string | null
  requested_region_id: string | null
  current_product_id: string | null
  current_region_id: string | null
  allocation_status: 'UNALLOCATED' | 'ALLOCATED' | 'MIXED' | 'NO_ACTIVE_CODES'
  active_code_count: number
  allocated_code_count: number
  quantity: number
  generation_status: string
  created_by: string | null
  created_at: string
  completed_at: string | null
  retired_at: string | null
}

export interface QRCode {
  id: string
  batch_id: string
  token: string
  status: string
  created_at: string
  scan_url: string
}

export interface QRAllocation {
  id: string
  qr_code_id: string
  product_id: string
  region_id: string
  assigned_by: string | null
  assigned_at: string
  ended_at: string | null
  reason: string | null
}

export interface LocationPolicy {
  id: string
  name: string
  requirement: 'MANDATORY' | 'SKIPPABLE'
  method: 'GPS_REQUIRED' | 'GPS_IP_FALLBACK' | 'IP_ONLY'
  is_active: boolean
  created_by: string | null
  created_at: string
  updated_at: string
}

export type LocationPolicyAssignment = {
  id: string
  policy_id: string
  scope_type: 'GLOBAL' | 'PRODUCT' | 'REGION'
  product_id: string | null
  region_id: string | null
  priority: number
  created_at: string
}

export interface AuditLog {
  id: string
  admin_id: string | null
  action: string
  entity_type: string
  entity_id: string | null
  old_values: Record<string, unknown> | null
  new_values: Record<string, unknown> | null
  ip_hash: string | null
  created_at: string
}

export interface AuditLogPage {
  items: AuditLog[]
  total: number
  offset: number
  limit: number
}

function getToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY)
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {},
): Promise<T> {
  const token = getToken()

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      ...(options.body instanceof FormData
        ? {}
        : { 'Content-Type': 'application/json' }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  })

  if (response.status === 401) {
    sessionStorage.removeItem(TOKEN_KEY)
  }

  if (!response.ok) {
    const body = await response.json().catch(() => null)
    const message =
      body?.detail ?? `Request failed with status ${response.status}`

    throw new Error(
      typeof message === 'string' ? message : JSON.stringify(message),
    )
  }

  return response.json() as Promise<T>
}

async function requestBlob(endpoint: string): Promise<Blob> {
  const token = getToken()
  const response = await fetch(`${API_BASE}${endpoint}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })

  if (response.status === 401) sessionStorage.removeItem(TOKEN_KEY)
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    const message = body?.detail ?? `Request failed with status ${response.status}`
    throw new Error(typeof message === 'string' ? message : JSON.stringify(message))
  }
  return response.blob()
}

export async function login(
  email: string,
  password: string,
): Promise<LoginResponse> {
  const result = await request<LoginResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })

  sessionStorage.setItem(TOKEN_KEY, result.access_token)
  return result
}

export function logout(): void {
  sessionStorage.removeItem(TOKEN_KEY)
}

export function hasSession(): boolean {
  return Boolean(getToken())
}

export function getCurrentAdmin(): Promise<AdminIdentity> {
  return request('/auth/me')
}

export function getAdminUsers(): Promise<AdminUser[]> {
  return request('/admin/users')
}

export function createAdminUser(data: { name: string; email: string; password: string }): Promise<AdminUser> {
  return request('/admin/users', { method: 'POST', body: JSON.stringify(data) })
}

export function setAdminUserActive(adminId: string, is_active: boolean): Promise<AdminUser> {
  return request(`/admin/users/${adminId}`, { method: 'PATCH', body: JSON.stringify({ is_active }) })
}

export function getPlatformSettings(): Promise<PlatformSettings> {
  return request('/settings')
}

export function searchPlatform(query: string): Promise<{ query: string; items: GlobalSearchResult[] }> {
  const params = new URLSearchParams({ q: query })
  return request(`/search?${params.toString()}`)
}

export function updatePlatformSettings(data: PlatformSettings): Promise<PlatformSettings> {
  return request('/settings', { method: 'PUT', body: JSON.stringify(data) })
}

export function getDashboardOverview(): Promise<DashboardOverview> {
  return request('/dashboard/overview')
}

export function getScanTrends(days = 7): Promise<ScanTrend[]> {
  return request(`/dashboard/scan-trends?days=${days}`)
}

export function getScanAnalytics(params: {
  from_date: string
  to_date: string
  product_id?: string
  qr_code_id?: string
  region_id?: string
  result_status?: string
  location_status?: string
}): Promise<ScanAnalytics> {
  const query = new URLSearchParams({ from_date: params.from_date, to_date: params.to_date })
  for (const key of ['product_id', 'qr_code_id', 'region_id', 'result_status', 'location_status'] as const) {
    if (params[key]) query.set(key, params[key]!)
  }
  return request(`/analytics/scans?${query.toString()}`)
}

export function getLocationAnalytics(): Promise<LocationAnalytics> {
  return request('/dashboard/location-analytics')
}

export function getRecentActivity(limit = 10): Promise<RecentActivity[]> {
  return request(`/dashboard/recent-activity?limit=${limit}`)
}

// Products

export function getProducts(params: {
  offset?: number
  limit?: number
  category_id?: string
  status?: ProductStatus
} = {}): Promise<Product[]> {
  const query = new URLSearchParams()
  query.set('offset', String(params.offset ?? 0))
  query.set('limit', String(params.limit ?? 50))
  if (params.category_id) query.set('category_id', params.category_id)
  if (params.status) query.set('status', params.status)
  return request(`/products?${query.toString()}`)
}

export async function getAllProducts(params: Omit<Parameters<typeof getProducts>[0], 'offset' | 'limit'> = {}): Promise<Product[]> {
  const pageSize = 100
  const products: Product[] = []
  for (let offset = 0; ; offset += pageSize) {
    const page = await getProducts({ ...params, offset, limit: pageSize })
    products.push(...page)
    if (page.length < pageSize) return products
  }
}

export function getProduct(productId: string): Promise<Product> {
  return request(`/products/${productId}`)
}

export function createProduct(data: {
  sku: string
  name: string
  category_id?: string | null
  short_description?: string | null
}): Promise<Product> {
  return request('/products', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export function updateProduct(
  productId: string,
  data: Partial<{
    sku: string
    name: string
    category_id: string | null
    short_description: string | null
  }>,
): Promise<Product> {
  return request(`/products/${productId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

export function archiveProduct(productId: string): Promise<Product> {
  return request(`/products/${productId}`, { method: 'DELETE' })
}

// Customer forms
export function getForms(): Promise<FormRecord[]> {
  return request('/forms')
}

export function createForm(data: {
  name: string
  description?: string | null
  schema: { fields: FormFieldDefinition[] }
}): Promise<{ form: FormRecord; version: FormVersionRecord }> {
  return request('/forms', { method: 'POST', body: JSON.stringify(data) })
}

export function getFormVersions(formId: string): Promise<FormVersionRecord[]> {
  return request(`/forms/${formId}/versions`)
}

export function createFormVersion(formId: string, schema: { fields: FormFieldDefinition[] }): Promise<FormVersionRecord> {
  return request(`/forms/${formId}/versions`, {
    method: 'POST',
    body: JSON.stringify({ schema }),
  })
}

export function publishFormVersion(formId: string, versionId: string): Promise<FormVersionRecord> {
  return request(`/forms/${formId}/versions/${versionId}/publish`, { method: 'POST' })
}

export function updateFormVersion(formId: string, versionId: string, schema: { fields: FormFieldDefinition[] }): Promise<FormVersionRecord> {
  return request(`/forms/${formId}/versions/${versionId}`, {
    method: 'PATCH',
    body: JSON.stringify({ schema }),
  })
}

export function getFormAssignments(): Promise<FormAssignmentRecord[]> {
  return request('/forms/assignments')
}

export function createFormAssignment(data: {
  form_version_id: string
  scope_type: FormAssignmentRecord['scope_type']
  product_id?: string | null
  region_id?: string | null
  requirement: FormAssignmentRecord['requirement']
}): Promise<FormAssignmentRecord> {
  return request('/forms/assignments', { method: 'POST', body: JSON.stringify(data) })
}

export function updateFormAssignment(assignmentId: string, data: {
  is_active?: boolean
  requirement?: FormAssignmentRecord['requirement']
}): Promise<FormAssignmentRecord> {
  return request(`/forms/assignments/${assignmentId}`, { method: 'PATCH', body: JSON.stringify(data) })
}

export function getFormSubmissions(
  formId: string,
  params: { offset?: number; limit?: number } = {},
): Promise<FormSubmissionPage> {
  const query = new URLSearchParams()
  if (params.offset !== undefined) query.set('offset', String(params.offset))
  if (params.limit !== undefined) query.set('limit', String(params.limit))
  const suffix = query.size ? `?${query.toString()}` : ''
  return request(`/forms/${formId}/submissions${suffix}`)
}

// Regions

export function getRegions(params: {
  offset?: number
  limit?: number
  is_active?: boolean
} = {}): Promise<Region[]> {
  const query = new URLSearchParams()
  query.set('offset', String(params.offset ?? 0))
  query.set('limit', String(params.limit ?? 100))
  if (params.is_active !== undefined) {
    query.set('is_active', String(params.is_active))
  }
  return request(`/regions?${query.toString()}`)
}

export async function getAllRegions(params: Omit<Parameters<typeof getRegions>[0], 'offset' | 'limit'> = {}): Promise<Region[]> {
  const pageSize = 100
  const regions: Region[] = []
  for (let offset = 0; ; offset += pageSize) {
    const page = await getRegions({ ...params, offset, limit: pageSize })
    regions.push(...page)
    if (page.length < pageSize) return regions
  }
}

export function getRegion(regionId: string): Promise<Region> {
  return request(`/regions/${regionId}`)
}

export function createRegion(data: {
  name: string
  region_code: string
  region_type: string
  parent_id?: string | null
}): Promise<Region> {
  return request('/regions', { method: 'POST', body: JSON.stringify(data) })
}

export function updateRegion(
  regionId: string,
  data: Partial<Pick<Region, 'name' | 'region_code' | 'region_type' | 'parent_id' | 'is_active'>>,
): Promise<Region> {
  return request(`/regions/${regionId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

export function deactivateRegion(regionId: string): Promise<Region> {
  return request(`/regions/${regionId}`, { method: 'DELETE' })
}

export function getRegionBoundary(regionId: string): Promise<RegionBoundary> {
  return request(`/regions/${regionId}/boundary`)
}

export function saveRegionBoundary(regionId: string, geometry: RegionBoundaryGeometry): Promise<RegionBoundary> {
  return request(`/regions/${regionId}/boundary`, {
    method: 'PUT',
    body: JSON.stringify({ geometry }),
  })
}

export function deleteRegionBoundary(regionId: string): Promise<{ deleted: boolean }> {
  return request(`/regions/${regionId}/boundary`, { method: 'DELETE' })
}

// QR batches

export function getQRBatches(params: {
  offset?: number
  limit?: number
} = {}): Promise<QRBatch[]> {
  const query = new URLSearchParams({
    offset: String(params.offset ?? 0),
    limit: String(params.limit ?? 50),
  })
  return request(`/qr/batches?${query.toString()}`)
}

export async function getAllQRBatches(): Promise<QRBatch[]> {
  const pageSize = 100
  const batches: QRBatch[] = []
  for (let offset = 0; ; offset += pageSize) {
    const page = await getQRBatches({ offset, limit: pageSize })
    batches.push(...page)
    if (page.length < pageSize) return batches
  }
}

export function getQRBatch(batchId: string): Promise<QRBatch> {
  return request(`/qr/batches/${batchId}`)
}

export function retireQRBatch(batchId: string): Promise<{
  batch_id: string
  batch_code: string
  revoked_count: number
  retired_at: string
}> {
  return request(`/qr/batches/${batchId}/retire`, { method: 'POST' })
}

export function allocateQRBatch(
  batchId: string,
  data: { product_id: string; region_id: string; reason?: string | null },
): Promise<{
  batch_id: string
  batch_code: string
  active_code_count: number
  allocated_count: number
  reassigned_count: number
  unchanged_count: number
}> {
  return request(`/qr/batches/${batchId}/allocation`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export function createQRBatch(data: {
  quantity: number
  batch_code?: string
  requested_product_id?: string | null
  requested_region_id?: string | null
}): Promise<QRBatch> {
  return request('/qr/batches', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export function exportQRBatchForSharing(batchId: string, format: 'svg-zip' | 'pdf' | 'png-zip'): Promise<Blob> {
  return requestBlob(`/qr/batches/${batchId}/share?format=${format}`)
}

export function getQRBatchCodes(params: {
  batchId: string
  offset?: number
  limit?: number
}): Promise<QRCode[]> {
  const query = new URLSearchParams({
    offset: String(params.offset ?? 0),
    limit: String(params.limit ?? 100),
  })
  return request(`/qr/batches/${params.batchId}/codes?${query.toString()}`)
}

export function getQRCode(qrCodeId: string): Promise<QRCode> {
  return request(`/qr/codes/${qrCodeId}`)
}

export function getQRCodeImage(
  qrCodeId: string,
  format: 'png' | 'svg' = 'png',
): Promise<Blob> {
  const query = new URLSearchParams({ format })
  return requestBlob(`/qr/codes/${qrCodeId}/image?${query.toString()}`)
}

export function getActiveQRAllocation(qrCodeId: string): Promise<QRAllocation | null> {
  return request(`/qr/codes/${qrCodeId}/allocation`)
}

export function getQRAllocationHistory(qrCodeId: string): Promise<QRAllocation[]> {
  return request(`/qr/codes/${qrCodeId}/allocation/history?offset=0&limit=100`)
}

export function allocateQRCodes(data: {
  qr_code_ids: string[]
  product_id: string
  region_id: string
  reason?: string | null
}): Promise<QRAllocation[]> {
  return request('/qr/allocations', { method: 'POST', body: JSON.stringify(data) })
}

export function reassignQRCode(
  qrCodeId: string,
  data: { product_id: string; region_id: string; reason?: string | null },
): Promise<QRAllocation> {
  return request(`/qr/codes/${qrCodeId}/allocation`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export async function getLocationPolicies(params: { is_active?: boolean } = {}): Promise<LocationPolicy[]> {
  const pageSize = 100
  const policies: LocationPolicy[] = []
  for (let offset = 0; ; offset += pageSize) {
    const query = new URLSearchParams({ offset: String(offset), limit: String(pageSize) })
    if (params.is_active !== undefined) query.set('is_active', String(params.is_active))
    const page: LocationPolicy[] = await request(`/location-policies?${query.toString()}`)
    policies.push(...page)
    if (page.length < pageSize) return policies
  }
}

export function getLocationPolicy(policyId: string): Promise<LocationPolicy> {
  return request(`/location-policies/${policyId}`)
}

export function createLocationPolicy(data: Pick<LocationPolicy, 'name' | 'requirement' | 'method'>): Promise<LocationPolicy> {
  return request('/location-policies', { method: 'POST', body: JSON.stringify(data) })
}

export function updateLocationPolicy(policyId: string, data: Partial<Pick<LocationPolicy, 'name' | 'requirement' | 'method' | 'is_active'>>): Promise<LocationPolicy> {
  return request(`/location-policies/${policyId}`, { method: 'PATCH', body: JSON.stringify(data) })
}

export function deactivateLocationPolicy(policyId: string): Promise<LocationPolicy> {
  return request(`/location-policies/${policyId}`, { method: 'DELETE' })
}

export function permanentlyDeleteLocationPolicy(policyId: string): Promise<{ deleted: boolean }> {
  return request(`/location-policies/${policyId}/permanent`, { method: 'DELETE' })
}

export async function getLocationPolicyAssignments(policyId: string): Promise<LocationPolicyAssignment[]> {
  const pageSize = 100
  const assignments: LocationPolicyAssignment[] = []
  for (let offset = 0; ; offset += pageSize) {
    const query = new URLSearchParams({ policy_id: policyId, offset: String(offset), limit: String(pageSize) })
    const page: LocationPolicyAssignment[] = await request(`/location-policy-assignments?${query.toString()}`)
    assignments.push(...page)
    if (page.length < pageSize) return assignments
  }
}

export function createLocationPolicyAssignment(data: {
  policy_id: string
  scope_type: LocationPolicyAssignment['scope_type']
  product_id?: string | null
  region_id?: string | null
  priority?: number
}): Promise<LocationPolicyAssignment> {
  return request('/location-policy-assignments', { method: 'POST', body: JSON.stringify(data) })
}

export function deleteLocationPolicyAssignment(assignmentId: string): Promise<void> {
  return request(`/location-policy-assignments/${assignmentId}`, { method: 'DELETE' })
}

export function getAuditLogs(params: {
  offset?: number
  limit?: number
  action?: string
  entity_type?: string
  entity_id?: string
  admin_id?: string
  created_from?: string
  created_to?: string
} = {}): Promise<AuditLogPage> {
  const query = new URLSearchParams({
    offset: String(params.offset ?? 0),
    limit: String(params.limit ?? 50),
  })
  for (const key of ['action', 'entity_type', 'entity_id', 'admin_id', 'created_from', 'created_to'] as const) {
    if (params[key]) query.set(key, params[key]!)
  }
  return request(`/audit-logs?${query.toString()}`)
}

export function getAuditLog(auditLogId: string): Promise<AuditLog> {
  return request(`/audit-logs/${auditLogId}`)
}

// Categories

export function getCategories(
  activeOnly: boolean | null = true,
  offset = 0,
  limit = 100,
): Promise<ProductCategory[]> {
  const query = new URLSearchParams({ offset: String(offset), limit: String(limit) })
  if (activeOnly !== null) query.set('is_active', String(activeOnly))
  return request(`/categories?${query.toString()}`)
}

export async function getAllCategories(
  activeOnly: boolean | null = true,
): Promise<ProductCategory[]> {
  const pageSize = 100
  const categories: ProductCategory[] = []
  for (let offset = 0; ; offset += pageSize) {
    const page = await getCategories(activeOnly, offset, pageSize)
    categories.push(...page)
    if (page.length < pageSize) return categories
  }
}

export function createCategory(data: {
  name: string
  description?: string | null
  parent_id?: string | null
}): Promise<ProductCategory> {
  return request('/categories', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export function updateCategory(
  categoryId: string,
  data: Partial<{
    name: string
    description: string | null
    parent_id: string | null
    is_active: boolean
  }>,
): Promise<ProductCategory> {
  return request(`/categories/${categoryId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

export function deactivateCategory(
  categoryId: string,
): Promise<ProductCategory> {
  return request(`/categories/${categoryId}`, { method: 'DELETE' })
}

// Product versions

export function getProductVersions(
  productId: string,
): Promise<ProductVersion[]> {
  return request(`/products/${productId}/versions`)
}

export function createProductVersion(
  productId: string,
  content_snapshot: Record<string, unknown>,
): Promise<ProductVersion> {
  return request(`/products/${productId}/versions`, {
    method: 'POST',
    body: JSON.stringify({ content_snapshot }),
  })
}

export function updateProductVersion(
  productId: string,
  versionId: string,
  content_snapshot: Record<string, unknown>,
): Promise<ProductVersion> {
  return request(`/products/${productId}/versions/${versionId}`, {
    method: 'PATCH',
    body: JSON.stringify({ content_snapshot }),
  })
}

export function publishProductVersion(
  productId: string,
  versionId: string,
): Promise<ProductVersion> {
  return request(
    `/products/${productId}/versions/${versionId}/publish`,
    { method: 'POST' },
  )
}

// Product media

export function getProductMedia(
  productId: string,
  versionId?: string,
): Promise<ProductMedia[]> {
  const query = versionId
    ? `?version_id=${encodeURIComponent(versionId)}`
    : ''
  return request(`/products/${productId}/media${query}`)
}

export function uploadProductMedia(
  productId: string,
  file: File,
  mediaType: MediaType,
  options: {
    version_id?: string
    display_order?: number
    alt_text?: string
  } = {},
): Promise<ProductMedia> {
  const form = new FormData()
  form.append('file', file)
  form.append('media_type', mediaType)
  if (options.version_id) form.append('version_id', options.version_id)
  form.append('display_order', String(options.display_order ?? 0))
  if (options.alt_text) form.append('alt_text', options.alt_text)

  return request(`/products/${productId}/media`, {
    method: 'POST',
    body: form,
  })
}

export function deleteProductMedia(
  productId: string,
  mediaId: string,
): Promise<ProductMedia> {
  return request(`/products/${productId}/media/${mediaId}`, {
    method: 'DELETE',
  })
}

export async function getProductMediaFile(
  productId: string,
  mediaId: string,
): Promise<Blob> {
  const token = getToken()
  const response = await fetch(
    `${API_BASE}/products/${productId}/media/${mediaId}/file`,
    {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    },
  )

  if (response.status === 401) {
    sessionStorage.removeItem(TOKEN_KEY)
  }

  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new Error(body?.detail ?? `Media download failed (${response.status})`)
  }

  return response.blob()
}

export interface ApiHealth {
  status: string
  application: string
}

export interface ReadinessHealth {
  status: string
  database: string
  schema: string
  postgis: string
}

async function healthRequest<T>(endpoint: string): Promise<T> {
  const response = await fetch(endpoint)

  if (!response.ok) {
    throw new Error(`Health check failed (${response.status})`)
  }

  return response.json() as Promise<T>
}

export function getApiHealth(): Promise<ApiHealth> {
  return healthRequest('/health')
}

export function getReadinessHealth(): Promise<ReadinessHealth> {
  return healthRequest('/ready')
}
