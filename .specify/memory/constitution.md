<!--
  SYNC IMPACT REPORT - Constitution v1.0.0
  ========================================
  Version Change: [none] → 1.0.0 (Initial ratification)

  Modified Principles: N/A (initial version)
  Added Sections:
    - Core Principles (all 5 principles)
    - Development Standards
    - Workflow & Practices
    - Governance

  Removed Sections: N/A

  Templates Status:
    ✅ .specify/templates/plan-template.md - Reviewed, compatible (Constitution Check section will reference quality gates)
    ✅ .specify/templates/spec-template.md - Reviewed, compatible (user stories and requirements align)
    ✅ .specify/templates/tasks-template.md - Reviewed, compatible (test-optional approach matches)
    ✅ .specify/templates/agent-file-template.md - Reviewed, compatible

  Follow-up TODOs: None
-->

# Transcriptor Constitution

## Core Principles

### I. Personal Project Scope

This is a **personal project** developed for individual use and learning. The constitution recognizes:
- **No scale requirements**: Design for single-user or small-scale usage
- **Pragmatic over perfect**: Ship working solutions without over-engineering
- **Learning-focused**: Experiment with new technologies and patterns when beneficial
- **Time-bounded**: Favor incremental progress over comprehensive solutions

**Rationale**: Personal projects succeed through sustainable progress, not enterprise patterns. This principle prevents analysis paralysis and feature creep.

### II. Code Quality MUST Be Maintained

Despite personal scope, code quality is **non-negotiable**:
- Code MUST be readable and well-structured
- Functions MUST have single, clear responsibilities
- Complex logic MUST include explanatory comments
- Dependencies MUST be justified and minimal
- Dead code MUST be removed, not commented out

**Rationale**: Future maintainability matters even for personal projects. Good code quality reduces cognitive load when revisiting the project after weeks or months.

### III. Testing is Pragmatic, Not Mandatory

Testing follows a **risk-based approach**:
- Critical paths (data integrity, security, core functionality) SHOULD have tests
- Exploratory features and UI tweaks MAY skip tests
- When tests are written, they MUST be meaningful (not just coverage numbers)
- Integration tests are preferred over excessive unit tests for personal projects

**Rationale**: 100% test coverage is overkill for personal projects. Focus testing effort where bugs would cause real pain.

### IV. Documentation for Future Self

Documentation serves **future maintainability**:
- README MUST explain what the project does and how to run it
- Complex algorithms or non-obvious decisions MUST be documented
- Setup instructions MUST be current and tested
- Inline comments MUST explain "why", not "what"

**Rationale**: You will forget context. Document for the person who returns to this code in 6 months (yourself).

### V. Simplicity Over Scalability

Design choices MUST favor **simplicity**:
- Use the simplest solution that works for current needs
- Avoid microservices, complex architectures, and premature optimization
- Prefer boring, proven technology over cutting-edge frameworks
- Refactor when complexity becomes painful, not in anticipation of growth

**Rationale**: YAGNI (You Aren't Gonna Need It) is especially true for personal projects. Scale when needed, not before.

## Development Standards

### Code Structure

- **Organize by feature**, not by type (prefer `feature/models.py + feature/views.py` over `models/feature.py + views/feature.py`)
- **Limit file length** to ~300 lines; split when cognitive load increases
- **Use consistent naming** within the project (pick camelCase or snake_case and stick with it)

### Dependencies

- **Minimize external dependencies**: Each dependency is a maintenance burden
- **Pin versions** to avoid surprise breakage
- **Review licenses** for any third-party code
- **Prefer standard library** solutions when reasonable

### Error Handling

- **Fail fast and loud**: Don't silently swallow errors
- **Log meaningful context**: What failed, what was attempted, relevant state
- **User-facing errors** MUST be actionable (tell users what to do)

## Workflow & Practices

### Development Cycle

1. **Understand** the problem before coding
2. **Write** the simplest solution that could work
3. **Test** critical paths manually or with automated tests
4. **Refactor** when code becomes hard to understand
5. **Document** non-obvious decisions

### Git Practices

- **Commit frequently** with clear messages
- **One logical change** per commit
- **Use branches** for experiments, merge to main when stable
- **Don't force push** to main unless absolutely necessary

### Code Review (Self-Review)

Before committing significant changes:
- Read your own diff critically
- Check for hardcoded values, debug statements, TODOs
- Verify error paths are handled
- Ensure added complexity is justified

## Governance

### Amendment Process

This constitution can be updated when:
1. A principle proves impractical for the project
2. New insights emerge about what works for this project
3. The project scope fundamentally changes

Amendments require:
- Documentation of what changed and why
- Version bump following semantic versioning
- Update of all dependent templates

### Compliance

- All design decisions SHOULD reference applicable principles
- Constitution violations MUST be explicitly justified in plan documents
- Complexity additions MUST pass the "future self" test: will this make sense in 6 months?

### Versioning

- **MAJOR**: Removing or fundamentally changing a core principle
- **MINOR**: Adding new principles or expanding existing ones
- **PATCH**: Clarifications, typo fixes, non-semantic improvements

**Version**: 1.0.0 | **Ratified**: 2026-01-14 | **Last Amended**: 2026-01-14
