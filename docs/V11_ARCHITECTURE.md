# RetroVault V11 Architecture: Application-Aware Data Protection & Automated Recovery

## Executive Overview
RetroVault V11 elevates the platform from an enterprise file-level backup system (V1–V10) to a capability-driven, application-aware data protection and automated recovery platform. V11 introduces plugin-based workload providers, factual evidence-based application consistency classification, synthetic sandbox restore verification, objective recovery readiness intelligence, and audited policy lifecycle orchestration.

## Core Architectural Invariants
1. **Local-First & Repository Decoupling**: Repository storage data remains outside the metadata database, physical blocks are stored exclusively via CAS (Content-Addressed Storage), and Recovery Point manifests serve as the logical source of truth.
2. **PostgreSQL / SQLite Storage Engine**: PostgreSQL serves as the production metadata store while SQLite remains fully supported for development and offline testing.
3. **Additive System Schema**: V11 does not alter or disrupt existing V1–V10 tables, jobs, or configurations.
4. **No Destructive Autonomous Actions**: Automated operations never delete Recovery Points, bypass CAS retention locks, or disable ransomware protection holds.
5. **Evidence-Based Consistency**: Recovery Points are never classified as `APPLICATION_CONSISTENT` without verifiable evidence (such as verified LSN headers, VSS SQL Writer freeze proof, or database transaction dumps).

## Component Flow & Topology

```mermaid
graph TD
    Client[Universal Protected Client] --> Scanner[Workload Scanner / Discovery]
    Scanner --> WorkloadDB[(Workloads DB)]
    
    subgraph "Workload Protection Pipeline"
        WorkloadDB --> PreHook[Pre-Snapshot Hook]
        PreHook --> Quiesce[Quiesce / App Freeze]
        Quiesce --> Snapshot[Snapshot / Artifact Generation]
        Snapshot --> Unquiesce[Unquiesce / App Thaw]
        Unquiesce --> PostHook[Post-Snapshot Hook]
        PostHook --> VerifyConsist[Consistency Verification]
        VerifyConsist --> CAS[Content-Addressed Storage / SHA-256]
        CAS --> RP[Recovery Point Manifest]
    end

    subgraph "Automated Recovery & Verification"
        RP --> VerifScheduler[Verification Engine]
        VerifScheduler --> Sandbox[Isolated Restore Sandbox]
        Sandbox --> ChecksumTest[CAS Checksum & Payload Test]
        ChecksumTest --> VerifResult[Recovery Verification Record]
    end

    subgraph "Governance & Orchestration"
        RP --> Readiness[Factual Readiness Engine (11 Signals)]
        Readiness --> Compliance[Compliance Evidence]
        Policy[Policy Orchestrator] --> ApprovalGate[Approval Gates]
        ApprovalGate --> ActivePolicy[Active Policy Version]
    end
```

## Capability Matrix

| Capability | Status | Implementation Detail |
|---|---|---|
| Windows Filesystem (VSS/USN) | **SUPPORTED** | Volume freeze/thaw, shadow copy emulation, NTFS USN delta tracking |
| Microsoft SQL Server (Full & Log) | **SUPPORTED** | Instance & DB discovery, VSS SQL Writer freeze, LSN continuity tracking |
| PostgreSQL (Logical & Streaming) | **SUPPORTED** | Database discovery, MVCC transaction isolation, WAL LSN tracking |
| Generic Application Protection | **SUPPORTED** | Safe hooks, strict binary allow-list, injection prevention, timeouts |
| Synthetic Restore Verification | **SUPPORTED** | Isolated sandbox extraction, zero production data modification |
| Backup Chain Integrity Engine | **SUPPORTED** | Detection of missing baselines, corrupted blocks, broken LSN chains |
| Factual Recovery Readiness | **SUPPORTED** | Transparent calculation across 11 measurable telemetry signals |
| Policy Lifecycle & Rollback | **SUPPORTED** | Versioning (DRAFT -> APPROVED -> ACTIVE -> RETIRED), rollback to prior versions |
| Safe Remediation Workflows | **SUPPORTED** | Dual-approval gating, auditable execution, rejection of destructive calls |
| Dependency Graph Safety | **SUPPORTED** | Prevents deletion of CAS blocks or workloads with active dependents |
| Arbitrary Remote Shell Commands | **UNSUPPORTED** | Intentionally blocked by security design; strict parameterized allow-list only |
| Physical Cross-Version DB Downgrades | **UNSUPPORTED** | Restoration across incompatible database major versions is rejected |
