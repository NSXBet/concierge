# Work type question guides

Use these tailored question sets based on the identified work type. Not every question applies to every project -- skip questions whose answers are obvious from the codebase or prior decisions.

## New Feature

1. Who is the primary user or consumer of this feature?
2. What is the core interaction or workflow?
3. Does this require new data models or changes to existing ones?
4. What API surface is needed (endpoints, events, messages)?
5. Does this touch the UI? If so, which parts?
6. What are the rollout constraints (feature flag, gradual rollout, big bang)?
7. Are there third-party integrations involved?
8. What are the edge cases or failure modes?
9. What observability is needed (logging, metrics, alerts)?
10. How should this be tested end-to-end?

## Refactor

1. What is the motivation (tech debt, performance, maintainability, team understanding)?
2. What are the boundaries of the refactor (which modules, layers, or files)?
3. What must not change (public API contracts, behavior, external interfaces)?
4. Is backwards compatibility required during the transition?
5. Can this be done incrementally or does it require a big-bang switch?
6. What is the risk of regression? Which areas are most fragile?
7. Are there existing tests that will catch regressions?
8. What patterns should the refactored code follow?

## Test Improvement

1. What is the current state of test coverage? Where are the gaps?
2. What type of tests are needed (unit, integration, e2e, performance)?
3. What test infrastructure exists (frameworks, fixtures, factories, CI)?
4. Are there flaky tests that need to be addressed first?
5. What coverage target are you aiming for?
6. Should tests be added alongside existing code or as a separate effort?
7. Are there testing patterns or conventions the team follows?

## Migration

1. What is the source and target (versions, systems, schemas)?
2. Is this a data migration, code migration, or both?
3. What is the data volume and expected migration duration?
4. What is the rollback strategy if something goes wrong?
5. Is zero-downtime required?
6. How will you verify data integrity after migration?
7. Are there dependent systems that need to be coordinated?
8. What is the cutover strategy (dual-write, blue-green, shadow)?

## Bug Fix

1. Can you reproduce the bug reliably? What are the reproduction steps?
2. What is the root cause (or best hypothesis)?
3. What is the blast radius (who/what is affected)?
4. Is there a workaround currently in place?
5. What should the correct behavior be?
6. What regression test will prevent this from recurring?
7. Are there related bugs or symptoms that might share the same root cause?

## Infrastructure

1. What infrastructure component is being changed (CI, deployment, networking, storage)?
2. What is the reliability or availability target?
3. What observability exists today? What needs to be added?
4. What are the scaling requirements (current and projected)?
5. What are the cost implications?
6. What security considerations apply?
7. What is the rollback strategy?
8. Who needs to be notified or coordinated with?

## Documentation Update

1. Who is the target audience (developers, users, ops, new team members)?
2. What is the scope (API docs, architecture guides, runbooks, onboarding)?
3. What format should the docs follow (existing conventions, new structure)?
4. Are there existing docs that need updating vs net-new docs?
5. How will the docs be maintained going forward?
6. Are there diagrams or visual aids needed?

## Performance Improvement

1. What is the bottleneck (CPU, memory, I/O, network, database)?
2. How is performance currently measured? What tools are available?
3. What are the target metrics (latency p50/p95/p99, throughput, resource usage)?
4. What tradeoffs are acceptable (memory vs speed, complexity vs performance)?
5. Is this a hot path that affects all users or a specific scenario?
6. Are there existing benchmarks or load tests?
7. What is the baseline measurement before changes?

## Dependency Updates

1. What is the motivation (security, features, deprecation, compatibility)?
2. Which dependencies are being updated and to what versions?
3. Are there breaking changes in the target versions?
4. What is the testing strategy to catch regressions?
5. Can dependencies be updated incrementally or must they be batched?
6. What is the rollback strategy?
7. Are there transitive dependency conflicts?

## Security Analysis

1. What is the threat model (who are the adversaries, what are they after)?
2. What is the attack surface (public APIs, user input, file uploads, auth flows)?
3. Are there compliance requirements (SOC2, GDPR, PCI-DSS, HIPAA)?
4. What security tooling is already in place (SAST, DAST, dependency scanning)?
5. What is the priority: find issues, remediate known issues, or both?
6. Are there known vulnerabilities or recent incidents driving this?
7. What is the remediation timeline and severity threshold?
