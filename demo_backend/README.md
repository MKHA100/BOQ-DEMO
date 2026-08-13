# AutoBOQ demo backend

Standalone mock API for the Mattegoda demonstration. It does not use the real
backend, database, workers, OpenAI, or Roboflow. The existing frontend remains
unchanged and continues to call `http://localhost:8000`.

Run:

```bash
./demo_backend/run.sh
```

Stop the real backend first if it is already using port 8000.

## Deploying the demo API

Build the Docker image from the repository root:

```bash
docker build -f demo_backend/Dockerfile -t autoboq-demo-api .
docker run --rm -p 8000:8000 -e PORT=8000 -e CORS_ORIGINS=http://localhost:3000 autoboq-demo-api
```

`CORS_ORIGINS` is a comma-separated list of permitted frontend origins. For a
Vercel frontend, set it on Railway to the deployed Vercel URL, for example:

```text
CORS_ORIGINS=https://your-app.vercel.app
```

`CORS_ORIGIN_REGEX` is also supported when a controlled pattern is more useful,
such as Vercel preview deployments.

## Demo sequence

The mock API uses prerequisite-aware phase clocks:

1. Plans starts when the PDF upload finishes. Ground Floor appears at about 8
   seconds and the remaining floor cards appear individually through 18 seconds.
2. Specifications cannot start before Plans completes. Its clock starts when the
   Specifications page is first requested, then one category completes every 2
   seconds.
3. Scale remains uncalibrated until every specification category is complete.
   It then returns the saved confirmed two-point calibrations.

The shared workflow summary follows the same clocks, so navigation badges never
show later phases as confirmed before their prerequisite data is available.
