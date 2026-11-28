# Smartventory Frontend

React + Vite frontend for the Smartventory inventory intelligence application.

## Requirements

- **Node.js**: 18 or later (tested on v24)
- **npm**: 9 or later
- **Backend**: Flask server (`python backend/app.py`) must be running for real data

## Quick start

```bash
# 1. Install backend dependencies (from project root)
pip install -r backend/requirements.txt

# 2. Start the Flask backend
python backend/app.py
# → http://127.0.0.1:5000  (keep this running)

# 3. Install frontend dependencies
cd frontend
npm install

# 4. Start the Vite dev server
npm run dev
# → http://localhost:3000
```

The Vite dev server proxies all `/api/*` requests to `http://127.0.0.1:5000`.

## Production build

```bash
cd frontend
npm run build
# Output: frontend/dist/
```

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `VITE_API_BASE_URL` | `""` (same origin) | Override the Flask backend URL |

Create `.env` in `frontend/`:

```env
VITE_API_BASE_URL=http://127.0.0.1:5000
```

## CSV upload

Required columns: `Date`, `Product ID`, `Demand`.  
Optional columns: `Store ID`, `Category`, `Inventory Level`, `Units Sold`, `Unit Cost`.

A sample CSV is at the project root: `dummy_kirana_test_data.csv`.

## Pages & API endpoints

| Page | Route | Backend endpoint |
|---|---|---|
| Upload | (initial screen) | `POST /api/analyze` |
| Home | `/home` | — |
| Future Sales | `/future-sales` | `POST /api/forecast` |
| My Stock | `/my-stock` | — |
| What to Order | `/what-to-order` | `POST /api/recommendations` |
| Settings | `/settings` | `POST /api/recommendations` (on policy change) |

## Known limitations

- CSV-based, no live stock sync
- Session-based in-memory backend (restarting Flask clears sessions)
- No authentication — do not expose Flask publicly
- Plotly loaded via CDN (requires internet in dev)

## Project structure

```
frontend/
├── src/
│   ├── components/common/   # Badges, StatCard, States, PlotlyChart
│   ├── components/layout/   # AppLayout, Sidebar, MobileHeader
│   ├── components/upload/   # FileUpload dropzone
│   ├── components/Icons.jsx
│   ├── pages/               # Home, FutureSales, MyStock, WhatToOrder, Settings
│   ├── services/api.js      # All Flask HTTP calls (centralised)
│   ├── utils/format.js      # Formatting + per-product analytics
│   ├── styles/              # variables.css, global.css, components.css
│   ├── App.jsx
│   └── main.jsx
├── index.html
├── vite.config.js
└── package.json
```
