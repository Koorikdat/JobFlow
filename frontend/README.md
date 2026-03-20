# Frontend for JobFlow
React + Vite frontend for browsing jobs and generating tailored resumes.

## Getting Started

### Install dependencies
```bash
cd frontend
npm install
```

### Development
```bash
# Start backend API (from root directory)
source .venv/bin/activate
python backend.py

# In another terminal, start frontend dev server
cd frontend
npm run dev
```

Then open http://localhost:5173 in your browser.

The frontend will proxy `/api/*` requests to the backend at `http://localhost:8000`.

### Build for production
```bash
npm run build
```

## Features
- Browse jobs from jobflow.db
- Filter by keyword, company, and location
- Click a job to view details
- Customize job title and generate tailored resume
- Responsive design
