import React, { useState } from 'react'
import JobList from './components/JobList'
import JobDetail from './components/JobDetail'
import ErrorBoundary from './components/ErrorBoundary'
import { runIngest } from './api'
import './styles/app.css'

export default function App() {
  const [selectedJob, setSelectedJob] = useState(null)
  const [refreshKey, setRefreshKey] = useState(0)
  const [ingestLoading, setIngestLoading] = useState(false)
  const [ingestStatus, setIngestStatus] = useState('')

  const handleJobSelect = (job) => {
    setSelectedJob(job)
  }

  const handleBack = () => {
    setSelectedJob(null)
  }

  const handleResumeGenerated = () => {
    // Show success feedback (without blocking alert)
    setTimeout(() => {
      handleBack()
    }, 1000)
  }

  const handleRunIngest = async () => {
    setIngestLoading(true)
    setIngestStatus('Ingesting jobs...')
    try {
      const result = await runIngest()
      setIngestStatus(`✓ Ingestion complete. ${result.message}`)
      // Refresh job list
      setTimeout(() => {
        setRefreshKey(k => k + 1)
        setIngestStatus('')
      }, 2000)
    } catch (error) {
      setIngestStatus(`✗ Error: ${error.message}`)
      setTimeout(() => setIngestStatus(''), 5000)
    } finally {
      setIngestLoading(false)
    }
  }

  return (
    <ErrorBoundary>
      <div className="app">
        <header className="app-header">
          <div className="header-content">
            <div>
              <h1>JobFlow — Resume Tailoring</h1>
              <p>Browse jobs and generate tailored resumes</p>
            </div>
            <div className="header-actions">
              <button 
                onClick={handleRunIngest}
                disabled={ingestLoading}
                className="ingest-btn"
                title="Fetch latest jobs from all sources"
              >
                {ingestLoading ? '⏳ Ingesting...' : '🔄 Refresh Jobs'}
              </button>
              {ingestStatus && <span className="ingest-status">{ingestStatus}</span>}
            </div>
          </div>
        </header>

        <div className="app-container">
          {selectedJob ? (
            <JobDetail job={selectedJob} onBack={handleBack} onResumeGenerated={handleResumeGenerated} />
          ) : (
            <JobList onJobSelect={handleJobSelect} refreshKey={refreshKey} />
          )}
        </div>
      </div>
    </ErrorBoundary>
  )
}
