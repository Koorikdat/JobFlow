import React, { useState, useEffect } from 'react'
import { fetchJobs, fetchCompanies, fetchLocations } from '../api'
import '../styles/job-list.css'

export default function JobList({ onJobSelect, refreshKey }) {
  const [jobs, setJobs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [pageSize] = useState(20)

  // Filters
  const [keyword, setKeyword] = useState('')
  const [company, setCompany] = useState('')
  const [location, setLocation] = useState('')
  const [companies, setCompanies] = useState([])
  const [locations, setLocations] = useState([])

  // Debug logging
  React.useEffect(() => {
    console.log('JobList mounted/updated', {
      jobsCount: jobs.length,
      loading,
      error,
      companiesCount: companies.length,
      locationsCount: locations.length,
    })
  }, [jobs, loading, error, companies, locations])

  // Load filter options
  useEffect(() => {
    async function loadFilters() {
      try {
        const [compRes, locRes] = await Promise.all([
          fetchCompanies(),
          fetchLocations(),
        ])
        setCompanies(compRes.companies || [])
        setLocations(locRes.locations || [])
      } catch (err) {
        console.error('Failed to load filters:', err)
        // Don't crash - just proceed without filters loaded yet
        setCompanies([])
        setLocations([])
      }
    }
    loadFilters()
  }, [])

  // Load jobs
  useEffect(() => {
    async function loadJobs() {
      setLoading(true)
      setError(null)
      try {
        const data = await fetchJobs(keyword, company, location, page, pageSize)
        setJobs(data.jobs)
        setTotal(data.total)
      } catch (err) {
        setError(err.message)
      } finally {
        setLoading(false)
      }
    }
    loadJobs()
  }, [keyword, company, location, page, refreshKey])

  const handleReset = () => {
    setKeyword('')
    setCompany('')
    setLocation('')
    setPage(1)
  }

  const totalPages = Math.ceil(total / pageSize)

  return (
    <div className="job-list-container">
      <div className="filters">
        <div className="filter-group">
          <label htmlFor="keyword">Search</label>
          <input
            id="keyword"
            type="text"
            placeholder="Search by title or keywords..."
            value={keyword}
            onChange={(e) => {
              setKeyword(e.target.value)
              setPage(1)
            }}
            className="filter-input"
          />
        </div>

        <div className="filter-group">
          <label htmlFor="company">Company</label>
          <select
            id="company"
            value={company}
            onChange={(e) => {
              setCompany(e.target.value)
              setPage(1)
            }}
            className="filter-select"
          >
            <option value="">All companies</option>
            {companies.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>

        <div className="filter-group">
          <label htmlFor="location">Location</label>
          <select
            id="location"
            value={location}
            onChange={(e) => {
              setLocation(e.target.value)
              setPage(1)
            }}
            className="filter-select"
          >
            <option value="">All locations</option>
            {locations.map((l) => (
              <option key={l} value={l}>
                {l}
              </option>
            ))}
          </select>
        </div>

        <button onClick={handleReset} className="filter-reset">
          Reset Filters
        </button>
      </div>

      {error && <div className="error-message">Error: {error}</div>}

      {loading ? (
        <div className="loading">Loading jobs...</div>
      ) : (
        <>
          <div className="jobs-count">
            Showing {jobs.length} of {total} jobs
          </div>

          <div className="jobs-list">
            {jobs.length === 0 ? (
              <div className="no-jobs">No jobs found. Try adjusting your filters.</div>
            ) : (
              jobs.map((job) => (
                <div
                  key={job.id}
                  className="job-card"
                  onClick={() => onJobSelect(job)}
                >
                  <h3 className="job-title">{job.title || 'Untitled Position'}</h3>
                  <p className="job-company">{job.company || 'Unknown Company'}</p>
                  <p className="job-location">{job.location || 'Location not specified'}</p>
                  <p className="job-date">
                    Posted: {job.date_posted ? (() => { const d = new Date(job.date_posted); return isNaN(d.getTime()) ? 'Date not specified' : d.toLocaleDateString(); })() : 'Date not specified'}
                  </p>
                  <p className="job-description">
                    {(job.description || 'No description available').substring(0, 150)}...
                  </p>
                  <button className="view-btn">View & Tailor Resume</button>
                </div>
              ))
            )}
          </div>

          {totalPages > 1 && (
            <div className="pagination">
              <button
                onClick={() => setPage(Math.max(1, page - 1))}
                disabled={page === 1}
              >
                Previous
              </button>
              <span>
                Page {page} of {totalPages}
              </span>
              <button
                onClick={() => setPage(Math.min(totalPages, page + 1))}
                disabled={page === totalPages}
              >
                Next
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
