# Photo Restoration Frontend

The frontend is a React single-page application built with Vite. It provides
the project pages and an editor for uploading a photograph, previewing the
original and restored images, choosing optional noise removal, and downloading
the result.

## Requirements

- Node.js
- npm
- The FastAPI backend running at `http://127.0.0.1:8000` for image processing

## Install and run

From this directory:

```bash
npm install
npm run dev
```

Open the local Vite development URL printed in the terminal, usually
`http://localhost:5173`.

## Available scripts

```bash
npm run dev      # Start Vite in development mode
npm run build    # Create the production build in dist/
npm run preview  # Preview the production build locally
npm run lint     # Run ESLint
```

## Backend connection

The image editor sends a `multipart/form-data` request to
`POST http://127.0.0.1:8000/restore`. It submits the selected file in the
`file` field and the noise-removal checkbox in the `denoise` boolean field. It
sends `true` when checked and `false` when unchecked. The
backend returns a PNG image, which the editor displays and makes available for
download.

The API base URL is currently defined as `API_URL` in
`src/components/Editor.jsx`; it is not read from a Vite environment variable.
If you change the backend address, update that constant and the allowed CORS
origins in `Backend/main.py` to include the frontend's origin.

Supported upload types are JPEG, PNG, and WebP. Noise removal is off by
default. Keep the backend running in a separate terminal while using the
editor.
