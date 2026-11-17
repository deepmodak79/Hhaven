# Haven — PG & Hostel Operations

Haven is a multi-property operations dashboard for Indian PG and hostel owners.

## Stack
- FastAPI + SQLAlchemy + PostgreSQL
- JWT authentication with owner / manager / tenant roles
- Responsive vanilla JS frontend served by FastAPI
- Docker + Railway deployment

## Included
- Property, floor, room and bed occupancy management
- Resident records and check-in / check-out
- Rent ledger, deposits, partial/manual payment records
- Electricity readings and configurable billing
- Complaints with priority and lifecycle
- Staff tasks and cleaning checklists
- Tenant-facing read-only view
- Demo seed data (clearly labelled)

## Demo access
- Owner: `owner@haven.demo`
- Password: `HavenDemo2026!`

Change the demo password and set a strong `JWT_SECRET` before using real data.

## Local run
```bash
docker compose up --build
```
Open http://localhost:8000.

## Railway
Deploy the repository as a Docker service and attach a PostgreSQL service. Set:
- `DATABASE_URL` to the Railway Postgres private connection reference
- `JWT_SECRET` to a long random secret
- `CORS_ORIGINS` to the public app origin (optional; same-origin is default)

The app seeds demo records only when the database is empty. Do not use the demo credentials or seed data for real resident information.

## Security notes
- Passwords are bcrypt-hashed.
- API requests require signed JWTs.
- Records are scoped to the authenticated user's property memberships.
- Payment entries are manual ledger records, not payment collection or bank verification.
- Resident document uploads and WhatsApp automation are not included in this MVP.
