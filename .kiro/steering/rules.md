---
inclusion: always
---

# Project Rules

## Bug & Error Investigation Protocol

For every ERROR, BUG, or Problem:

1. **Stop all changes** until root cause is identified with 100% certainty
2. Conduct deep analysis of the flow and dependencies
3. Document: what is failing, why it's failing, and any patterns or anomalies
4. No guesses — findings must be comprehensive before proposing fixes
5. Double-check for overlooked dependencies, edge cases, or related factors
6. Confirm the proposed solution directly addresses the root cause with evidence

### When Stuck on a Bug

1. Reflect on 5–7 different possible sources of the problem
2. Distill down to 1–2 most likely sources
3. Add logs to validate assumptions before implementing the actual fix

## Change Impact Analysis

- Make changes to features without impacting core functionality, other features, or flows
- Analyze behavior and dependencies to understand risks
- Communicate concerns before proceeding
- Test thoroughly to confirm no regressions or unintended effects
- Flag any out-of-scope changes for review
- Pause if uncertain

## New Feature Implementation Protocol

Before implementing ANY new feature:

1. **Check existing project structure** and database schema
2. **Reuse or centralize** where possible — keep things simple
3. **Never create a new database/table** without examining existing schema first (new features are likely related to existing data)
4. **Plan step by step**: what will change, what's impacted, how to test success
5. **Ask 1–5+ clarifying questions** before proceeding, with multiple-choice options for easy answers

### Pre-Implementation Checklist

- [ ] Search for similar implementations in other pages/components
- [ ] Review how other features handle the same pattern
- [ ] Check if utilities or helpers already exist
- [ ] Read database schema to understand table structure and relationships
- [ ] Verify field names, types, and relationships in models
- [ ] Review related documentation
- [ ] Check if feature was previously implemented
- [ ] Review existing API endpoints and patterns
- [ ] Look at similar pages to understand established patterns

## File Editing Best Practices

**Use `strReplace` for:**
- Small, targeted changes (single line or function)
- Import statement fixes
- Configuration value updates
- Bug fixes in specific code sections

**Use `fsWrite` for:**
- New files (components, modules, scripts)
- Complete file rewrites
- New documentation files

**Use `fsAppend` for:**
- Adding to existing files (new functions or sections)
- Extending configurations

## Testing Before Delivery

All scripts, code changes, and solutions MUST be tested BEFORE presenting:

1. **Run scripts** to verify they work (no syntax errors, encoding issues)
2. **Verify file changes** — read back to confirm correct application
3. **Test integration** — verify changes work with existing code
4. **Document results** — note what was tested and outcomes

If testing is NOT possible (requires running services, database, etc.):
- Clearly state the limitation
- Provide verification steps for the user
- Include expected outcomes
- Offer troubleshooting steps



### Responsive Design
- Mobile-first approach using ShadCN and Tailwind built-in breakpoints
- No custom breakpoints unless explicitly requested
- Create a phased plan: largest layout components first, then progressively smaller elements
- Test across all breakpoints before delivery

