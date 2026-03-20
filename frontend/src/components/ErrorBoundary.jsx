import React from 'react'
import '../styles/app.css'

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught:', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="app">
          <header className="app-header">
            <h1>JobFlow — Resume Tailoring</h1>
          </header>
          <div className="app-container">
            <div style={{ background: 'white', padding: '2rem', borderRadius: '12px', textAlign: 'center' }}>
              <h2>Oops! Something went wrong</h2>
              <p style={{ color: '#666', marginBottom: '1rem' }}>
                {this.state.error?.message || 'An unexpected error occurred'}
              </p>
              <button 
                onClick={() => this.setState({ hasError: false, error: null })}
                style={{
                  background: '#667eea',
                  color: 'white',
                  padding: '0.8rem 1.5rem',
                  border: 'none',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  fontSize: '1rem',
                }}
              >
                Try Again
              </button>
              <details style={{ marginTop: '2rem', textAlign: 'left', opacity: 0.7 }}>
                <summary>Error Details</summary>
                <pre style={{ background: '#f5f5f5', padding: '1rem', borderRadius: '4px', overflow: 'auto' }}>
                  {this.state.error?.stack}
                </pre>
              </details>
            </div>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}
