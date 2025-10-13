# Phase 6: Documentation & Polish

## Goal

Update all documentation to reflect the new architecture and clean up any
remaining technical debt.

## Problem Statement

Current state:
- `dev/specs/` describe old multi-command architecture
- CLAUDE.md has outdated command examples
- No architecture documentation for new design
- Todos scattered across code and files

Target state:
- All specs updated to reflect Phase 1-5 changes
- Architecture documentation explains new design
- CLAUDE.md has current examples
- All todos either completed or tracked in GitHub issues

## Key Changes

### 1. Update Specifications

**Files to update:**
- `dev/specs/2025-09-24-financial-flow-system.md` - Reflect interactive prompts
- `dev/specs/2025-09-21-python-package-restructure.md` - Document new structure
- Other specs as needed

**Updates needed:**
- Remove references to individual CLI commands
- Document interactive node prompts
- Update examples to use `finances flow`
- Document Money and FinancialDate types
- Document DataStore architecture

### 2. Create Architecture Documentation

**File:** `dev/docs/architecture.md` (NEW)

Document:
- System overview diagram
- Data flow through the system
- Domain model relationships
- DataStore pattern
- Transformer pattern for split generation
- Money and FinancialDate usage
- Testing philosophy

### 3. Update CLAUDE.md

**File:** `CLAUDE.md`

Update sections:
- Command examples (now just `finances flow`)
- Currency handling (now `Money` class)
- Date handling (now `FinancialDate` class)
- Testing philosophy (inverted pyramid)
- Development workflow (unchanged)
- Recent improvements section

### 4. Create Developer Guide

**File:** `CONTRIBUTING.md` (enhance existing)

Add sections:
- How to add a new flow node
- How to create a new DataStore
- How to write good tests (with examples)
- How to use Money and FinancialDate
- How to debug the flow system

### 5. Clean Up TODOs

**Strategy:**
1. Grep for all `TODO`, `FIXME`, `XXX` comments in code
2. For each:
   - If trivial, fix immediately
   - If important, create GitHub issue and reference in comment
   - If obsolete, delete
3. Document known limitations in `KNOWN_ISSUES.md`

**File:** `dev/KNOWN_ISSUES.md` (update)

Document:
- Architecture limitations
- Performance considerations
- Edge cases and workarounds
- Future enhancement ideas

### 6. Update README

**File:** `README.md`

Update:
- Quick start examples (use `finances flow`)
- Installation instructions
- Basic usage guide
- Link to architecture docs

## Documentation Checklist

### User-Facing Documentation
- [ ] README.md updated with new examples
- [ ] Quick start guide updated
- [ ] Command reference updated

### Developer Documentation
- [ ] Architecture documentation created
- [ ] CONTRIBUTING.md enhanced
- [ ] Testing guide updated
- [ ] CLAUDE.md updated for Claude Code

### Specification Updates
- [ ] Financial Flow System spec updated
- [ ] Python Package spec updated
- [ ] Other specs reviewed and updated

### Code Cleanup
- [ ] All TODOs addressed or tracked
- [ ] KNOWN_ISSUES.md updated
- [ ] Obsolete comments removed
- [ ] Dead code removed

### Polish
- [ ] Consistent formatting across all docs
- [ ] Links working
- [ ] Examples tested
- [ ] Spelling and grammar checked

## Testing Strategy

- Run all examples in documentation
- Verify links work
- Check for broken references
- Validate code examples compile

## Definition of Done

- [ ] All specs updated
- [ ] Architecture documentation complete
- [ ] CLAUDE.md current
- [ ] Developer guide complete
- [ ] All TODOs addressed
- [ ] README updated
- [ ] Examples tested
- [ ] No broken links

## Estimated Effort

- **Spec Updates**: 3-4 hours
- **Architecture Docs**: 4-6 hours
- **CLAUDE.md Update**: 2-3 hours
- **Developer Guide**: 3-4 hours
- **TODO Cleanup**: 3-4 hours
- **Testing & Polish**: 2-3 hours
- **Total**: 17-24 hours (3-4 work days)

## Dependencies

- All Phases 1-5 complete (documenting the final state)

## Output Examples

### Before (CLAUDE.md):
```bash
# Amazon transaction matching
finances amazon match --start 2024-07-01 --end 2024-07-31

# Apple receipt processing
finances apple fetch-emails --days-back 30
finances apple parse-receipts --input-dir data/apple/emails/
```

### After (CLAUDE.md):
```bash
# Complete financial data update
finances flow   # Interactive prompts guide you through

# Or non-interactive mode
finances flow --non-interactive
```

### Architecture Documentation

```markdown
# System Architecture

## Overview

The justdavis-finances system processes financial data through a directed
acyclic graph (DAG) of nodes, each responsible for one data operation.

## Core Concepts

### Flow Nodes
Each node represents one operation (sync YNAB, match Amazon orders, etc.)
and implements:
- Data summary generation (for interactive prompts)
- Change detection (to skip unnecessary work)
- Execution logic (the actual work)
- Dependency declaration (what it needs)

### Interactive Prompts
Before executing each node, the system prompts:
```
YNAB Sync
  YNAB cache: 1,234 transactions
  Last updated: 5 days ago
  Update this data? [y/N]
```

[... detailed diagrams and explanations ...]
```

## Success Criteria

- New developer can understand system in <1 hour reading docs
- All code examples in docs are accurate and tested
- No orphaned TODOs in codebase
- Claude Code has accurate instructions for working with repo
