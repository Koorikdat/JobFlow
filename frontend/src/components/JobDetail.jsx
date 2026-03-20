import React, { useState } from 'react'
import { tailorResume } from '../api'
import '../styles/job-detail.css'

export default function JobDetail({ job, onBack, onResumeGenerated }) {
  const [isGenerating, setIsGenerating] = useState(false)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(null)
  const [role, setRole] = useState(job.title)

  const handleGenerateResume = async () => {
    setIsGenerating(true)
    setError(null)
    setSuccess(null)

    try {
      const result = await tailorResume(job.url, job.company, role)
      setSuccess(`Resume generated: ${result.pdf}`)
      onResumeGenerated()
    } catch (err) {
      setError(err.message)
    } finally {
      setIsGenerating(false)
    }
  }

  return (
    <div className="job-detail-container">
      <button className="back-btn" onClick={onBack}>
        ← Back to Jobs
      </button>

      <div className="job-detail-content">
        <div className="job-header">
          <h1>{job.title || 'Job Title'}</h1>
          <h2>{job.company || 'Company'}</h2>
          <p className="location">{job.location || 'Location not specified'}</p>
          <p className="date">
            Posted: {job.date_posted ? (() => { const d = new Date(job.date_posted); return isNaN(d.getTime()) ? 'Date not specified' : d.toLocaleDateString(); })() : 'Date not specified'}
          </p>
          {job.apply_url && (
            <a href={job.apply_url} target="_blank" rel="noopener noreferrer" className="apply-link">
              Apply Directly →
            </a>
          )}
        </div>

        <div className="job-body">
          <h3>Job Description</h3>
          <div className="description">
            {(job.description || 'No description available').split('\n').map((line, i) => (
              <p key={i}>{line}</p>
            ))}
          </div>
        </div>
      </div>

      <div className="resume-tailor-panel">
        <h3>Generate Tailored Resume</h3>
        <p>Customize the job title for your tailored resume:</p>

        <div className="tailor-form">
          <div className="form-group">
            <label htmlFor="role">Job Title for Resume</label>
            <input
              id="role"
              type="text"
              value={role}
              onChange={(e) => setRole(e.target.value)}
              placeholder="e.g., Senior Backend Engineer"
              className="role-input"
            />
          </div>

          {error && <div className="error-message">{error}</div>}
          {success && <div className="success-message">{success}</div>}

          <button
            onClick={handleGenerateResume}
            disabled={isGenerating}
            className="generate-btn"
          >
            {isGenerating ? 'Generating...' : 'Generate Tailored Resume'}
          </button>
        </div>
      </div>
    </div>
  )
}
