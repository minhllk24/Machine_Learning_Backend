"""
Temporal Fusion Transformer (TFT) PyTorch Implementation.
Reference: Lim et al. (2021), "Temporal Fusion Transformers for Interpretable Multi-horizon Time Series Forecasting"
International Journal of Forecasting, 37(4), 1748-1764.

Adapted for Retail SKU-Week Demand Forecasting with Causal Tabular Features.
Implements:
- Gated Linear Unit (GLU)
- Gated Residual Network (GRN)
- Variable Selection Network (VSN) across semantic feature groups
- Interpretable Multi-Head Self-Attention
- Temporal Residual Gating & Linear Output Projection
"""
from typing import Dict, List, Any, Optional, Tuple
import torch
import torch.nn as nn
import torch.nn.functional as F


class GatedLinearUnit(nn.Module):
    """
    Gated Linear Unit (GLU).
    Splits input of dimension 2*D into two halves: value and gate,
    and returns value * sigmoid(gate).
    """
    def __init__(self, in_features: int, out_features: int):
        super().__init__()
        self.linear = nn.Linear(in_features, out_features * 2)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        val_and_gate = self.linear(x)
        val, gate = val_and_gate.chunk(2, dim=-1)
        return val * torch.sigmoid(gate)


class GatedResidualNetwork(nn.Module):
    """
    Gated Residual Network (GRN) - the fundamental building block of TFT.
    GRN(a, c) = LayerNorm(skip(a) + GLU(Linear(Dropout(ELU(Linear(a) + Linear(c))))))
    """
    def __init__(
        self,
        in_dim: int,
        hidden_dim: int,
        out_dim: int,
        dropout: float = 0.1,
        context_dim: Optional[int] = None
    ):
        super().__init__()
        self.in_dim = in_dim
        self.out_dim = out_dim

        self.linear1 = nn.Linear(in_dim, hidden_dim)
        self.context_linear = nn.Linear(context_dim, hidden_dim, bias=False) if context_dim else None
        self.act = nn.ELU()
        self.drop = nn.Dropout(dropout)
        self.glu = GatedLinearUnit(hidden_dim, out_dim)

        # Skip connection
        if in_dim != out_dim:
            self.skip = nn.Linear(in_dim, out_dim)
        else:
            self.skip = nn.Identity()

        self.norm = nn.LayerNorm(out_dim)

    def forward(self, a: torch.Tensor, c: Optional[torch.Tensor] = None) -> torch.Tensor:
        h = self.linear1(a)
        if self.context_linear is not None and c is not None:
            h = h + self.context_linear(c)
        h = self.act(h)
        h = self.drop(h)
        g = self.glu(h)
        return self.norm(self.skip(a) + g)


class VariableSelectionNetwork(nn.Module):
    """
    Variable Selection Network (VSN).
    Processes semantic feature groups through individual GRNs, computes data-dependent
    variable selection weights using a selection GRN + Softmax, and outputs the weighted sum.
    """
    def __init__(
        self,
        group_dims: List[int],
        hidden_dim: int,
        dropout: float = 0.1
    ):
        super().__init__()
        self.num_groups = len(group_dims)
        self.group_grns = nn.ModuleList([
            GatedResidualNetwork(dim, hidden_dim, hidden_dim, dropout=dropout)
            for dim in group_dims
        ])
        # Selection weight network
        total_dim = sum(group_dims)
        self.selection_grn = GatedResidualNetwork(total_dim, hidden_dim, self.num_groups, dropout=dropout)

    def forward(self, group_tensors: List[torch.Tensor]) -> Tuple[torch.Tensor, torch.Tensor]:
        # Concatenate all inputs to compute group weights
        all_x = torch.cat(group_tensors, dim=-1)
        weights = F.softmax(self.selection_grn(all_x), dim=-1)  # (batch_size, num_groups)

        # Process each group through its GRN
        group_embeddings = [grn(x) for grn, x in zip(self.group_grns, group_tensors)]  # list of (B, hidden_dim)
        stacked = torch.stack(group_embeddings, dim=1)  # (batch_size, num_groups, hidden_dim)

        # Compute weighted sum
        weights_expanded = weights.unsqueeze(-1)  # (batch_size, num_groups, 1)
        weighted_out = (stacked * weights_expanded).sum(dim=1)  # (batch_size, hidden_dim)

        return weighted_out, weights


class InterpretableMultiHeadAttention(nn.Module):
    """
    Interpretable Multi-Head Self-Attention.
    Applies multi-head attention across representation dimensions with additive aggregation.
    """
    def __init__(self, hidden_dim: int, num_heads: int = 4, dropout: float = 0.1):
        super().__init__()
        self.hidden_dim = hidden_dim
        self.num_heads = num_heads
        self.head_dim = hidden_dim // num_heads

        assert hidden_dim % num_heads == 0, f"hidden_dim {hidden_dim} must be divisible by num_heads {num_heads}"

        self.q_proj = nn.Linear(hidden_dim, hidden_dim)
        self.k_proj = nn.Linear(hidden_dim, hidden_dim)
        self.v_proj = nn.Linear(hidden_dim, hidden_dim)

        self.out_glu = GatedLinearUnit(hidden_dim, hidden_dim)
        self.norm = nn.LayerNorm(hidden_dim)
        self.drop = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (batch_size, hidden_dim)
        # Reshape to (batch_size, 1, hidden_dim) for attention
        x_seq = x.unsqueeze(1)
        B, S, D = x_seq.shape

        q = self.q_proj(x_seq).view(B, S, self.num_heads, self.head_dim).transpose(1, 2)
        k = self.k_proj(x_seq).view(B, S, self.num_heads, self.head_dim).transpose(1, 2)
        v = self.v_proj(x_seq).view(B, S, self.num_heads, self.head_dim).transpose(1, 2)

        scores = torch.matmul(q, k.transpose(-2, -1)) / (self.head_dim ** 0.5)
        attn = F.softmax(scores, dim=-1)
        attn = self.drop(attn)

        context = torch.matmul(attn, v).transpose(1, 2).contiguous().view(B, S, D).squeeze(1)
        gated = self.out_glu(context)

        return self.norm(x + gated)


class TFTModel(nn.Module):
    """
    Temporal Fusion Transformer Model for Demand Forecasting.
    - Variable Selection Network across 4 semantic domains
    - Interpretable Multi-Head Self-Attention
    - Gated Temporal Fusion & Output Projection
    """
    def __init__(
        self,
        group_dims: List[int],
        group_indices: List[List[int]],
        hidden_dim: int = 64,
        num_heads: int = 4,
        dropout: float = 0.1
    ):
        super().__init__()
        self.group_indices = group_indices
        self.vsn = VariableSelectionNetwork(group_dims, hidden_dim, dropout=dropout)
        self.attention = InterpretableMultiHeadAttention(hidden_dim, num_heads=num_heads, dropout=dropout)
        self.output_grn = GatedResidualNetwork(hidden_dim, hidden_dim, hidden_dim, dropout=dropout)
        self.out_proj = nn.Linear(hidden_dim, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.
        Args:
            x: Input feature tensor of shape (batch_size, total_features)
        Returns:
            Tensor of shape (batch_size,)
        """
        # Split x into semantic feature groups
        group_tensors = [x[:, indices] for indices in self.group_indices]

        # 1. Variable selection
        vsn_out, _ = self.vsn(group_tensors)

        # 2. Interpretable multi-head attention
        attn_out = self.attention(vsn_out)

        # 3. Post-attention GRN
        final_rep = self.output_grn(attn_out)

        # 4. Output projection
        pred = self.out_proj(final_rep).squeeze(-1)
        return pred


def get_canonical_tft_feature_groups(feature_names: List[str]) -> Tuple[List[int], List[List[int]], Dict[str, List[str]]]:
    """
    Partition the 71 canonical predictors into 4 semantic groups for TFT VSN:
    1. Demand Dynamics & Lags (45 features)
    2. Intermittency & Lifecycle (11 features)
    3. Calendar & Seasonality (10 features)
    4. Price & Value Dynamics (5 features)
    """
    g_cal_names = [f for f in feature_names if f.startswith('target_')]
    g_price_names = [f for f in feature_names if 'price' in f]
    g_intermit_names = [
        f for f in feature_names
        if f in [
            'is_zero_denominator_1_2', 'is_zero_denominator_1_4',
            'weeks_since_last_sale', 'weeks_since_first_observed',
            'txn_count_lag_1', 'unique_customer_count_lag_1'
        ] or 'zero' in f
    ]
    g_demand_names = [
        f for f in feature_names
        if f not in g_cal_names and f not in g_price_names and f not in g_intermit_names
    ]

    groups = [
        ("demand_dynamics", g_demand_names),
        ("intermittency_lifecycle", g_intermit_names),
        ("calendar_seasonality", g_cal_names),
        ("price_dynamics", g_price_names)
    ]

    group_dims = [len(g_feats) for _, g_feats in groups]
    name_to_idx = {name: i for i, name in enumerate(feature_names)}
    group_indices = [[name_to_idx[f] for f in g_feats] for _, g_feats in groups]
    group_dict = {name: g_feats for name, g_feats in groups}

    # Verify total
    total = sum(group_dims)
    if total != len(feature_names):
        raise ValueError(f"Feature partition sum {total} != feature count {len(feature_names)}")

    return group_dims, group_indices, group_dict


def create_tft_primary_config(feature_names: List[str]) -> Dict[str, Any]:
    """
    Returns the pre-registered configuration dictionary for TFT__primary_config.
    """
    group_dims, group_indices, group_dict = get_canonical_tft_feature_groups(feature_names)
    return {
        "model_name": "TFT__primary_config",
        "family": "TFT",
        "objective": "L1_MAE",
        "eval_metric": "MAE",
        "group_dims": group_dims,
        "group_indices": group_indices,
        "group_dict": group_dict,
        "hyperparameters": {
            "hidden_dim": 64,
            "num_heads": 4,
            "dropout": 0.1,
            "lr": 1e-3,
            "weight_decay": 1e-4,
            "batch_size": 2048,
            "max_epochs": 15,
            "early_stopping_patience": 3,
            "seed": 42
        }
    }
