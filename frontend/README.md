# Frontend for JobFlow

React + Vite frontend for browsing jobs and generating tailored resumes.

## Getting Started

### Install frontend dependencies

```bash
cd frontend
npm install
```

### Development

Start the backend API server (from root directory):
```bash
source .venv/bin/activate
python backend.py
```

In another terminal, start the frontend dev server:
```bash
cd frontend
npm run dev
```

Then open **http://localhost:5173** in your browser.

The frontend will proxy `/api/*` requests to the backend at `http://localhost:8000`.

### Build for production

```bash
npm run build
```

The production build will be in `frontend/dist/`.

### Project structure

- `index.html` - Single-page application entry point
- `src/main.jsx` - React app initialization
- `src/App.jsx` - Main application component
- `src/api.js` - API client for backend communication
- `src/components/` - Reusable React components
  - `JobList.jsx` - Job listings display
  - `JobDetail.jsx` - Individual job detail view
  - `ErrorBoundary.jsx` - Error handling component
- `src/styles/` - CSS modules for components
- `vite.config.js` - Vite configuration

## Features
- Browse jobs from jobflow.db
- Filter by keyword, company, and location
- Click a job to view details
- Customize job title and generate tailored resume
- Responsive design
