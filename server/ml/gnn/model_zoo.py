"""
Extension to the Model Zoo to include the MLP Baseline.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import GCNConv, SAGEConv, GATConv, global_mean_pool, global_max_pool
from torch_geometric.data import Data
from typing import Dict, Any

from ml.gnn.baseline_mlp import MLPBaseline

# Constants
try:
    from market.standalone_checker import NUM_NODE_FEATURES, NUM_EDGE_FEATURES
except ImportError:
    try:
        from ml.utils.graph_features import NUM_NODE_FEATURES, NUM_EDGE_FEATURES
    except ImportError:
        NUM_NODE_FEATURES = 6
        NUM_EDGE_FEATURES = 5

class BaseFeasibilityModel(nn.Module):
    def __init__(self, hidden_dim: int = 64, dropout: float = 0.2):
        super().__init__()
        self.hidden_dim = hidden_dim
        self.dropout = dropout

    def _get_graph_embedding(self, x: torch.Tensor, batch: torch.Tensor) -> torch.Tensor:
        pooled_mean = global_mean_pool(x, batch)
        pooled_max = global_max_pool(x, batch)
        return torch.cat([pooled_mean, pooled_max], dim=1)

    def _build_head(self, input_dim: int) -> nn.Sequential:
        return nn.Sequential(
            nn.Linear(input_dim, self.hidden_dim),
            nn.ReLU(),
            nn.Dropout(self.dropout),
            nn.Linear(self.hidden_dim, self.hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(self.dropout),
            nn.Linear(self.hidden_dim // 2, 1),
        )

class GCNFeasibility(BaseFeasibilityModel):
    def __init__(self, node_features=NUM_NODE_FEATURES, hidden_dim=64, num_layers=3, dropout=0.2):
        super().__init__(hidden_dim, dropout)
        self.convs = nn.ModuleList([GCNConv(node_features if i == 0 else hidden_dim, hidden_dim) for i in range(num_layers)])
        self.bns = nn.ModuleList([nn.BatchNorm1d(hidden_dim) for _ in range(num_layers)])
        self.head = self._build_head(hidden_dim * 2)

    def forward(self, data: Data) -> Dict[str, torch.Tensor]:
        x, edge_index = data.x, data.edge_index
        batch = data.batch if hasattr(data, 'batch') else torch.zeros(x.size(0), dtype=torch.long, device=x.device)
        for i in range(len(self.convs)):
            x = self.convs[i](x, edge_index)
            x = self.bns[i](x)
            x = F.relu(x)
            x = F.dropout(x, p=self.dropout, training=self.training)
        graph_emb = self._get_graph_embedding(x, batch)
        logit = self.head(graph_emb)
        return {"logit": logit.squeeze(-1), "probability": torch.sigmoid(logit).squeeze(-1)}

class GraphSAGEFeasibility(BaseFeasibilityModel):
    def __init__(self, node_features=NUM_NODE_FEATURES, hidden_dim=64, num_layers=3, dropout=0.2):
        super().__init__(hidden_dim, dropout)
        self.convs = nn.ModuleList([SAGEConv(node_features if i == 0 else hidden_dim, hidden_dim) for i in range(num_layers)])
        self.bns = nn.ModuleList([nn.BatchNorm1d(hidden_dim) for _ in range(num_layers)])
        self.head = self._build_head(hidden_dim * 2)

    def forward(self, data: Data) -> Dict[str, torch.Tensor]:
        x, edge_index = data.x, data.edge_index
        batch = data.batch if hasattr(data, 'batch') else torch.zeros(x.size(0), dtype=torch.long, device=x.device)
        for i in range(len(self.convs)):
            x = self.convs[i](x, edge_index)
            x = self.bns[i](x)
            x = F.relu(x)
            x = F.dropout(x, p=self.dropout, training=self.training)
        graph_emb = self._get_graph_embedding(x, batch)
        logit = self.head(graph_emb)
        return {"logit": logit.squeeze(-1), "probability": torch.sigmoid(logit).squeeze(-1)}

class GATFeasibility(BaseFeasibilityModel):
    def __init__(self, node_features=NUM_NODE_FEATURES, hidden_dim=64, num_layers=3, heads=4, dropout=0.2):
        super().__init__(hidden_dim, dropout)
        self.convs = nn.ModuleList()
        self.convs.append(GATConv(node_features, hidden_dim // heads, heads=heads))
        for _ in range(num_layers - 1):
            self.convs.append(GATConv(hidden_dim, hidden_dim // heads, heads=heads))
        self.bns = nn.ModuleList([nn.BatchNorm1d(hidden_dim) for _ in range(num_layers)])
        self.head = self._build_head(hidden_dim * 2)

    def forward(self, data: Data) -> Dict[str, torch.Tensor]:
        x, edge_index = data.x, data.edge_index
        batch = data.batch if hasattr(data, 'batch') else torch.zeros(x.size(0), dtype=torch.long, device=x.device)
        for i in range(len(self.convs)):
            x, (edge_idx, alpha) = self.convs[i](x, edge_index, return_attention_weights=True)
            x = self.bns[i](x)
            x = F.relu(x)
            x = F.dropout(x, p=self.dropout, training=self.training)
        graph_emb = self._get_graph_embedding(x, batch)
        logit = self.head(graph_emb)
        return {"logit": logit.squeeze(-1), "probability": torch.sigmoid(logit).squeeze(-1)}

class GRGNFeasibility(BaseFeasibilityModel):
    def __init__(self, node_features=NUM_NODE_FEATURES, hidden_dim=64, num_layers=3, dropout=0.2):
        super().__init__(hidden_dim, dropout)
        self.sage = SAGEConv(node_features, hidden_dim)
        self.rnn = nn.GRUCell(hidden_dim, hidden_dim)
        self.bn = nn.BatchNorm1d(hidden_dim)
        self.head = self._build_head(hidden_dim * 2)

    def forward(self, data: Data) -> Dict[str, torch.Tensor]:
        x, edge_index = data.x, data.edge_index
        batch = data.batch if hasattr(data, 'batch') else torch.zeros(x.size(0), dtype=torch.long, device=x.device)
        h_spatial = self.sage(x, edge_index)
        h_spatial = F.relu(self.bn(h_spatial))
        h_rec = torch.zeros_like(h_spatial)
        for _ in range(3):
            h_rec = self.rnn(h_spatial, h_rec)
        x = h_rec
        graph_emb = self._get_graph_embedding(x, batch)
        logit = self.head(graph_emb)
        return {"logit": logit.squeeze(-1), "probability": torch.sigmoid(logit).squeeze(-1)}

def create_model_zoo(model_name: str, **kwargs) -> nn.Module:
    models = {
        "gcn": GCNFeasibility,
        "graphsage": GraphSAGEFeasibility,
        "gat": GATFeasibility,
        "grgn": GRGNFeasibility,
        "mlp": MLPBaseline,
    }
    if model_name.lower() not in models:
        raise ValueError(f"Model {model_name} not found in zoo. Available: {list(models.keys())}")
    return models[model_name.lower()](**kwargs)
