"""
Temporal Fusion Transformer (TFT) Sequence Model (Canonical Temporal Architecture).
Reference: Lim et al. (2021), "Temporal Fusion Transformers for Interpretable Multi-horizon Time Series Forecasting"
International Journal of Forecasting, 37(4), 1748-1764. DOI: 10.1016/j.ijforecast.2021.03.012
Google Research.

Implements the canonical temporal sequence architecture:
1. Full sequence representation across time steps S = L + H (lookback L + horizon H).
2. Per-timestep Variable Selection Network (VSN) with Gated Residual Networks (GRN) and GLU gating.
3. Recurrent local temporal processing (Seq2Seq / LSTM) across S timesteps.
4. Causal Interpretable Multi-Head Self-Attention over S timesteps (S > 1, strictly non-degenerate).
5. Post-attention temporal gating & GRN decoder.
6. Direct multi-horizon demand forecasting head mapping to (B, H).
"""
from typing import Dict, List, Any, Optional, Tuple
import math
import torch
import torch.nn as nn
import torch.nn.functional as F


class GatedLinearUnit(nn.Module):
    """
    Gated Linear Unit (GLU).
    GLU(x) = Linear_val(x) * sigmoid(Linear_gate(x))
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
    Gated Residual Network (GRN) - the core non-linear gating block of TFT.
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


class TemporalVariableSelectionNetwork(nn.Module):
    """
    Temporal Variable Selection Network applied across sequence timesteps.
    For each timestep t in 1..S, it takes D input feature groups, passes each through a GRN,
    computes variable selection weights via a selection GRN + Softmax, and outputs the weighted representation.
    """
    def __init__(
        self,
        input_dims: List[int],
        hidden_dim: int,
        dropout: float = 0.1
    ):
        super().__init__()
        self.num_vars = len(input_dims)
        self.var_grns = nn.ModuleList([
            GatedResidualNetwork(dim, hidden_dim, hidden_dim, dropout=dropout)
            for dim in input_dims
        ])
        total_dim = sum(input_dims)
        self.selection_grn = GatedResidualNetwork(total_dim, hidden_dim, self.num_vars, dropout=dropout)

    def forward(self, var_tensors: List[torch.Tensor]) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            var_tensors: List of tensors, each of shape (B, S, dim_i)
        Returns:
            weighted_out: (B, S, hidden_dim)
            weights: (B, S, num_vars)
        """
        # Concatenate across feature dimension: (B, S, sum(dim_i))
        all_vars = torch.cat(var_tensors, dim=-1)
        weights = F.softmax(self.selection_grn(all_vars), dim=-1)  # (B, S, num_vars)

        # Process each variable through its GRN: (B, S, hidden_dim)
        var_embeddings = [grn(v) for grn, v in zip(self.var_grns, var_tensors)]
        stacked = torch.stack(var_embeddings, dim=-2)  # (B, S, num_vars, hidden_dim)

        weights_expanded = weights.unsqueeze(-1)  # (B, S, num_vars, 1)
        weighted_out = (stacked * weights_expanded).sum(dim=-2)  # (B, S, hidden_dim)

        return weighted_out, weights


class CausalInterpretableMultiHeadAttention(nn.Module):
    """
    Causal Interpretable Multi-Head Self-Attention for Temporal Sequences.
    Reference: Lim et al. (2021), Section 3.2.4.
    
    Shares value weights V across heads to produce an interpretable attention map,
    and enforces a strict causal lower-triangular mask so no future timestep can attend
    to future information.
    """
    def __init__(self, hidden_dim: int, num_heads: int = 4, dropout: float = 0.1):
        super().__init__()
        self.hidden_dim = hidden_dim
        self.num_heads = num_heads
        self.head_dim = hidden_dim // num_heads

        assert hidden_dim % num_heads == 0, f"hidden_dim {hidden_dim} must be divisible by num_heads {num_heads}"

        self.q_proj = nn.Linear(hidden_dim, hidden_dim)
        self.k_proj = nn.Linear(hidden_dim, hidden_dim)
        # Shared value projection across heads for interpretability
        self.v_proj = nn.Linear(hidden_dim, hidden_dim)

        self.out_glu = GatedLinearUnit(hidden_dim, hidden_dim)
        self.norm = nn.LayerNorm(hidden_dim)
        self.drop = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            x: (B, S, hidden_dim) temporal representation across sequence timesteps
        Returns:
            out: (B, S, hidden_dim) post-attention gated representation
            attn_weights: (B, S, S) averaged interpretable attention weights
        """
        B, S, D = x.shape
        # Strict architecture assertion: Temporal attention MUST have S > 1
        assert S > 1, f"Canonical temporal attention requires sequence length S > 1; received S={S}."

        q = self.q_proj(x).view(B, S, self.num_heads, self.head_dim).transpose(1, 2)  # (B, num_heads, S, head_dim)
        k = self.k_proj(x).view(B, S, self.num_heads, self.head_dim).transpose(1, 2)  # (B, num_heads, S, head_dim)
        v = self.v_proj(x).view(B, S, self.num_heads, self.head_dim).transpose(1, 2)  # (B, num_heads, S, head_dim)

        # Scaled dot-product
        scores = torch.matmul(q, k.transpose(-2, -1)) / math.sqrt(self.head_dim)  # (B, num_heads, S, S)

        # Causal mask: position i can only attend to positions j <= i
        causal_mask = torch.triu(torch.full((S, S), float("-inf"), device=x.device), diagonal=1)
        scores = scores + causal_mask.unsqueeze(0).unsqueeze(0)

        attn = F.softmax(scores, dim=-1)  # (B, num_heads, S, S)
        attn = self.drop(attn)

        # Context computation
        context = torch.matmul(attn, v)  # (B, num_heads, S, head_dim)
        context = context.transpose(1, 2).contiguous().view(B, S, D)  # (B, S, D)

        # Gated additive residual connection
        gated = self.out_glu(context)
        out = self.norm(x + gated)

        # Mean attention weights across heads for interpretability analysis
        mean_attn = attn.mean(dim=1)  # (B, S, S)

        return out, mean_attn


class TFTSequenceModel(nn.Module):
    """
    Canonical Temporal Fusion Transformer (TFT_Sequence_v1) for Multi-Horizon Demand Forecasting.
    
    Sequence Layout:
      - Lookback window: L time steps (e.g., L=13 weeks)
      - Forecast horizon: H time steps (e.g., H=8 weeks)
      - Total sequence length: S = L + H = 21 weeks
    
    Inputs:
      - past_targets: (B, L) historical demand sequence
      - past_covariates: (B, L, d_past) dynamic historical covariates (e.g. price, promo)
      - future_covariates: (B, H, d_future) known future calendar/holiday covariates
      - past_calendar_covariates: (B, L, d_future) past calendar covariates
    
    Output:
      - predictions: (B, H) direct multi-horizon point forecasts
    """
    def __init__(
        self,
        lookback_len: int = 13,
        horizon_len: int = 8,
        d_past_cov: int = 4,
        d_future_cov: int = 10,
        hidden_dim: int = 64,
        num_heads: int = 4,
        dropout: float = 0.1
    ):
        super().__init__()
        self.lookback_len = lookback_len
        self.horizon_len = horizon_len
        self.total_seq_len = lookback_len + horizon_len  # S = 21
        self.d_past_cov = d_past_cov
        self.d_future_cov = d_future_cov
        self.hidden_dim = hidden_dim

        # 1. Variable Selection Network across timesteps:
        # Variables:
        # 1) Target channel (dim 1)
        # 2) Dynamic past covariate channel (dim d_past_cov)
        # 3) Known calendar covariate channel (dim d_future_cov)
        # 4) Step temporal indicator channel (dim 1: 0 for past, 1 for future)
        input_dims = [1, max(1, d_past_cov), d_future_cov, 1]
        self.vsn = TemporalVariableSelectionNetwork(input_dims, hidden_dim, dropout=dropout)

        # 2. Recurrent Local Temporal Processing (Seq2Seq / LSTM)
        self.lstm = nn.LSTM(
            input_size=hidden_dim,
            hidden_size=hidden_dim,
            batch_first=True
        )
        self.lstm_glu = GatedLinearUnit(hidden_dim, hidden_dim)
        self.lstm_norm = nn.LayerNorm(hidden_dim)

        # 3. Causal Interpretable Multi-Head Self-Attention over S timesteps
        self.attention = CausalInterpretableMultiHeadAttention(
            hidden_dim=hidden_dim,
            num_heads=num_heads,
            dropout=dropout
        )

        # 4. Multi-Horizon Decoder Head
        # Post-attention GRN for the H future forecast steps
        self.decoder_grn = GatedResidualNetwork(hidden_dim, hidden_dim, hidden_dim, dropout=dropout)
        self.out_proj = nn.Linear(hidden_dim, 1)

    def forward(
        self,
        past_targets: torch.Tensor,
        past_covariates: Optional[torch.Tensor] = None,
        future_covariates: Optional[torch.Tensor] = None,
        past_calendar_covariates: Optional[torch.Tensor] = None
    ) -> torch.Tensor:
        """
        Forward pass.
        Args:
            past_targets: (B, L)
            past_covariates: (B, L, d_past) or None
            future_covariates: (B, H, d_future)
            past_calendar_covariates: (B, L, d_future) or None
        Returns:
            predictions: (B, H)
        """
        B, L = past_targets.shape
        H = self.horizon_len
        S = L + H
        device = past_targets.device

        assert L == self.lookback_len, f"Expected lookback_len={self.lookback_len}, got {L}"

        # 1. Construct unified sequence tensors across S timesteps:
        # Variable 1: Target sequence (B, S, 1) - known in past, 0 masked in future
        future_target_placeholder = torch.zeros(B, H, device=device)
        full_targets = torch.cat([past_targets, future_target_placeholder], dim=1).unsqueeze(-1)  # (B, S, 1)

        # Variable 2: Dynamic past covariates (B, S, d_past) - known in past, forward-filled / 0 in future
        if self.d_past_cov > 0 and past_covariates is not None:
            last_past_cov = past_covariates[:, -1:, :].expand(B, H, self.d_past_cov)
            full_past_cov = torch.cat([past_covariates, last_past_cov], dim=1)  # (B, S, d_past)
        else:
            full_past_cov = torch.zeros(B, S, max(1, self.d_past_cov), device=device)

        # Variable 3: Calendar covariates (B, S, d_future) - known across both past and future
        if past_calendar_covariates is not None and future_covariates is not None:
            full_calendar = torch.cat([past_calendar_covariates, future_covariates], dim=1)  # (B, S, d_future)
        elif future_covariates is not None:
            dummy_past_cal = future_covariates[:, :1, :].expand(B, L, self.d_future_cov)
            full_calendar = torch.cat([dummy_past_cal, future_covariates], dim=1)
        else:
            full_calendar = torch.zeros(B, S, self.d_future_cov, device=device)

        # Variable 4: Temporal horizon indicator (B, S, 1) - 0 for past, 1 for future
        past_indicator = torch.zeros(B, L, 1, device=device)
        future_indicator = torch.ones(B, H, 1, device=device)
        temporal_indicator = torch.cat([past_indicator, future_indicator], dim=1)  # (B, S, 1)

        # 2. Variable Selection Network across timesteps
        vsn_input = [full_targets, full_past_cov, full_calendar, temporal_indicator]
        vsn_out, _ = self.vsn(vsn_input)  # (B, S, hidden_dim)

        # 3. Recurrent Local Temporal Processing (LSTM over S timesteps)
        lstm_out, _ = self.lstm(vsn_out)  # (B, S, hidden_dim)
        local_rep = self.lstm_norm(vsn_out + self.lstm_glu(lstm_out))  # (B, S, hidden_dim)

        # 4. Causal Temporal Multi-Head Attention over S timesteps
        attn_out, _ = self.attention(local_rep)  # (B, S, hidden_dim)

        # 5. Extract future horizon slice: steps L..L+H (length H)
        future_rep = attn_out[:, L:S, :]  # (B, H, hidden_dim)

        # 6. Decoder GRN and multi-horizon projection
        decoded = self.decoder_grn(future_rep)  # (B, H, hidden_dim)
        pred = self.out_proj(decoded).squeeze(-1)  # (B, H)

        return pred


def create_tft_sequence_config(
    lookback_len: int = 13,
    horizon_len: int = 8,
    d_past_cov: int = 4,
    d_future_cov: int = 10
) -> Dict[str, Any]:
    """Pre-registered configuration for TFT_Sequence_v1."""
    return {
        "model_name": "TFT_Sequence_v1",
        "family": "TFT_Canonical",
        "objective": "L1_MAE",
        "eval_metric": "MAE",
        "architecture_type": "TEMPORAL_SEQUENCE_CANONICAL",
        "hyperparameters": {
            "lookback_len": lookback_len,
            "horizon_len": horizon_len,
            "d_past_cov": d_past_cov,
            "d_future_cov": d_future_cov,
            "hidden_dim": 64,
            "num_heads": 4,
            "dropout": 0.1,
            "lr": 1e-3,
            "weight_decay": 1e-4,
            "batch_size": 1024,
            "max_epochs": 20,
            "early_stopping_patience": 4,
            "seed": 42
        }
    }
