"""
GNN Feasibility Model — GraphSAGE / GAT architecture.

This is the core ML model that learns to predict whether a candidate P2P
energy trade will cause grid constraint violations (voltage out of ±5% bounds,
line thermal overload) by reasoning over the grid graph structure.

Architecture:
- Input: PyG Data object with node features, edge features, edge index
- Graph convolution layers: GraphSAGE (default) or GAT (interpretable attention)
- Readout: Global mean + max pooling → MLP classification/regression head
- Output: Feasibility prediction (binary classification or regression)

Why GNN, not MLP?
The grid is a graph — power flows from bus to bus along physical lines.
A trade at bus X affects bus Y depending on the electrical distance and
topology between them, not just their individual features. The GNN
learns these topology-dependent relationships; the MLP baseline (same
features, flattened) cannot. If the GNN outperforms the MLP, this proves
the graph structure helps — which is the core novelty claim.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import SAGEConv, GATConv, global_mean_pool, global_max_pool
from torch_geometric.data import Data, Batch
from typing import Optional, Tuple

from ml.utils.graph_features import NUM_NODE_FEATURES, NUM_EDGE_FEATURES


class GraphSAGEFeasibility(nn.Module):
    """
    GraphSAGE-based feasibility prediction model.

    GraphSAGE (SAmple and aggreGatE) is chosen as the default because:
    1. It's simpler and faster to train than GAT
    2. It handles inductive learning well (can generalize to unseen graph sizes)
    3. It provides a clean baseline before adding attention complexity
    """

    def __init__(
        self,
        node_features: int = NUM_NODE_FEATURES,
        hidden_dim: int = 64,
        num_layers: int = 3,
        dropout: float = 0.2,
        output_mode: str = "classification",  # "classification" or "regression"
        num_buses: int = 13,
        num_lines: int = 11,
    ):
        """
        Args:
            node_features: Number of input features per node.
            hidden_dim: Hidden layer dimension.
            num_layers: Number of GraphSAGE convolution layers.
            dropout: Dropout rate.
            output_mode: "classification" for binary feasible/infeasible,
                         "regression" for continuous voltage/loading prediction.
            num_buses: Number of buses (for regression output).
            num_lines: Number of lines (for regression output).
        """
        super().__init__()
        self.output_mode = output_mode
        self.num_layers = num_layers
        self.dropout = dropout

        # GraphSAGE convolution layers
        self.convs = nn.ModuleList()
        self.convs.append(SAGEConv(node_features, hidden_dim))
        for _ in range(num_layers - 1):
            self.convs.append(SAGEConv(hidden_dim, hidden_dim))

        # Batch normalization layers
        self.bns = nn.ModuleList([
            nn.BatchNorm1d(hidden_dim) for _ in range(num_layers)
        ])

        # After pooling: [mean_pool || max_pool] → 2 * hidden_dim
        pooled_dim = hidden_dim * 2

        if output_mode == "classification":
            # Binary classification head
            self.head = nn.Sequential(
                nn.Linear(pooled_dim, hidden_dim),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(hidden_dim, hidden_dim // 2),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(hidden_dim // 2, 1),
            )
        else:
            # Regression head: predict voltages and loadings
            self.voltage_head = nn.Sequential(
                nn.Linear(pooled_dim + hidden_dim, hidden_dim),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(hidden_dim, num_buses),
            )
            self.loading_head = nn.Sequential(
                nn.Linear(pooled_dim + hidden_dim, hidden_dim),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(hidden_dim, num_lines),
            )
            # Also keep a classification head derived from regression
            self.feasibility_head = nn.Sequential(
                nn.Linear(pooled_dim, hidden_dim // 2),
                nn.ReLU(),
                nn.Linear(hidden_dim // 2, 1),
            )

    def forward(
        self,
        data: Data,
    ) -> dict:
        """
        Forward pass.

        Args:
            data: PyG Data or Batch object.

        Returns:
            Dict with predictions:
            - 'logit': Raw classification logit
            - 'probability': Sigmoid probability of feasibility
            - 'predicted_voltages': (regression mode) Per-bus voltage predictions
            - 'predicted_loadings': (regression mode) Per-line loading predictions
        """
        x, edge_index = data.x, data.edge_index
        batch = data.batch if hasattr(data, 'batch') else torch.zeros(x.size(0), dtype=torch.long, device=x.device)

        # Graph convolution layers
        for i in range(self.num_layers):
            x = self.convs[i](x, edge_index)
            x = self.bns[i](x)
            x = F.relu(x)
            x = F.dropout(x, p=self.dropout, training=self.training)

        node_embeddings = x  # Save for regression heads

        # Global pooling (graph-level representation)
        pooled_mean = global_mean_pool(x, batch)
        pooled_max = global_max_pool(x, batch)
        graph_embedding = torch.cat([pooled_mean, pooled_max], dim=1)

        result = {}

        if self.output_mode == "classification":
            logit = self.head(graph_embedding)
            result["logit"] = logit.squeeze(-1)
            result["probability"] = torch.sigmoid(logit).squeeze(-1)
        else:
            # Regression mode: predict per-bus voltages and per-line loadings
            # Use node embeddings + graph embedding for per-node predictions
            num_nodes_per_graph = []
            if hasattr(data, 'batch'):
                for g in range(batch.max().item() + 1):
                    num_nodes_per_graph.append((batch == g).sum().item())
            else:
                num_nodes_per_graph = [x.size(0)]

            # Expand graph embedding to match node count, concatenate with node embeddings
            graph_expanded = torch.cat([
                graph_embedding[g].unsqueeze(0).expand(n, -1)
                for g, n in enumerate(num_nodes_per_graph)
            ], dim=0)

            node_with_global = torch.cat([node_embeddings, graph_expanded], dim=1)

            # Pool node features back to graph level for fixed-size output
            node_pooled = global_mean_pool(node_with_global, batch)

            result["predicted_voltages"] = self.voltage_head(node_pooled)
            result["predicted_loadings"] = self.loading_head(node_pooled)

            # Feasibility classification from graph embedding
            logit = self.feasibility_head(graph_embedding)
            result["logit"] = logit.squeeze(-1)
            result["probability"] = torch.sigmoid(logit).squeeze(-1)

        return result


class GATFeasibility(nn.Module):
    """
    Graph Attention Network (GAT) variant.

    GAT adds attention weights to graph convolutions, providing:
    1. Potentially better performance (attention learns which neighbors matter)
    2. Interpretability (attention weights show which bus most influenced the prediction)

    Use this as the second version after GraphSAGE is working.
    """

    def __init__(
        self,
        node_features: int = NUM_NODE_FEATURES,
        hidden_dim: int = 64,
        num_layers: int = 3,
        num_heads: int = 4,
        dropout: float = 0.2,
    ):
        super().__init__()
        self.num_layers = num_layers
        self.dropout = dropout

        self.convs = nn.ModuleList()
        self.convs.append(GATConv(node_features, hidden_dim // num_heads, heads=num_heads))
        for _ in range(num_layers - 1):
            self.convs.append(GATConv(hidden_dim, hidden_dim // num_heads, heads=num_heads))

        self.bns = nn.ModuleList([nn.BatchNorm1d(hidden_dim) for _ in range(num_layers)])

        pooled_dim = hidden_dim * 2
        self.head = nn.Sequential(
            nn.Linear(pooled_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, 1),
        )

    def forward(self, data: Data) -> dict:
        x, edge_index = data.x, data.edge_index
        batch = data.batch if hasattr(data, 'batch') else torch.zeros(x.size(0), dtype=torch.long, device=x.device)

        attention_weights = []

        for i in range(self.num_layers):
            x, (edge_idx, alpha) = self.convs[i](x, edge_index, return_attention_weights=True)
            attention_weights.append(alpha)
            x = self.bns[i](x)
            x = F.relu(x)
            x = F.dropout(x, p=self.dropout, training=self.training)

        pooled_mean = global_mean_pool(x, batch)
        pooled_max = global_max_pool(x, batch)
        graph_embedding = torch.cat([pooled_mean, pooled_max], dim=1)

        logit = self.head(graph_embedding)

        return {
            "logit": logit.squeeze(-1),
            "probability": torch.sigmoid(logit).squeeze(-1),
            "attention_weights": attention_weights,  # For interpretability
        }


def create_model(
    model_type: str = "graphsage",
    output_mode: str = "classification",
    **kwargs,
) -> nn.Module:
    """Factory function to create a GNN model."""
    if model_type == "graphsage":
        return GraphSAGEFeasibility(output_mode=output_mode, **kwargs)
    elif model_type == "gat":
        return GATFeasibility(**kwargs)
    else:
        raise ValueError(f"Unknown model type: {model_type}")
