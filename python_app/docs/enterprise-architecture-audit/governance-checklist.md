# Architecture Governance Checklist

## Use this before merging structural changes

### Layering
- [ ] Did the change avoid adding new feature orchestration into `MainWindow`?
- [ ] Did the change avoid adding direct DB access into `views/`?
- [ ] Did the change avoid adding UI assumptions into `services/`?
- [ ] Did the change keep `models/` free of DB/network/Qt dependencies?

### Ownership
- [ ] Does the new code live in the package where future engineers would expect to find it?
- [ ] If this is orchestration logic, was `features/<feature>/coordinator.py` considered first?
- [ ] If this is provider/tool integration, does it live in `services/`?
- [ ] If this is persistence/query logic, does it live in `database/`?

### MainWindow control
- [ ] If `MainWindow` was touched, is the change glue/delegation rather than new business logic?
- [ ] If a coordinator already exists for this feature, did the change go there instead of staying in the host?

### Refactor safety
- [ ] Did the change preserve existing visible behavior?
- [ ] Is there a smoke validation plan for the affected feature?
- [ ] Did the change avoid mixing visualizer subsystem refactor into unrelated app-shell changes?

### Migration discipline
- [ ] If this is transitional code, is the exception temporary and documented?
- [ ] Did the change reduce architectural drift instead of just moving code sideways?
