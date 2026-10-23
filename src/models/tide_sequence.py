"""
TiDE Sequence Model (Canonical Temporal Architecture).
Reference: Das et al. (2023), "Long-term Forecasting with TiDE: Time-series Dense Encoder"
Transactions on Machine Learning Research (TMLR) / Google Research. arXiv:2304.08424.

Implements the canonical multi-horizon time-series dense encoder:
1. Dynamic covariate projection across time steps.
2. Flattened dense residual encoder.
3. Multi-horizon dense decoder.
4. Global linear residual skip connection from past target sequence y_{1:L} to future horizons y_{1:H}.
"""
from typing import Dict, Any, Optional
import torch
import torch.nn as nn


class TiDEResidualBlock(nn.Module):
    """
    Residual Block with LayerNorm, Linear, ReLU, Dropout, Linear, and additive skip connection.
    ResidualBlock(x) = x + Linear(Dropout(ReLU(Linear(LayerNorm(x)))))
    """
    def __init__(self, hidden_dim: int, dropout: float = 0.1):
        super().__init__()
        self.norm = nn.LayerNorm(hidden_dim)
        self.linear1 = nn.Linear(hidden_dim, hidden_dim)
        self.act = nn.ReLU()
        self.drop = nn.Dropout(dropout)
        self.linear2 = nn.Linear(hidden_dim, hidden_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        res = x
        out = self.norm(x)
        out = self.linear1(out)
        out = self.act(out)
        out = self.drop(out)
        out = self.linear2(out)
        return res + out


class TiDESequenceModel(nn.Module):
    """
    Canonical TiDE Architecture for multi-horizon retail demand forecasting.
    
    Inputs:
      - past_targets: (B, L) historical demand sequence
      - past_covariates: (B, L, d_past) dynamic historical covariates (e.g. price, promo, lags)
      - future_covariates: (B, H, d_future) known future calendar/holiday covariates
    
    Output:
      - predictions: (B, H) direct multi-horizon demand forecasts
    """
    def __init__(
        self,
        lookback_len: int = 13,
        horizon_len: int = 8,
        d_past_cov: int = 4,
        d_future_cov: int = 10,
        d_cov_proj: int = 16,
        hidden_dim: int = 128,
        num_encoder_layers: int = 2,
        decoder_dim: int = 64,
        dropout: float = 0.1
    ):
        super().__init__()
        self.lookback_len = lookback_len
        self.horizon_len = horizon_len
        self.d_past_cov = d_past_cov
        self.d_future_cov = d_future_cov
        self.d_cov_proj = d_cov_proj
        self.hidden_dim = hidden_dim

        # 1. Covariate projection MLPs (per timestep)
        if d_past_cov > 0:
            self.past_cov_proj = nn.Sequential(
                nn.Linear(d_past_cov, d_cov_proj),
                nn.ReLU()
            )
        else:
            self.past_cov_proj = None

        if d_future_cov > 0:
            self.future_cov_proj = nn.Sequential(
                nn.Linear(d_future_cov, d_cov_proj),
                nn.ReLU()
            )
        else:
            self.future_cov_proj = None

        # Calculate flattened encoder input dimension:
        # lookback_len targets + (lookback_len * d_cov_proj) + (horizon_len * d_cov_proj)
        total_encoder_in = lookback_len
        if d_past_cov > 0:
            total_encoder_in += lookback_len * d_cov_proj
        if d_future_cov > 0:
            total_encoder_in += horizon_len * d_cov_proj

        # 2. Dense feature encoder
        self.encoder_in_proj = nn.Linear(total_encoder_in, hidden_dim)
        self.encoder_blocks = nn.ModuleList([
            TiDEResidualBlock(hidden_dim, dropout=dropout)
            for _ in range(num_encoder_layers)
        ])

        # 3. Dense decoder
        # Maps hidden_dim -> horizon_len * decoder_dim, then projects per horizon step to 1
        self.decoder_proj = nn.Sequential(
            nn.LayerNorm(hidden_dim),
            nn.Linear(hidden_dim, horizon_len * decoder_dim),
            nn.ReLU(),
            nn.Dropout(dropout)
        )
        self.decoder_head = nn.Linear(decoder_dim, 1)

        # 4. Global Residual Skip Connection: Linear(lookback_len -> horizon_len)
        # Directly connects past target sequence to all forecast horizons
        self.global_skip = nn.Linear(lookback_len, horizon_len, bias=True)

    def forward(
        self,
        past_targets: torch.Tensor,
        past_covariates: Optional[torch.Tensor] = None,
        future_covariates: Optional[torch.Tensor] = None
    ) -> torch.Tensor:
        """
        Args:
            past_targets: (B, L)
            past_covariates: (B, L, d_past) or None
            future_covariates: (B, H, d_future) or None
        Returns:
            (B, H) predictions
        """
        B, L = past_targets.shape
        parts = [past_targets]

        if self.past_cov_proj is not None and past_covariates is not None:
            p_proj = self.past_cov_proj(past_covariates)  # (B, L, d_cov_proj)
            p_flat = p_proj.view(B, -1)                   # (B, L * d_cov_proj)
            parts.append(p_flat)

        if self.future_cov_proj is not None and future_covariates is not None:
            f_proj = self.future_cov_proj(future_covariates)  # (B, H, d_cov_proj)
            f_flat = f_proj.view(B, -1)                       # (B, H * d_cov_proj)
            parts.append(f_flat)

        # Concatenate lookback targets and projected dynamic covariates
        enc_in = torch.cat(parts, dim=-1)

        # Pass through Dense Encoder
        h = self.encoder_in_proj(enc_in)
        for block in self.encoder_blocks:
            h = block(h)

        # Dense Decoder: (B, H * decoder_dim) -> (B, H, decoder_dim) -> (B, H)
        dec_out = self.decoder_proj(h)
        dec_out = dec_out.view(B, self.horizon_len, -1)
        pred_dense = self.decoder_head(dec_out).squeeze(-1)  # (B, H)

        # Global linear skip from full lookback sequence y_{1:L}
        pred_skip = self.global_skip(past_targets)            # (B, H)

        return pred_dense + pred_skip


def create_tide_sequence_config(
    lookback_len: int = 13,
    horizon_len: int = 8,
    d_past_cov: int = 4,
    d_future_cov: int = 10
) -> Dict[str, Any]:
    """Pre-registered configuration for TiDE_Sequence_v1."""
    return {
        "model_name": "TiDE_Sequence_v1",
        "family": "TiDE_Canonical",
        "objective": "L1_MAE",
        "eval_metric": "MAE",
        "architecture_type": "TEMPORAL_SEQUENCE_CANONICAL",
        "hyperparameters": {
            "lookback_len": lookback_len,
            "horizon_len": horizon_len,
            "d_past_cov": d_past_cov,
            "d_future_cov": d_future_cov,
            "d_cov_proj": 16,
            "hidden_dim": 128,
            "num_encoder_layers": 2,
            "decoder_dim": 64,
            "dropout": 0.1,
            "lr": 1e-3,
            "weight_decay": 1e-4,
            "batch_size": 1024,
            "max_epochs": 20,
            "early_stopping_patience": 4,
            "seed": 42
        }
    }
