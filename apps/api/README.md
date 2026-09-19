# API Boundary

This directory is the FastAPI modular-monolith backend boundary.

FND-002 defines typed configuration in `app/core/config.py`. Settings use the
`BIZPILOT_` prefix and `__` for nested fields. Process environment values
override a local `.env` file. Copy `.env.example` for local development and
never commit a populated `.env` file.

Supported modes are `local`, `test`, `staging`, and `production`. AI
credentials and a model are required only when AI is enabled. Production rejects
debug mode, placeholder secrets, and PostgreSQL URLs that do not require TLS.

Application startup, database connectivity, domain modules, routes, and
business functionality require later approved tasks.
