# Development T-Dos

## Minor Items

- [X] Add additional Markdown formatting rules to @CONTRIBUTORS.md and @CLAUDE.md,
        then apply them to all existing Markdown files:
    - [X] Every sentence, list item, or other full sentence-like line should end with a period.
    - [X] Trailing whitespace should be removed from lines,
            except when required by Markdown's formatting rules,
            such as for code blocks inside a list.
    - [X] Files should end with a line break, per POSIX.
- [X] Rename the YNAB "mutations" to "edits".
- [X] JSON file outputs should be pretty-printed, for readability and searchability.

## Major Items

- [ ] Remove the error ignores in pyproject.toml and resolve any resulting issues.
- [ ] Implement @dev/specs/2025-09-21-code-quality.md, to add lints and CI and such.
- [ ] Ensure there's one canonical end-to-end test that covers all major functionality.
      As the human overseer of a project mostly written by Claude Code,
        I'll keep an eye on this test case to ensure things haven't gone off the rails.
