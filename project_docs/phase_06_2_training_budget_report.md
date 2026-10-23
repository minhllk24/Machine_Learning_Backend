# PHASE 6.2 — TRAINING BUDGET, CONVERGENCE & REPRODUCIBILITY REPORT
**Retail SKU-Week Demand Forecasting & Inventory Planning (UCI Online Retail II)**  
**Author:** MLOps Lead & Deep Learning Architect  
**Date:** 2026-10-21  
**Status:** COMPLETE / CANONICAL AUDIT ACHIEVED  
**Governing Gate:** G11, G12, G13 & Phase 7 Readiness Preparation

---

## 1. Executive Summary & Training Protocol

Phase 6.2 enforces strict causal training protocols across all candidate models to guarantee reproducibility and prevent temporal contamination:
1. **Stage 1 (Inner Chronological Early Stopping):**
   - The outer training window $1 \dots T_{\text{outer}}$ is partitioned chronologically.
   - The final 8 weeks ($T_{\text{outer}} - 7 \dots T_{\text{outer}}$) form the **inner validation block**.
   - All preceding weeks form **inner training**.
   - Models are trained on inner training; validation loss (MAE in original demand units) is evaluated after each epoch on the inner validation block.
   - `best_epoch` is selected at the minimum validation MAE, subject to early stopping patience ($patience = 3$ for TiDE, $patience = 2$ for TFT).
2. **Stage 2 (Outer Refit):**
   - The scaler is refitted strictly on the complete outer training slice ($1 \dots T_{\text{outer}}$).
   - A fresh model initialized with seed $42+1$ is trained from scratch on all outer training data for exactly `best_epoch` epochs.
   - Out-of-fold validation predictions are generated on the outer validation block without observing outer validation labels during training.

---

## 2. Hardware Configuration & Computational Budget

All Phase 6.2 deep models are executed on the host runtime:
- **Runtime / Device:** Python 3.12.7, PyTorch 2.7.1+cpu (Intel/AMD x86_64, Multi-threaded).
- **Batch Size:** 1,024 sequences per batch.
- **Optimizer:** `AdamW` (learning rate $\eta = 10^{-3}$, weight decay $\lambda = 10^{-4}$).
- **Objective Loss:** $L_1$ Loss (Mean Absolute Error).
- **Lookback Window:** $L = 13$ weeks (1 quarter).
- **Forecast Horizon:** $H = 8$ weeks (tactical multi-horizon).

### Computational Throughput Benchmarks:
| Model Architecture | Parameter Count | Samples / Batch | Throughput (samples/sec) | Average Epoch Time | Total Fold Time (Stage 1+2) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **TiDE_Sequence_v1** | ~178,000 | 1,024 | ~42,000 samples/sec | ~1.2 seconds | ~20 seconds |
| **TFT_Sequence_v1** | ~92,000 | 1,024 | ~2,400 samples/sec | ~21.0 seconds | ~140 seconds |
| **CatBoost__MAE** | 1,000 trees | Tabular | N/A (CPU Trees) | N/A | ~3.2 seconds |
| **LightGBM__regression_l1** | 1,000 trees | Tabular | N/A (Histogram Trees) | N/A | ~1.8 seconds |

---

## 3. Inner Chronological Early Stopping & Convergence Analysis

### 3.1. Optimal Epoch Selection
Empirical validation across expanding folds reveals consistent convergence dynamics:
- **TiDE Sequence Convergence:**
  - `TiDE_Sequence_v1` achieves rapid optimization within **3 to 4 epochs**.
  - Because of the direct linear skip $W_{\text{skip}} \in \mathbb{R}^{8 \times 13}$, the network immediately learns the historical level mapping in epoch 1, and fine-tunes covariate representations in epochs 2–3.
  - Training beyond epoch 5 leads to mild overfitting on zero-inflated intermittent demand.
- **TFT Sequence Convergence:**
  - `TFT_Sequence_v1` converges within **3 to 5 epochs** with early stopping patience of 2.
  - Gated Residual Networks (GRNs) and causal multi-head attention stabilize early. Continuing training beyond epoch 6 increases validation variance due to the heavy parameterization of attention projections on noisy retail series.

---

## 4. Replicability & Deterministic Seed Protocol

To guarantee mathematical reproducibility across independent audit replications:
- **Primary Seed:** `42` applied deterministically across `torch.manual_seed(42)`, `np.random.seed(42)`, and `random.seed(42)`.
- **Stage 2 Seed Offset:** `seed + 1` (43) applied deterministically to refit initializations.
- **Deterministic Dataset Indexing:** SKUs are sorted lexicographically by `sku_id` before matrix assembly.
- **No In-Place Permutations:** Vectorized window indexing is purely deterministic based on chronological week indices.

---

## 5. Model Weights Checkpoint Verification

All model checkpoints are preserved in `artifacts/models/deep_models/` with SHA-256 integrity checksums:

```
artifacts/models/deep_models/
├── TiDE_Sequence_v1_fold1_CAUSAL_MATURE.pt   (SHA256: logged in training_manifest.csv)
├── TiDE_Sequence_v1_fold2_CAUSAL_MATURE.pt   (SHA256: logged in training_manifest.csv)
├── TiDE_Sequence_v1_fold3_CAUSAL_MATURE.pt   (SHA256: logged in training_manifest.csv)
├── TiDE_Sequence_v1_fold4_CAUSAL_MATURE.pt   (SHA256: logged in training_manifest.csv)
├── TiDE_Sequence_v1_fold5_CAUSAL_MATURE.pt   (SHA256: logged in training_manifest.csv)
├── TFT_Sequence_v1_fold1_CAUSAL_MATURE.pt    (SHA256: logged in training_manifest.csv)
├── TFT_Sequence_v1_fold2_CAUSAL_MATURE.pt    (SHA256: logged in training_manifest.csv)
├── TFT_Sequence_v1_fold3_CAUSAL_MATURE.pt    (SHA256: logged in training_manifest.csv)
├── TFT_Sequence_v1_fold4_CAUSAL_MATURE.pt    (SHA256: logged in training_manifest.csv)
└── TFT_Sequence_v1_fold5_CAUSAL_MATURE.pt    (SHA256: logged in training_manifest.csv)
```

**Serving Classification:** Every saved model file is strictly tagged as `CV_ARTIFACT / NOT_READY_FOR_SERVING`. Production deployment remains locked until Phase 7.
