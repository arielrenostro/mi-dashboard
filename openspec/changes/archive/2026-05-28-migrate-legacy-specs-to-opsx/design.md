## Context

The project has 10 specification files under `.specs/` written before the OPSX toolchain was adopted. These files are accurate documentation of the current system behavior. The goal is to promote them into `openspec/specs/` as proper OPSX spec files so future changes can reference, update, and archive them through the standard workflow.

## Goals / Non-Goals

**Goals:**
- Represent each `.specs/*.md` file as a capability spec under `openspec/specs/<name>/spec.md`
- Preserve the full semantic content of each existing spec
- Format requirements as testable SHALL/MUST statements with WHEN/THEN scenarios

**Non-Goals:**
- Changing any system behavior
- Modifying any production code
- Removing the `.specs/` directory (kept as-is; can be archived later)
- Filling in known TODOs in the original specs (e.g., VE map ECU data source)

## Decisions

**One spec per existing `.specs/*.md` file** — the original files have clean single-responsibility boundaries; there is no reason to merge or split them.

**Kebab-case mapping:** `alarm_system.md` → `alarm-system`, `ve_calibration_screen.md` → `ve-calibration-screen`, etc. Underscores become hyphens; no other renaming.

**Content conversion:** all tables, algorithms, and rules in the existing specs are preserved verbatim. The OPSX requirement/scenario structure is layered on top — original text becomes requirement bodies; observable inputs and outputs become WHEN/THEN scenarios.

**No delta specs** — no existing `openspec/specs/` capability overlaps with these. All 11 specs are entirely new.

## Risks / Trade-offs

**[Risk] Spec content may drift from code** → Not introduced by this change; `.specs/` was already the source of truth. Mitigation: OPSX makes it easier to keep specs updated via the apply/archive workflow.

**[Risk] Existing `openspec/specs/ve-percentage-increment/` may reference concepts named differently** → Low risk; that spec targets VE increment size, not map structure. No cross-spec identifiers need aligning.
