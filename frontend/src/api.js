// API helper functions
// Use relative paths so Vite proxy can intercept and forward to backend
const API_BASE = '/api'

export async function fetchJobs(keyword = '', company = '', location = '', page = 1, pageSize = 20) {
  const params = new URLSearchParams({
    page,
    page_size: pageSize,
  })
  
  if (keyword) params.append('keyword', keyword)
  if (company) params.append('company', company)
  if (location) params.append('location', location)

  const response = await fetch(`${API_BASE}/jobs?${params}`)
  if (!response.ok) throw new Error('Failed to fetch jobs')
  return response.json()
}

export async function fetchJobDetail(jobUrl) {
  // URL-encode the job URL for safe transmission
  const encodedUrl = encodeURIComponent(jobUrl)
  const response = await fetch(`${API_BASE}/jobs/${encodedUrl}`)
  if (!response.ok) throw new Error('Failed to fetch job detail')
  return response.json()
}

export async function fetchCompanies() {
  try {
    const response = await fetch(`${API_BASE}/jobs/filters/companies`)
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    return response.json()
  } catch (err) {
    console.error('Failed to fetch companies:', err)
    return { companies: [] }
  }
}

export async function fetchLocations() {
  try {
    const response = await fetch(`${API_BASE}/jobs/filters/locations`)
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    return response.json()
  } catch (err) {
    console.error('Failed to fetch locations:', err)
    return { locations: [] }
  }
}

export async function tailorResume(jobUrl, company, role) {
  const response = await fetch(`${API_BASE}/tailor`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      job_url: jobUrl,
      company,
      role,
      input_file: 'input.txt',
      config_file: 'config/default.yaml',
    }),
  })
  if (!response.ok) throw new Error('Failed to tailor resume')
  return response.json()
}

export async function runIngest() {
  const response = await fetch(`${API_BASE}/admin/ingest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  })
  if (!response.ok) throw new Error('Failed to run ingestion')
  return response.json()
}
