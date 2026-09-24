# RetroVault Backup Engine — V10: Storage Capacity Intelligence & Forecasting

## 1. Capacity Intelligence Engine

The `CapacityPlanningService` in `server/app/services/observability/capacity_service.py` tracks factual storage utilization across all storage repositories.

### Monitored Metrics
- **Logical Bytes**: Uncompressed, pre-deduplicated volume of client files protected.
- **Unique Content Bytes**: De-duplicated unique content payload size.
- **Compressed Bytes**: Volume of data after streaming block compression.
- **Physical Bytes**: Physical disk footprint consumed on underlying storage devices.
- **Free Bytes**: Remaining unallocated capacity available in the repository.
- **Total Capacity Bytes**: Maximum usable boundary of the repository.
- **Deduplication Ratio**: $\frac{\text{Logical Bytes}}{\text{Unique Content Bytes}}$
- **Compression Ratio**: $\frac{\text{Unique Content Bytes}}{\text{Compressed Bytes}}$
- **Overall Storage Efficiency**: $\frac{\text{Logical Bytes}}{\text{Physical Bytes}}$

---

## 2. Mathematical Forecasting Methodology

Forecasts are computed strictly using reproducible statistical methods. **No external LLM or speculative extrapolation is used.**

### Linear Regression Formulation
For historical capacity snapshots $(t_i, y_i)$ where $t_i$ is time (in fractional days) and $y_i$ is physical bytes used:

$$\text{Slope } m = \frac{N \sum (t_i y_i) - \sum t_i \sum y_i}{N \sum (t_i^2) - (\sum t_i)^2}$$

$$\text{Intercept } c = \frac{\sum y_i - m \sum t_i}{N}$$

### Projected Physical Usage
$$\hat{y}(t) = \max(0, m \cdot t + c)$$

The engine calculates projected storage consumption for horizons:
- **7-Day Projection**: $t = t_{\text{current}} + 7$
- **30-Day Projection**: $t = t_{\text{current}} + 30$
- **90-Day Projection**: $t = t_{\text{current}} + 90$

### Estimated Depletion Date
If $m > 0$ (positive daily growth):
$$\text{Days to Depletion} = \frac{\text{Total Capacity} - y_{\text{current}}}{m}$$
$$\text{Depletion Date} = t_{\text{current}} + \text{Days to Depletion}$$

### Uncertainty & Confidence ($R^2$)
Confidence is expressed through the Pearson coefficient of determination ($R^2$):
$$R^2 = 1 - \frac{\sum (y_i - \hat{y}_i)^2}{\sum (y_i - \bar{y})^2}$$

---

## 3. Strict Insufficient Data Handling

> [!IMPORTANT]
> **Deterministic Guardrail**: If fewer than 3 historical snapshots exist in the evaluation window, the forecasting engine strictly refuses to extrapolate.

When samples $< 3$:
- `status`: `"INSUFFICIENT_DATA"`
- `confidence_r_squared`: `0.0`
- `estimated_depletion_date`: `None`
- `forecast_7d_bytes`: `None`
- `explanation`: `"Insufficient historical snapshots (found N, minimum required: 3) to generate statistically valid linear trend projection."`

---

## 4. Auditable Projection Disclaimer

All forecasts stored in `capacity_forecasts` and returned via `/api/v1/capacity/forecast` include:
```json
{
  "is_projection": true,
  "disclaimer": "PROJECTION: Mathematical projection based on linear regression of historical telemetry. Actual consumption may vary based on backup frequency, deduplication variability, and file churn."
}
```
This guarantees administrative clarity and prevents presenting mathematical projections as guaranteed capacities.
