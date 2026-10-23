"""
TiDE: Time-series Dense Encoder (PyTorch Implementation).
Reference: Das et al. (2023), "Long-term Forecasting with TiDE: Time-series Dense Encoder"
Google Research / Transactions on Machine Learning Research (TMLR).

Adapted for Retail SKU-Week Demand Forecasting with Causal Tabular Features.
"""
from typing import Dict, Any, Optional
import torch
import torch.nn as nn


class TiDEResidualBlock(nn.Module):
    """
    Residual Block with LayerNorm, Linear, ReLU, Dropout, Linear, and Skip Connection.
    """
    def __init__(self, hidden_dim: int, dropout: float = 0.1):
        super().__init__()
        self.norm = nn.LayerNorm(hidden_dim)
        self.linear1 = nn.Linear(hidden_dim, hidden_dim)
        self.act = nn.ReLU()
        self.drop = nn.Dropout(dropout)
        self.linear2 = nn.Linear(hidden_dim, hidden_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        residual = x
        out = self.norm(x)
        out = self.linear1(out)
        out = self.act(out)
        out = self.drop(out)
        out = self.linear2(out)
        return residual + out


class TiDEModel(nn.Module):
    """
    TiDE Model Architecture.
    - Feature Projection Encoder: Projects input features to hidden_dim.
    - Stack of Dense Residual Blocks: Deep non-linear representation.
    - Dense Decoder: Projects hidden state to demand prediction.
    - Global Residual Skip: Linear connection from key historical demand lag directly to output.
    """
    def __init__(
        self,
        in_dim: int = 71,
        hidden_dim: int = 128,
        num_encoder_layers: int = 2,
        decoder_dim: int = 64,
        dropout: float = 0.1,
        primary_lag_idx: int = 0  # index of demand_lag_1 in allowlist
    ):
        super().__init__()
        self.in_dim = in_dim
        self.hidden_dim = hidden_dim
        self.primary_lag_idx = primary_lag_idx

        # 1. Feature projection
        self.feature_encoder = nn.Sequential(
            nn.Linear(in_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout)
        )

        # 2. Residual blocks
        self.encoder_blocks = nn.ModuleList([
            TiDEResidualBlock(hidden_dim, dropout=dropout)
            for _ in range(num_encoder_layers)
        ])

        # 3. Dense decoder
        self.decoder = nn.Sequential(
            nn.LayerNorm(hidden_dim),
            nn.Linear(hidden_dim, decoder_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(decoder_dim, 1)
        )

        # 4. Global residual skip connection from primary lag (demand_lag_1)
        self.global_skip = nn.Linear(1, 1, bias=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.
        Args:
            x: Input feature tensor of shape (batch_size, in_dim)
        Returns:
            Tensor of shape (batch_size,)
        """
        # Feature projection
        h = self.feature_encoder(x)

        # Residual encoder blocks
        for block in self.encoder_blocks:
            h = block(h)

        # Decoder prediction
        pred_main = self.decoder(h).squeeze(-1)

        # Global skip connection from primary lag (demand_lag_1)
        lag1 = x[:, self.primary_lag_idx:self.primary_lag_idx + 1]
        skip_out = self.global_skip(lag1).squeeze(-1)

        return pred_main + skip_out


def create_tide_primary_config(in_dim: int = 71, primary_lag_idx: int = 0) -> Dict[str, Any]:
    """
    Returns the pre-registered configuration dictionary for TiDE__primary_config.
    """
    return {
        "model_name": "TiDE__primary_config",
        "family": "TiDE",
        "objective": "L1_MAE",
        "eval_metric": "MAE",
        "hyperparameters": {
            "in_dim": in_dim,
            "hidden_dim": 128,
            "num_encoder_layers": 2,
            "decoder_dim": 64,
            "dropout": 0.1,
            "primary_lag_idx": primary_lag_idx,
            "lr": 1e-3,
            "weight_decay": 1e-4,
            "batch_size": 2048,
            "max_epochs": 15,
            "early_stopping_patience": 3,
            "seed": 42
        }
    }
