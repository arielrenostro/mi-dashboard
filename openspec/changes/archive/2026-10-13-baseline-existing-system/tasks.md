## 1. Verify the baseline

- [ ] 1.1 Run `openspec validate baseline-existing-system --strict` and verify it reports no errors
- [ ] 1.2 Review each of the 13 spec files against the running app (or the code) and verify no requirement contradicts observed behavior
- [ ] 1.3 Confirm the Known issues table in design.md with the maintainer and verify each row has an owner change or an explicit "later" decision

## 2. Publish the baseline

- [ ] 2.1 Archive the change (`openspec archive baseline-existing-system`) and verify `openspec list --specs` shows the 13 capabilities
- [ ] 2.2 After 2.1, delete `.specs/` and `ARCHITECTURE.md` and verify `git status` shows only those deletions
- [ ] 2.3 Trim the parts of `README.md` and `CLAUDE.md` that duplicate the specs (scope agreed, see design.md Resolved during review) and verify both still contain run, install and configuration instructions plus a pointer to `openspec/specs/`

## 3. Start the follow-up changes

- [ ] 3.1 Create one change per entry in the Follow-up changes table of design.md (`openspec new change <name>`) and verify each appears in `openspec list`
