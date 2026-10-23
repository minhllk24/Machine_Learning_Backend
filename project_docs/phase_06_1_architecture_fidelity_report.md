# PHASE 6.1 AUDIT REPORT: ARCHITECTURE FIDELITY FOR TiDE & TFT

**Project:** Retail SKU-Week Demand Forecasting & Inventory Planning  
**Execution Date:** 2026-10-21  
**Auditor Roles:** Senior ML Research Engineer, Time-Series Researcher, Applied Statistician & MLOps Lead  
**Governing Gate Target:** Gates G11 (TiDE Fidelity) and G12 (TFT Fidelity)  
**Status:** **PARTIAL (Re-classified as Tabular-Adapted Architectures)**  

---

## 1. Executive Summary & Audit Intent

In Phase 6, two neural forecasting architectures—**TiDE (Time-series Dense Encoder)** and **TFT (Temporal Fusion Transformer)**—were implemented in native PyTorch (`src/models/tide.py` and `src/models/tft.py`) and evaluated on the 5 expanding-window folds. Both models achieved substantial empirical gains over statistical baselines (e.g., TiDE achieved 69.75% WAPE vs 76.75% for MA_4).

However, an rigorous academic audit requires distinguishing between a **canonical reproduction of the published literature** and a **tabular architecture inspired by the paper's core ideas**. 

This audit compares the physical code, tensor dimensions, and forward execution paths in `src/models/tide.py` and `src/models/tft.py` against the foundational papers:
1. **TiDE:** Das, Abhimanyu, Weihao Kong, Andrew Leach, Shreshth Mathur, Rajat Sen, and Rose Yu. *"Long-term Forecasting with TiDE: Time-series Dense Encoder."* Transactions on Machine Learning Research (TMLR), 2023. arXiv:2304.08424. Google Research.
2. **TFT:** Lim, Bryan, Sercan Ö. Arık, Nicolas Loeff, and Tomas Pfister. *"Temporal Fusion Transformers for Interpretable Multi-horizon Time Series Forecasting."* International Journal of Forecasting 37, no. 4 (2021): 1748–1764. DOI: 10.1016/j.ijforecast.2021.03.012. Google Cloud AI.

---

## 2. TiDE Architecture Fidelity Audit

### 2.1. Canonical Literature Specifications (Das et al., 2023)
In Das et al. (2023), TiDE is designed as a direct multi-horizon time-series forecasting model:
- **Lookback Input:** Continuous historical target trajectory $y_{t-L:t-1} \in \mathbb{R}^L$ for lookback window $L$.
- **Dynamic Covariates:** Time-varying past and future covariates $x \in \mathbb{R}^{(L+H) \times r}$, projected down per time-step using a shared feature projection MLP.
- **Flattened Representation:** The lookback vector $y_{1:L}$, static attributes $s$, and projected dynamic covariates are flattened into a single feature vector.
- **Dense Residual Encoder:** A stack of Dense Residual Blocks:
  $$\text{Block}(x) = x + \text{Linear}(\text{Dropout}(\text{ReLU}(\text{Linear}(\text{LayerNorm}(x)))))$$
- **Dense Decoder:** Projects the latent embedding $e \in \mathbb{R}^d$ into a multi-horizon matrix $D \in \mathbb{R}^{H \times p}$.
- **Global Residual Skip:** Direct linear connection from past targets $y_{t-L:t-1}$ to the future predictions $\hat{y}_{\text{skip}} = W_{\text{skip}} y_{t-L:t-1} \in \mathbb{R}^H$.

### 2.2. Inspection of `src/models/tide.py`
Audit of physical lines 13–106 in `src/models/tide.py`:
- **Input Tensor Geometry:** Accepts $x \in \mathbb{R}^{B \times 71}$, where the 71 features represent a single tabular row (already engineered lags, rolling statistics, calendar indicators, and price signals).
- **Residual Blocks (`TiDEResidualBlock`):** Exactly implements the canonical LayerNorm $\to$ Linear $\to$ ReLU $\to$ Dropout $\to$ Linear with additive residual connection.
- **Decoder:** Projects `(B, 128) -> (B, 64) -> (B, 1)` scalar output ($H=1$).
- **Global Skip:** Implements `nn.Linear(1, 1)` mapping `demand_lag_1` (feature index 0) directly to output: $\hat{y} = \text{Decoder}(h) + w_{\text{skip}} y_{t-1} + b_{\text{skip}}$.

### 2.3. Fidelity Findings for TiDE
1. **Tabular Adaptation:** The model operates on pre-computed tabular rows ($B \times 71$) rather than raw 1D lookback histories ($B \times L$).
2. **Simplified Skip:** The global skip operates on a single primary lag ($y_{t-1}$) rather than the full historical vector ($y_{t-L:t-1}$).
3. **Empirical Justification:** This skip connection acts as a direct learnable anchor to the persistence baseline (Naive_1), which explains why TiDE outperformed TFT and approached tree model performance on retail demand.
4. **Fidelity Classification:** **`TiDE-inspired Tabular Dense Residual Network with Global Skip`**.

---

## 3. TFT Architecture Fidelity Audit

### 3.1. Canonical Literature Specifications (Lim et al., 2021)
In Lim et al. (2021), TFT combines several specialized components:
1. **Static Covariate Encoders:** Maps static metadata to context vectors used across the network.
2. **Variable Selection Networks (VSN):** Applied at **each individual time step $t$** across all individual feature variables $j \in \{1..D\}$. Each feature has its own dedicated GRN; a selection GRN computes Softmax weights across variables at each time step.
3. **Recurrent Temporal Processing:** Seq2seq LSTM layer across time steps $1..L+H$ to capture localized sequential patterns.
4. **Interpretable Multi-Head Self-Attention:** Self-attention across **time steps** $(1..L+H)$ with causal masking to capture long-range temporal dependencies.
5. **Gated Temporal Fusion:** Gated Residual Networks (GRNs) applied post-attention.
6. **Multi-Horizon Quantile Outputs:** Predicts 10th, 50th, and 90th percentiles for horizons $t=L+1..L+H$.

### 3.2. Inspection of `src/models/tft.py`
Audit of physical lines 20–202 in `src/models/tft.py`:
- **Gated Residual Network (`GatedResidualNetwork`):** Fully faithful implementation of Lim et al. (2021) Section 3.1.2:
  $$\text{GRN}(a, c) = \text{LayerNorm}(\text{skip}(a) + \text{GLU}(\text{Dropout}(\text{ELU}(\text{Linear}(a) + \text{Linear}(c)))))$$
- **Variable Selection Network (`VariableSelectionNetwork`):**
  - Features are partitioned into 4 pre-defined semantic domains: Demand Dynamics (45), Intermittency (11), Calendar (10), Price (5).
  - Dedicated GRNs process each domain tensor; a selection GRN computes Softmax weights across the 4 groups.
  - *Deviation:* VSN selects across 4 coarse semantic groups rather than individual variables, and operates on a 2D tabular row rather than across a 3D temporal sequence.
- **Interpretable Multi-Head Self-Attention (`InterpretableMultiHeadAttention`):**
  - Audit of lines 139–140:
    ```python
    x_seq = x.unsqueeze(1)
    B, S, D = x_seq.shape # S = 1
    ```
  - **CRITICAL AUDIT FINDING:** Because the model receives a single tabular row, sequence length $S = 1$. When $S = 1$, the attention score matrix $Q K^T / \sqrt{d}$ is a $1 \times 1$ scalar!
  - Softmax over a $1 \times 1$ scalar evaluates trivially to **$1.0$** (constant identity).
  - Consequently, **no temporal self-attention across time steps is performed**. The attention module acts strictly as a static multi-head linear transformation followed by GLU gating.
- **Recurrent Layer:** Zero LSTM or RNN layers are present.
- **Output:** Point forecast scalar ($H=1$) optimizing L1 loss (MAE), with no quantile heads.

### 3.3. Fidelity Findings for TFT
1. **Degenerate Attention:** Feeding 2D tabular rows ($B \times 71$) collapsed temporal self-attention to a scalar identity operation ($S=1$).
2. **Absence of Recurrence:** Omission of seq2seq LSTM removes the primary inductive bias for local temporal autocorrelation.
3. **Gating Bias:** The stacked GRN and GLU gating heavily squashed predictions toward zero on intermittent series, creating severe negative forecast bias ($-52.98\%$).
4. **Fidelity Classification:** **`TFT-inspired Gated Tabular Network with Semantic VSN`**.

---

## 4. Architecture Fidelity Matrix

The complete component-by-component comparison is serialized in [`artifacts/tables/phase_06_1_architecture_fidelity_matrix.csv`](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/artifacts/tables/phase_06_1_architecture_fidelity_matrix.csv):

| Model | Required Canonical Component | Current Implementation | Status | Research Impact |
|---|---|---|:---:|---|
| **TiDE** | Lookback Window & Target History | `x: (B, 71)` tabular row | `DEVIATION` | Uses discrete pre-engineered lags instead of continuous 1D trajectory. |
| **TiDE** | Dynamic Covariates Projection | `Linear(71, 128)` in `feature_encoder` | `PARTIAL` | Single MLP projection conflates temporal and cross-feature dimensions. |
| **TiDE** | Stack of Dense Residual Blocks | `TiDEResidualBlock` (2 layers) | **`FULL`** | Exact match with Das et al. (2023) residual block formulation. |
| **TiDE** | Dense Decoder | `Linear(128, 64) -> Linear(64, 1)` | `DEVIATION` | Point forecast scalar ($H=1$) rather than direct multi-horizon matrix. |
| **TiDE** | Global Residual Skip | `Linear(1, 1)` on `demand_lag_1` | `SIMPLIFIED` | Operates on single primary lag rather than full lookback vector. |
| **TFT** | Gated Residual Network (GRN) | `GatedResidualNetwork` with GLU | **`FULL`** | Exact match with Lim et al. (2021) gating equations. |
| **TFT** | Variable Selection Network | 4 semantic group GRNs | `DEVIATION` | Selects across 4 feature domains rather than 71 individual variables. |
| **TFT** | Recurrent Temporal Processing | None | `OMITTED` | No LSTM seq2seq layer; relies on pre-engineered rolling features. |
| **TFT** | Interpretable Attention | Attention over $S=1$ sequence | `DEGENERATE` | $1 \times 1$ attention matrix trivially evaluates to identity weight 1.0. |
| **TFT** | Quantile Multi-Horizon Output | Single linear projection | `DEVIATION` | Point forecast scalar under L1 loss; no quantile distribution heads. |

---

## 5. Governance Decision & Gate Adjustments

1. **Re-titling Models:**
   - In all future benchmarks, reports, and registry entries, the candidate models MUST be formally named:
     - `TiDE-inspired__primary_config` (or `TiDE-inspired Tabular Dense Residual Network`)
     - `TFT-inspired__primary_config` (or `TFT-inspired Gated Tabular Network`)
   - The project shall NOT claim to have established a definitive benchmark of canonical 3D temporal-window TiDE or TFT.
2. **Gate Adjustments:**
   - **Gate G11 (TiDE):** Adjusted from `PASS` to **`PARTIAL (Tabular-Adapted Implementation Verified)`**.
   - **Gate G12 (TFT):** Adjusted from `PASS` to **`PARTIAL (Tabular-Adapted Implementation Verified; Degenerate Attention Noted)`**.
3. **Scientific Value:** This re-classification preserves scientific integrity. It explains why TiDE outperformed TFT (due to the explicit linear skip from $y_{t-1}$) and why both underperformed GBDTs (due to global scaling requirements and the loss of tree-based orthogonal partitioning on tabular retail features).
