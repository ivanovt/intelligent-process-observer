## 1. Runtime dependency and source configuration

- [x] 1.1 Promote `httpx` to backend runtime dependency range `>=0.28,<1` and refresh the lockfile.
- [x] 1.2 Add backend settings and `.env.example` documentation for named Prometheus source profiles with ID, display name, base URL, and bearer-token or Basic-auth credentials.
- [x] 1.3 Define the resolved source-profile and adapter interfaces independently of settings storage.

## 2. Definition domain and persistence

- [x] 2.1 Implement typed Metric Observation/Lens/Relationship domain and API contracts with the approved validation rules and machine-readable error shape.
- [x] 2.2 Add PostgreSQL persistence models and repository operations for atomic Observation aggregate creation and deterministic definition reads.
- [x] 2.3 Create an Alembic migration for Observation, Metric Lens, and Relationship definition storage.

## 3. Definition and navigation API

- [x] 3.1 Implement atomic Observation creation with aggregate validation and generated Observation identities.
- [x] 3.2 Implement compact Observation listing and complete Observation, Lens, and Relationship detail routes with relative hrefs.
- [x] 3.3 Implement Prometheus capability discovery without exposing connection details or credentials.

## 4. Prometheus Metric preflight

- [x] 4.1 Implement the async Prometheus range-query adapter using POST, 15-second timeout, no retry, bearer/basic authentication, and safe provider error mapping.
- [x] 4.2 Implement Metric preflight request validation and response translation, including single-series checks, typed finite/non-finite samples, warnings, and bounded multi-series label diagnostics.
- [x] 4.3 Expose the non-persisting Metric preflight endpoint and ensure it creates no definition or runtime objects.

## 5. Verification

- [x] 5.1 Add unit tests for contract validation, Relationship topology/vocabulary, source capability projection, and href generation.
- [x] 5.2 Add persistence and API tests for atomic creation, list/detail navigation, unknown resources, and machine-readable validation errors.
- [x] 5.3 Add mocked Prometheus adapter tests for successful single-series responses, cardinality failures, non-finite samples, provider warnings, query errors, auth failures, timeouts, and transport failures.
- [x] 5.4 Run `make check` and resolve all reported failures before archive or pull-request preparation.
