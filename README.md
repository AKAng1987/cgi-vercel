# CGI Dashboard (Vercel + Render)

A two-part deployment of the CGI (Compass Grid Identifier) macro-regime
dashboard: a Next.js frontend on Vercel talking server-side to a Python
FastAPI backend on Render, authenticated with a shared bearer token.

## Repo structure

```
cgi-vercel/
  api/          FastAPI app, deployed to Render
    main.py
    requirements.txt
    render.yaml
  web/          Next.js 15 app, deployed to Vercel
    app/
    lib/
```

The frontend never talks to the API from the browser — `lib/api.ts` runs
only in Next.js Server Components, so `API_TOKEN` never reaches the client.

## Deployment

### Render (api/)

1. Create a new Blueprint (or Web Service) on Render, connect this repo.
2. If using the Blueprint, Render will read `api/render.yaml` automatically.
   Otherwise, set manually: build command `pip install -r requirements.txt`,
   start command `uvicorn main:app --host 0.0.0.0 --port $PORT`, root
   directory `api/`.
3. In the Render dashboard, set the `API_TOKEN` environment variable (the
   value generated during scaffolding — see your terminal output / local
   `.env`).
4. Deploy. Note the resulting `https://<your-service>.onrender.com` URL.

### Vercel (web/)

1. Import this repo into Vercel.
2. Set **Root Directory** to `web/`.
3. Set environment variables:
   - `API_URL` = the Render URL from above
   - `API_TOKEN` = the same token you set in Render
4. Deploy. Visit the resulting Vercel URL.

Expected result: the page shows **CGI Dashboard** with a green
**API status: OK · CGI API v0.1.0** card.

## Local development

**API:**
```bash
cd api
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
API_TOKEN=<your-token> uvicorn main:app --reload
```

**Web:**
```bash
cd web
npm install
cp .env.example .env.local   # fill in API_URL / API_TOKEN
npm run dev
```
