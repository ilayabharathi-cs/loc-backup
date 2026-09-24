# RetroVault V11 Testing & Quality Assurance Guide

## Test Architecture
RetroVault V11 features comprehensive multi-layered test coverage:
1. **Regression Suite**: Full V1–V10 regression suites (94 tests) + V10 46-step live E2E runner.
2. **V11 Unit & Integration Suite**: 16 dedicated unit and API tests in `server/tests/`.
3. **V11 Live E2E Suite**: 60-scenario comprehensive live validation script (`test_v11_application_aware_recovery.py`).

## Running Test Suites

### 1. Run Complete Pytest Suite (110 Tests)
```powershell
& server\.venv\Scripts\python.exe -m pytest server/tests
```
Expected: `110 passed`

### 2. Run V11 Live End-to-End Suite (60 Scenarios)
```powershell
& server\.venv\Scripts\python.exe test_v11_application_aware_recovery.py
```
Expected: `60 Passed, 0 Failed out of 60 Scenarios`

### 3. Run V10 Operational Intelligence Regression Suite (46 Steps)
```powershell
& server\.venv\Scripts\python.exe test_v10_operational_intelligence.py
```
Expected: `46/46 STEPS PASSED (100%)`

### 4. Build Frontend UI
```powershell
npm run build
```
Expected: `✓ built in ~600ms` with zero TypeScript or packaging errors.
