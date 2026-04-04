# Changelog

## [Unreleased] — Decision Intelligence Platform

### Added

#### Database
- Migration 003: 8 composite performance indexes for DI query patterns
- Migration 004: `di_simulation_results` table for portfolio simulation storage
- Migration 005: `di_weight_history` table for adaptive weight calibration tracking

#### Backend
- `models.py` — 42 standardized Pydantic models for all DI entities
- 14 new DI API endpoints under `/api/di/` with cursor-based pagination
- Standardized error response format with machine-readable error codes
- Base64-encoded cursor pagination helpers

#### Frontend
- React Query integration with `@tanstack/react-query`
- 7 new reusable components: ConfidenceBadge, FactorBreakdown, OutcomeTracker, RegimeIndicator, SignalTable, EquityCurve, PerformanceMetrics
- 3 new pages: `/signals`, `/signals/[id]`, `/simulations`
- Comprehensive TypeScript type definitions matching backend models
- Query key hierarchy for cache management

#### Testing
- Backend unit tests for Pydantic models, cursor pagination, error handling
- Frontend component tests for all new UI components
- Pytest configuration in `pyproject.toml`

#### Documentation
- Updated README with DI platform overview and API endpoint table
- Implementation plan at `docs/IMPLEMENTATION_PLAN.md`

### Changed
- `api.py` — Added global exception handler with standardized error format
- `services/di_router.py` — Updated with 14 standardized endpoints
- `lib/types.ts` — Replaced with comprehensive TypeScript interfaces
- `lib/api.ts` — Updated with standardized API client functions

### Architecture
- Polling-based execution model (no daemons, websockets, or background queues)
- Free-tier hosting compatible
- Modular architecture with strict type safety
- All existing functionality preserved without regressions
