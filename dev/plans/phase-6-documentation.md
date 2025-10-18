# Phase 6: Documentation & Code Cleanup

## Status: 🚧 IN PROGRESS

**Last Updated**: 2025-10-18

## Goal

Ensure all documentation accurately reflects the completed Phase 1-5 architecture and eliminate
  technical debt from the codebase.

## High-Level Objectives

1. **Audit and update specification files** to reflect the completed flow system and domain models
2. **Create architecture documentation** for new developers
3. **Clean up technical debt** (TODOs, obsolete comments, dead code)
4. **Ensure documentation accuracy** (tested examples, working links, current instructions)

## Problem Statement

**Current state:**
- ✅ README.md is comprehensive and current (documents `finances flow`)
- ✅ CLAUDE.md is up-to-date with Money/FinancialDate and testing philosophy
- ✅ Phase plans documented and marked complete (Phases 1-5)
- ⚠️ Specs in `dev/specs/` may reference old command structures or outdated architecture
- ❌ No centralized architecture documentation file for developers
- ❌ TODOs/FIXMEs not audited or tracked
- ❌ CONTRIBUTING.md may need enhancement with developer guides

**Target state:**
- All specifications updated to reflect current architecture (flow system, domain models, DataStores)
- Architecture documentation explains system design for new developers (<1 hour to understand)
- All TODOs either completed, tracked in GitHub issues, or documented as known limitations
- CONTRIBUTING.md includes comprehensive developer guides

## Success Criteria

- New developer can understand system architecture in <1 hour reading docs
- All code examples in documentation are accurate and tested
- No orphaned TODOs in codebase (all tracked or resolved)
- All internal documentation links work correctly
- Specs reflect actual implementation (not aspirational designs)

## Key Changes

### 1. Audit and Update Specifications

**Files to audit** (in `dev/specs/`):
- `2025-09-24-financial-flow-system.md` - Verify reflects current implementation
- `2025-09-21-python-package-restructure.md` - Verify reflects final package structure
- `2025-09-21-amazon-transaction-matching.md` - Verify reflects domain model implementation
- `2025-09-14-apple-transaction-matching.md` - Verify reflects domain model implementation
- `2025-09-20-ynab-transaction-updater.md` - Verify reflects current YNAB integration
- `2025-09-21-amazon-data-workflow.md` - Verify reflects DataStore and flow system
- `2025-09-21-ynab-data-workflow.md` - Verify reflects DataStore and flow system
- `2025-09-21-cash-flow-analysis.md` - Verify reflects current analysis implementation
- Other specs as needed

**Updates needed:**
- Remove references to deprecated multi-command architecture (if any)
- Document Money and FinancialDate primitives in relevant specs
- Document DataStore architecture usage
- Update code examples to reflect current implementations
- Mark obsolete specs as deprecated or archive them

**Audit criteria:**
- Does spec reflect current implementation?
- Are code examples accurate and tested?
- Are command examples current (`finances flow` vs old individual commands)?
- Are domain models documented correctly?

### 2. Create Architecture Documentation

**File:** `dev/docs/ARCHITECTURE.md` (NEW)

**Content to include:**
- **System Overview**: High-level description of financial flow system
- **Core Concepts**:
  - Flow nodes and dependency graph
  - DataStore pattern for data persistence
  - Domain models and type-safe primitives (Money, FinancialDate)
  - Change detection and archiving
- **Package Structure**: Explain `src/finances/` organization
- **Data Flow Diagrams**: Visual representation of data through system
- **Testing Philosophy**: Link to inverted pyramid documentation
- **Extension Points**: How to add new flow nodes, datastores, domain models

**Target audience**: New developers with Python experience but no codebase familiarity

**Success metric**: New developer can understand architecture in <1 hour

### 3. Update CONTRIBUTING.md

**File:** `CONTRIBUTING.md` (enhance existing)

**Add sections:**
- **Adding a New Flow Node**: Step-by-step guide with example
- **Creating a New DataStore**: Pattern and best practices
- **Working with Domain Models**: Money, FinancialDate, and domain-specific models
- **Writing Tests**: E2E → Integration → Unit approach with examples
- **Debugging the Flow System**: Common issues and solutions
- **Code Quality Tools**: pre-commit hooks, mypy, ruff, black usage

**Keep existing sections:**
- PR workflow and success criteria
- Testing philosophy
- Markdown formatting guidelines

### 4. Clean Up TODOs and Technical Debt

**Strategy:**
1. Search codebase for `TODO`, `FIXME`, `XXX`, `HACK` comments
2. For each item:
   - **Trivial**: Fix immediately in this phase
   - **Important**: Create GitHub issue and reference in comment (`# TODO(#123): ...`)
   - **Obsolete**: Delete the comment
   - **By design**: Move to `KNOWN_ISSUES.md` with explanation

**File:** `dev/KNOWN_ISSUES.md` (update or create)

**Document:**
- Architecture limitations (intentional design constraints)
- Performance considerations (acceptable trade-offs)
- Edge cases and workarounds (documented behaviors)
- Future enhancement ideas (not TODO, but "nice to have")

**Search commands:**
```bash
# Find all TODOs in source code
rg "TODO|FIXME|XXX|HACK" src/

# Find all TODOs in test code
rg "TODO|FIXME|XXX|HACK" tests/

# Find all TODOs in documentation
rg "TODO|FIXME|XXX|HACK" *.md dev/
```

### 5. Verify Documentation Accuracy

**Tasks:**
1. **Test all code examples** in README.md and CLAUDE.md
2. **Verify all links** work (internal and external)
3. **Check command examples** match actual CLI
4. **Validate import examples** in CLAUDE.md
5. **Spell-check** all documentation files

**Testing checklist:**
- [ ] Run every command in README.md "Basic Usage" section
- [ ] Run every command in "Core Features" sections
- [ ] Verify import statements in CLAUDE.md work
- [ ] Test CLI examples in specification files
- [ ] Verify configuration examples in README.md

**Link verification:**
```bash
# Check internal links in markdown files
# (manual inspection needed)
grep -r "\[.*\](.*.md)" *.md dev/

# Verify files referenced exist
# (check paths in CLAUDE.md, README.md, CONTRIBUTING.md)
```

### 6. Clean Up Obsolete Files and Directories

**Audit:**
- Check `dev/` for obsolete planning documents
- Remove empty or placeholder files
- Archive superseded specifications

**Candidates for review:**
- `dev/phase-2-type-checking-report.md` - Integrate into Phase 2 plan or archive
- Duplicate/superseded phase plans (keep only final versions)
- Old reports that are no longer relevant

## Documentation Checklist

### User-Facing Documentation
- [x] README.md comprehensive and current
- [ ] All examples in README.md tested
- [ ] Configuration section accurate

### Developer Documentation
- [ ] ARCHITECTURE.md created with complete system overview
- [ ] CONTRIBUTING.md enhanced with developer guides
- [ ] CLAUDE.md accuracy verified
- [ ] Testing guide complete (tests/README.md already excellent)

### Specification Audit
- [ ] Financial Flow System spec audited
- [ ] Python Package spec audited
- [ ] Amazon matching spec audited
- [ ] Apple matching spec audited
- [ ] YNAB integration spec audited
- [ ] Cash flow analysis spec audited
- [ ] Other specs reviewed
- [ ] Obsolete specs archived or marked deprecated

### Code Cleanup
- [ ] All TODOs cataloged
- [ ] Trivial TODOs fixed
- [ ] Important TODOs tracked in GitHub issues
- [ ] Obsolete TODOs removed
- [ ] KNOWN_ISSUES.md updated
- [ ] Dead code removed
- [ ] Obsolete comments removed

### Documentation Quality
- [ ] All code examples tested
- [ ] All links verified
- [ ] Spelling checked
- [ ] Consistent formatting
- [ ] No broken references

## Testing Strategy

1. **Code Examples**: Run every code example in documentation
2. **CLI Examples**: Execute every `finances` command example
3. **Links**: Manually verify all internal links
4. **Imports**: Test Python import examples in fresh environment
5. **Configuration**: Verify `.env` examples and configuration docs

## Estimated Effort

| Task | Estimated Hours |
|------|----------------|
| Specification audit and updates | 4-6 hours |
| Architecture documentation | 4-6 hours |
| CONTRIBUTING.md enhancement | 2-3 hours |
| TODO cleanup and tracking | 3-4 hours |
| Documentation testing | 2-3 hours |
| Link verification and polish | 1-2 hours |
| **Total** | **16-24 hours (2-3 work days)** |

## Dependencies

- ✅ Phase 1 (CLI Simplification) - Complete
- ✅ Phase 2 (Type-Safe Primitives) - Complete
- ✅ Phase 3 (DataStore Infrastructure) - Complete
- ✅ Phase 4/4.5 (Domain Models) - Complete
- ✅ Phase 5 (Test Overhaul) - Complete

## Tasks

### Task 1: Specification Audit
**Priority**: High
**Effort**: 4-6 hours

For each spec file in `dev/specs/`:
1. Read through completely
2. Identify outdated sections (command examples, architecture references)
3. Update or mark as deprecated
4. Test any code examples
5. Update "Status" section if present

**Deliverable**: All specs reflect current implementation or marked as deprecated

### Task 2: Architecture Documentation
**Priority**: High
**Effort**: 4-6 hours

Create `dev/docs/ARCHITECTURE.md` with:
1. System overview diagram (text-based or Mermaid)
2. Core concepts explained (Flow, DataStore, Domain Models)
3. Package structure walkthrough
4. Data flow through system
5. Extension guide (adding nodes, datastores)

**Deliverable**: New developers can understand system in <1 hour

### Task 3: CONTRIBUTING.md Enhancement
**Priority**: Medium
**Effort**: 2-3 hours

Add developer guides for:
1. Adding a new flow node (with example)
2. Creating a new DataStore (pattern)
3. Working with Money and FinancialDate
4. Debugging flow execution
5. Using code quality tools

**Deliverable**: Comprehensive developer onboarding guide

### Task 4: TODO Cleanup
**Priority**: Medium
**Effort**: 3-4 hours

1. Search for all TODO/FIXME/XXX/HACK comments
2. Categorize as trivial/important/obsolete/by-design
3. Fix trivial issues immediately
4. Create GitHub issues for important TODOs
5. Remove obsolete comments
6. Document design limitations in KNOWN_ISSUES.md

**Deliverable**: Zero orphaned TODOs, all tracked or resolved

### Task 5: Documentation Accuracy Verification
**Priority**: Medium
**Effort**: 2-3 hours

1. Test all CLI command examples
2. Test all Python import examples
3. Verify all internal links
4. Spell-check all markdown files
5. Ensure consistent formatting

**Deliverable**: 100% accurate, tested documentation

### Task 6: File Cleanup
**Priority**: Low
**Effort**: 1-2 hours

1. Review `dev/` directory for obsolete files
2. Archive or remove superseded documents
3. Consolidate duplicate information
4. Organize reports and plans

**Deliverable**: Clean, organized documentation structure

## Definition of Done

- [ ] All specifications audited and updated or marked deprecated
- [ ] ARCHITECTURE.md created with complete system overview
- [ ] CONTRIBUTING.md enhanced with developer guides
- [ ] All TODOs cataloged and tracked in GitHub issues or resolved
- [ ] All code examples in documentation tested and accurate
- [ ] All internal links verified and working
- [ ] Spell-check completed across all documentation
- [ ] Obsolete files archived or removed
- [ ] New developer can understand system in <1 hour from docs
- [ ] Claude Code has accurate, current instructions

## Success Metrics

**Documentation Quality**:
- ✅ New developer onboarding time: <1 hour to understand architecture
- ✅ Code example accuracy: 100% tested and working
- ✅ Link integrity: 100% working internal links
- ✅ TODO tracking: Zero orphaned TODOs

**Technical Debt**:
- ✅ All TODOs tracked in GitHub issues or resolved
- ✅ No dead code or obsolete comments
- ✅ All known limitations documented

**Developer Experience**:
- ✅ Clear extension guides (new nodes, datastores)
- ✅ Testing philosophy well-documented
- ✅ Debugging guides available
- ✅ Code quality tools documented

## Related Work

**Completed Phases**:
- Phase 1: CLI Simplification (Single `finances flow` command)
- Phase 2: Type-Safe Primitives (Money, FinancialDate)
- Phase 3: DataStore Infrastructure (Data persistence layer)
- Phase 4/4.5: Domain Model Migration (Complete domain model coverage)
- Phase 5: Test Overhaul (357 high-quality tests, E2E-first approach)

**Documentation Already Complete**:
- README.md: Comprehensive user guide
- CLAUDE.md: Current AI assistant instructions
- Phase plans: Complete documentation of all phases
- tests/README.md: Excellent testing guide

---

## Phase 6 Status: 🚧 IN PROGRESS

**Next Steps**:
1. Start with specification audit (Task 1)
2. Create architecture documentation (Task 2)
3. Clean up TODOs (Task 4)
4. Enhance CONTRIBUTING.md (Task 3)
5. Verify documentation accuracy (Task 5)
6. Final polish and file cleanup (Task 6)
