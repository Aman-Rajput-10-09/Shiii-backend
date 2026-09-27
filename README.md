# Shiii-backend

Shiii AI Diplomatic Couple Emissary Backend — built with FastAPI, PostgreSQL, and Google Gemini.

## Features
- **Couple Diplomacy & Mediation**: LLM-driven empathetic mediation between partners.
- **REST API**: Built with FastAPI and Pydantic v2.
- **Vercel Serverless Ready**: Native deployment support via `vercel.json` and `api/index.py`.

## Quick Start (Local)
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Copy environment variables:
   ```bash
   cp .env.example .env
   ```
3. Run the development server:
   ```bash
   python run_server.py
   ```

## Deploy on Vercel
1. Import this repository into Vercel.
2. Set Environment Variables:
   - `DATABASE_URL` (or attach Vercel Postgres / Neon / Supabase)
   - `SECRET_KEY`
   - `GEMINI_API_KEY`
3. Deploy!
