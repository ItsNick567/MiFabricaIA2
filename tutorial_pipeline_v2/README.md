# Tutorial Pipeline v2

Pipeline para generar y publicar tutoriales de forma autonoma.

## Que hace ahora

- Hace scraping diario de tendencias desde Dev.to, Hashnode, GitHub y Reddit.
- Genera tutoriales en **ingles obligatorio** (con validacion y traduccion de respaldo).
- Publica en plataformas con API activa: Dev.to, Hashnode, Telegram y Blogger.
- Selecciona temas automaticamente desde datos reales de tendencia.
- Permite ejecucion 24/7 con scheduler.

## Requisitos

- Python 3.10+
- Dependencias de `requirements.txt`
- Al menos un motor LLM configurado:
  - Groq (`GROQ_API_KEY`) o
  - Ollama local (`LOCAL_LLM_BASE_URL` + `LOCAL_LLM_MODEL`) o
  - Gemini (`GOOGLE_API_KEY`) como fallback

## Instalacion

```bash
cd tutorial_pipeline_v2
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
```

## Configuracion

Copia `.env.example` a `.env` y completa tus credenciales.

Variables minimas recomendadas:

- `GROQ_API_KEY` o motor local de Ollama
- `DEVTO_API_KEY`
- `HASHNODE_API_KEY`
- `HASHNODE_PUBLICATION_ID`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHANNEL_ID`
- `BLOGGER_ACCESS_TOKEN`
- `BLOGGER_REFRESH_TOKEN`
- `BLOGGER_BLOG_ID`
- `FORCE_ENGLISH=true`
- `BUSINESS_CONTACT_EMAIL` (para sponsorship/contacto)

## APIs y setup

### Dev.to

- Docs: https://developers.forem.com/api
- API key: `https://dev.to/settings/extensions`
- Env: `DEVTO_API_KEY`

### Hashnode

- Endpoint GraphQL: `https://gql.hashnode.com`
- API key: `https://hashnode.com/settings/developer`
- Necesitas tu publication id (blog principal)
- Env: `HASHNODE_API_KEY`, `HASHNODE_PUBLICATION_ID`

### Telegram Bot API

- Docs: https://core.telegram.org/bots/api
- Crea bot con `@BotFather`
- Env: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL_ID`

### Blogger API v3

- Docs: https://developers.google.com/blogger/docs/3.0/using
- Crea OAuth token y blog id en Google Cloud
- Env: `BLOGGER_ACCESS_TOKEN`, `BLOGGER_REFRESH_TOKEN`, `BLOGGER_CLIENT_ID`, `BLOGGER_CLIENT_SECRET`, `BLOGGER_BLOG_ID`

### AdSense CMP (Blogger)

Si te aparece la pantalla de consentimiento CMP:

- Recomendado: la opcion de **3 botones** (`Consentir`, `No consentir`, `Administrar opciones`).
- Despues haz clic en `Enviar`.
- Esto ayuda a cumplimiento en EEE/Reino Unido/Suiza.

## Ejecucion manual (UI)

```bash
streamlit run app.py
```

## Ejecucion autonoma (24/7)

Windows:

```bat
run_autonomous.bat
```

Linux/Mac:

```bash
chmod +x run_autonomous.sh
./run_autonomous.sh
```

Sponsor hunter (separado del pipeline de tutoriales):

```bat
C:\Users\nicos\Desktop\MiFabricaIA2\run_sponsor_hunter.bat
```

Enviar correos reales (requiere SMTP configurado):

```bat
C:\Users\nicos\Desktop\MiFabricaIA2\run_sponsor_hunter.bat send
```

El pipeline autonoma ejecuta:

- `TRENDS_UPDATE_HOUR` (default `02:00`): refresh de tendencias
- `AUTO_PUBLISH_TIMES` (default `09:00,14:00,20:00`): genera y publica

Modo one-shot (sin loop infinito), util para cron externo o GitHub Actions:

```bash
python autonomous_pipeline.py --once --job cron
```

## GitHub Actions 24/7 (sin PC encendido)

Se agrego workflow cron listo para ejecutar en GitHub:

- Workflow: `.github/workflows/tutorial-pipeline-cron.yml`

Pasos:

1. Commit + push de estos cambios a GitHub.
2. En GitHub -> `Settings` -> `Secrets and variables` -> `Actions`, crea estos `Repository secrets`:
   - `GROQ_API_KEY`
   - `DEVTO_API_KEY`
   - `HASHNODE_API_KEY`
   - `HASHNODE_PUBLICATION_ID`
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHANNEL_ID`
   - `BLOGGER_ACCESS_TOKEN`
   - `BLOGGER_REFRESH_TOKEN`
   - `BLOGGER_BLOG_ID`
   - `BLOGGER_CLIENT_ID`
   - `BLOGGER_CLIENT_SECRET`
   - `BUSINESS_CONTACT_EMAIL`
   - `SPONSORSHIP_PAGE_URL`
   - `NEWSLETTER_URL`
   - `COMMUNITY_URL`
3. En `Actions`, habilita el workflow `Tutorial Pipeline Cron`.
4. Ejecuta `Run workflow` una vez manual para prueba inicial.

El workflow corre cada hora y el script decide automaticamente si corresponde ejecutar tendencias/publicacion segun:

- `TRENDS_UPDATE_HOUR`
- `AUTO_PUBLISH_TIMES`
- `PIPELINE_TIMEZONE`
- `CRON_WINDOW_MINUTES`

## Flujo de alto nivel

1. Scraping multi-fuente (`core/trend_analyzer.py`)
2. Ranking y cache de topics (`data/trends_cache*.json`)
3. Generacion en ingles (`core/content_generator.py`)
4. Publicacion multi-plataforma (`publishers/`)
5. Registro en historial y analytics (`data/history.json`, `data/analytics.json`)

## Reparar posts viejos de Blogger

Si tenias publicaciones viejas con markdown crudo en Blogger, puedes repararlas en sitio:

```bash
python scripts/repair_blogger_posts.py --tutorial-id <id_tutorial>
```

O reparar todas las entradas de Blogger que aparecen en el historial:

```bash
python scripts/repair_blogger_posts.py --all
```

## Funnel de sponsors/newsletter (Hashnode/Dev.to/Blogger)

El pipeline ya puede anadir automaticamente un footer de CTA con newsletter/contacto/sponsorship.
Configura en `.env`:

- `SPONSOR_CTA_ENABLED=true`
- `BUSINESS_CONTACT_EMAIL=...`
- `SPONSORSHIP_PAGE_URL=...`
- `NEWSLETTER_URL=...`
- `COMMUNITY_URL=...`

Publicar pagina "Work with me / Sponsorship" con un comando:

```bash
python scripts/publish_sponsorship_page.py --platforms hashnode,devto,blogger
```

Este comando crea/publica tu pagina comercial "Work with me" en las plataformas elegidas.

## Bot de sponsors (descubrimiento + outreach)

Script principal:

```bash
python scripts/run_sponsor_hunter.py
```

Que hace:

- Busca empresas potenciales en GitHub (por keywords).
- Intenta encontrar email/contact page en sus sitios.
- Calcula score de oportunidad.
- Exporta leads a `data/sponsor_leads.csv`.
- Prepara outreach personalizado usando `templates/sponsor_outreach_email.txt`.

Para envio real de emails:

```bash
python scripts/run_sponsor_hunter.py --send
```

Prueba de SMTP a un correo puntual:

```bash
python scripts/send_test_email.py --to nicoproxd567@gmail.com
```

Requisitos para envio:

- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`
- `OUTREACH_FROM_EMAIL`
- plantilla `templates/sponsor_outreach_email.txt`

## Validacion tecnica

```bash
python -m pytest tests -v
python -m flake8 . --max-line-length=120
python -m mypy . --ignore-missing-imports
```
