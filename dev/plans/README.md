# Implementation Plans

This directory contains detailed implementation plans for the architectural overhaul
of the justdavis-finances system.

## Background

The project approached its first release with significant quality issues:
- Far too many CLI commands with excessive options
- Brittle integration points causing test failures
- Inconsistent type handling (especially currency and dates)
- Tests coupled to implementation details rather than behavior
- Data format mismatches between components

These issues led to a multi-PR cycle of yo-yo fixes where addressing one problem
would break something else.

## Approach: Top-Down Refactoring

We're taking a **top-down approach**:
1. Lock in the UX first (Phase 1)
2. Build type safety (Phase 2)
3. Create consistent infrastructure (Phase 3)
4. Refactor domain models (Phase 4)
5. Improve test quality (Phase 5)
6. Update documentation (Phase 6)

This minimizes rework by defining the target interface before refactoring internals.

## Phases

### [Phase 1: CLI Simplification](phase-1-cli-simplification.md)
**Status:** 🟢 Complete
**Completed:** 2024-10-13
**PR:** #10

Transform from 5 CLI command files with 20+ commands to a single `finances flow` command
with interactive prompts showing data summary/age and asking user whether to update.

**Key Changes:**
- Removed all individual CLI commands
- Added interactive node prompts with data summaries
- Users just run `finances flow` and answer questions
- FlowNode pattern with dependency management

**Impact:** Immediate UX improvement, massively simplified interface

---

### [Phase 2: Primitive Types](phase-2-primitive-types.md)
**Status:** 🟢 Complete
**Completed:** 2024-10-13
**PR:** #11

Introduce `Money` and `FinancialDate` wrapper classes for type-safe currency and date handling.

**Key Changes:**
- `Money` class wraps currency (no more raw ints)
- `FinancialDate` class wraps dates (consistent formatting)
- Type system prevents mixing incompatible units
- Full migration of all domains to new types

**Impact:** Zero floating-point violations, type-safe operations

---

### [Phase 3: DataStore Infrastructure](phase-3-datastore-infrastructure.md)
**Status:** 🔵 Ready to start
**Effort:** 13-19 hours (2-3 days) - *revised down from 18-25 hours*
**Dependencies:** ✅ Phases 1-2 complete

Extract data management logic from FlowNodes into reusable DataStore components for better
separation of concerns and testability.

**Key Changes:**
- DataStore protocol matching NodeDataSummary interface
- 8 domain-specific DataStore implementations
- FlowNodes delegate to DataStores for data access
- Archive system integration

**Impact:** Separation of concerns, better testability, eliminates code duplication

---

### [Phase 4: Domain Model Refactoring](phase-4-domain-models.md)
**Status:** ⏳ Waiting for Phase 3
**Effort:** 32-42 hours (5-7 days)
**Dependencies:** Phases 1-3

Clean domain models true to source formats (CSV, HTML, JSON), with split generator
handling normalization internally.

**Key Changes:**
- YNAB models match API structure
- Amazon models match CSV structure
- Apple models match HTML structure
- Split generator gets internal transformers

**Impact:** Domain integrity, clear responsibilities, better testability

---

### [Phase 5: Test Suite Overhaul](phase-5-test-overhaul.md)
**Status:** ⏳ Can start after Phase 1
**Effort:** 24-33 hours (4-5 days)
**Dependencies:** Phase 1 (can parallelize with 2-4)

Refactor test suite to inverted pyramid: E2E > Integration > Unit. Remove low-value tests.

**Key Changes:**
- Primary E2E test: complete `finances flow` execution
- Integration tests use real components, minimal mocking
- Unit tests only for complex business logic
- Delete ~100+ low-value tests

**Impact:** Tests catch real bugs, faster execution, easier maintenance

---

### [Phase 6: Documentation & Polish](phase-6-documentation.md)
**Status:** ⏳ Waiting for all phases
**Effort:** 17-24 hours (3-4 days)
**Dependencies:** Phases 1-5

Update all documentation to reflect new architecture and clean up technical debt.

**Key Changes:**
- Update all specs
- Create architecture documentation
- Update CLAUDE.md
- Clean up TODOs
- Polish README

**Impact:** Accurate docs, easier onboarding, professional finish

---

## Total Effort Estimate

**Original estimate:** 116-161 hours (18-25 work days, ~4-5 weeks)

**Revised estimate (post-Phases 1 & 2):**
- ✅ Phase 1: ~11 hours (complete)
- ✅ Phase 2: ~20 hours (complete)
- Phase 3: 13-19 hours (revised down from 18-25)
- Phase 4: 32-42 hours
- Phase 5: 24-33 hours
- Phase 6: 17-24 hours

**Remaining work:** 86-118 hours (14-19 work days, ~3-4 weeks)

**With parallelization opportunities:**
- Phase 5 can overlap with Phases 3-4
- Some phases can be split into sub-phases
- Realistic timeline: ~2-3 weeks with focused effort

## Success Metrics

### Technical Quality
- Zero floating-point currency operations
- No type mismatches at integration points
- <5 minute test suite execution
- Single command interface

### Development Velocity
- PRs merge in 1-3 commits (not 10+)
- Fixes don't break other components
- Clear failure messages when things break

### User Experience
- One command to remember: `finances flow`
- Clear prompts at each decision point
- Helpful error messages

## Working Through Plans

Each phase plan includes:
- **Goal**: What we're trying to achieve
- **Problem Statement**: Current vs. target state
- **Key Changes**: Detailed implementation notes
- **Testing Strategy**: How to verify it works
- **Definition of Done**: Concrete checklist
- **Estimated Effort**: Time expectations
- **Dependencies**: What must complete first

### Process

1. **Read the phase plan thoroughly**
2. **Create feature branch** for the phase
3. **Work through Definition of Done checklist**
4. **Create PR** when complete
5. **Update phase status** in this README

### Phase Status Indicators

- 🔵 **Ready to start** - No blockers
- 🟡 **In progress** - Currently being worked on
- 🟢 **Complete** - Merged to main
- ⏳ **Waiting** - Blocked by dependencies

## Questions or Concerns?

If you encounter issues or have questions while implementing:
1. Check the relevant spec in `dev/specs/`
2. Review CLAUDE.md for project conventions
3. Create a GitHub issue for discussion
4. Update the plan based on learnings

## Tracking Progress

Update this README as phases complete:
```markdown
### [Phase 1: CLI Simplification](phase-1-cli-simplification.md)
**Status:** 🟢 Complete
**Completed:** 2025-10-15
**PR:** #123
```

This helps future developers understand the evolution of the system.
