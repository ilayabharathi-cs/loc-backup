# RetroVault V11 Policy Orchestration & Lifecycle Governance

## Overview
RetroVault V11 replaces mutable policy editing with immutable versioning and audited lifecycle governance. Policies are never silently modified in-place while active.

## Lifecycle States
1. `DRAFT`: Newly proposed policy version. Has no operational effect on running backup jobs.
2. `VALIDATING`: System executes pre-flight checks and calculates affected clients/workloads.
3. `APPROVED`: Formally signed off by an authorized administrator or security officer.
4. `ACTIVE`: Promoted to production enforcement. Replaces previous active version.
5. `SUSPENDED`: Temporarily halted by administrative action.
6. `RETIRED`: Deprecated version superseded by a newer active version.

## Deterministic Impact Analysis
The `calculate_affected_resources(policy_id)` service calculates:
- Exact list and count of affected workloads (`workload_ids`).
- Exact list and count of affected clients (`client_ids`).
- Historical runs affected by the policy change.

## Policy Rollback Workflow
When a regression occurs, administrators trigger deterministic rollback:
1. Target historical version `vX` is retrieved.
2. A new version `v(N+1)` is created containing the exact configuration of `vX`.
3. The new version is approved and activated with full audit logging:
   `action="POLICY_ROLLED_BACK", details="Rolled back policy to configuration of vX as new v(N+1)"`.
