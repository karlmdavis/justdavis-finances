# Development T-Dos

## Minor Items

- [X] Add additional Markdown formatting rules to @CONTRIBUTING.md and @CLAUDE.md,
        then apply them to all existing Markdown files:
    - [X] Every sentence, list item, or other full sentence-like line should end with a period.
    - [X] Trailing whitespace should be removed from lines,
            except when required by Markdown's formatting rules,
            such as for code blocks inside a list.
    - [X] Files should end with a line break, per POSIX.
- [X] Rename the YNAB "mutations" to "edits".
- [X] JSON file outputs should be pretty-printed, for readability and searchability.

## Major Items

- [ ] Figure out what version of Python we want to target,
        and remove any unnecessary compatibility comprises.
- [ ] Remove the error ignores in pyproject.toml and resolve any resulting issues.
- [X] Implement @dev/specs/2025-09-21-code-quality.md, to add lints and CI and such.
    - [X] Pre-commit hooks configured (Black, Ruff, file hygiene).
    - [X] GitHub Actions CI/CD workflow with all quality checks.
    - [X] Tool configurations (Black, Ruff, Mypy strict mode).
    - [X] Zero mypy errors achieved.
    - [X] IDE integration (.vscode/ settings, extensions, debugging).
    - [X] Renovate bot configuration for automated dependency updates.
    - [X] Status badges in README.md.
    - [X] Documentation updated with setup instructions.
    - [ ] Fix 2 failing tests in retirement service.
    - [ ] Increase test coverage from 56% to 60% threshold.
- [ ] Ensure there's one canonical end-to-end test that covers all major functionality.
      As the human overseer of a project mostly written by Claude Code,
        I'll keep an eye on this test case to ensure things haven't gone off the rails.
