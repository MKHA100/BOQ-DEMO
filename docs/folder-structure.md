# Folder Structure

```text
autoboq/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── dependencies/
│   │   │   ├── v1/
│   │   │   │   ├── auth_routes.py
│   │   │   │   ├── job_routes.py
│   │   │   │   ├── platform_routes.py
│   │   │   │   └── project_routes.py
│   │   │   └── router.py
│   │   ├── auth/
│   │   ├── core/
│   │   ├── database/
│   │   │   ├── migrations.py
│   │   │   ├── schema.py
│   │   │   └── session.py
│   │   ├── jobs/
│   │   │   ├── job_models.py
│   │   │   ├── job_repository.py
│   │   │   ├── job_service.py
│   │   │   └── worker.py
│   │   ├── platform/
│   │   ├── projects/
│   │   ├── storage/
│   │   ├── workflow/
│   │   │   ├── constants.py
│   │   │   ├── dependencies.py
│   │   │   ├── files.py
│   │   │   ├── jobs.py
│   │   │   ├── *_repo.py
│   │   │   ├── repo.py
│   │   │   ├── read_routes.py
│   │   │   ├── read_service.py
│   │   │   ├── routes.py
│   │   │   ├── schema.py
│   │   │   ├── schemas.py
│   │   │   ├── *_service.py
│   │   │   └── service.py
│   │   ├── tests/
│   │   └── main.py
│   ├── .env.example
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── app/
│   │   ├── workspace/[projectId]/
│   │   │   ├── loading.tsx
│   │   │   ├── error.tsx
│   │   │   ├── upload/page.tsx
│   │   │   ├── floor-plans/page.tsx
│   │   │   ├── specifications/page.tsx
│   │   │   ├── scale/page.tsx
│   │   │   ├── model-review/page.tsx
│   │   │   ├── walls/page.tsx
│   │   │   ├── floors/page.tsx
│   │   │   ├── review/page.tsx
│   │   │   └── boq/page.tsx
│   │   └── layout.tsx
│   ├── features/
│   │   ├── upload/
│   │   ├── floor-plans/
│   │   ├── specifications/
│   │   ├── scale/
│   │   ├── model-review/
│   │   ├── walls/
│   │   ├── floors/
│   │   ├── review/
│   │   ├── boq/
│   │   └── workflow/
│   │       ├── components/
│   │       ├── hooks/
│   │       ├── state/
│   │       ├── api.ts
│   │       ├── readApi.ts
│   │       ├── readTypes.ts
│   │       ├── queryKeys.ts
│   │       ├── steps.ts
│   │       └── types.ts
│   ├── shared/
│   │   ├── components/
│   │   ├── constants/
│   │   ├── providers/
│   │   ├── services/
│   │   └── types/
│   ├── styles/
│   │   ├── globals.css
│   │   └── tokens.css
│   ├── .env.local.example
│   ├── Dockerfile
│   └── package.json
├── docker/
├── docs/
├── scripts/
├── .env.example
├── package.json
└── README.md
```

The structure follows the existing FastAPI and Next.js application rather than introducing a separate monorepo framework. Shared behavior stays centralized, while later page-specific components, hooks, API adapters, types, and utilities can be added inside the matching short feature name.
