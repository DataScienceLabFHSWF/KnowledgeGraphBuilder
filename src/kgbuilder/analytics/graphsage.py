"""GraphSAGE structural embeddings and comparison to semantic embeddings.

Trains a lightweight GraphSAGE model (unsupervised) on the KG topology
to produce *structural* node embeddings that capture neighbourhood
patterns. These are then compared quantitatively to the *semantic*
embeddings obtained from the LLM encoder (Ollama/OpenAI/etc.).

Key research questions this module answers:
- Do structurally similar nodes also have similar semantic embeddings?
- Where do the two embedding spaces diverge? — These divergence points
  highlight entities whose textual description does not match their
  graph connectivity (possible extraction errors, missing relations,
  or genuinely surprising cross-domain connections).
- If we fuse both embeddings, does downstream clustering improve?

The module works with or without a GPU and gracefully falls back to
CPU-only training.  For small KGs (< 50k nodes) training takes seconds.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import structlog

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------


@dataclass
class GraphSAGEResult:
    """GraphSAGE training output + comparison to semantic embeddings."""

    # Structural embeddings
    node_ids: list[str] = field(default_factory=list)
    structural_embeddings: np.ndarray = field(
        default_factory=lambda: np.empty((0, 0))
    )
    embedding_dim: int = 0
    training_loss: list[float] = field(default_factory=list)

    # Comparison to semantic embeddings
    cosine_similarities: np.ndarray = field(
        default_factory=lambda: np.empty(0)
    )
    mean_cosine_similarity: float = 0.0
    std_cosine_similarity: float = 0.0

    # Divergent nodes (structurally ≠ semantically)
    divergent_nodes: list[tuple[str, float]] = field(default_factory=list)
    # Convergent nodes (structurally ≈ semantically)
    convergent_nodes: list[tuple[str, float]] = field(default_factory=list)

    # Procrustes alignment error (lower = more isomorphic spaces)
    procrustes_disparity: float | None = None

    # Fused embedding (concatenated + PCA-reduced)
    fused_embeddings: np.ndarray = field(
        default_factory=lambda: np.empty((0, 0))
    )


# ---------------------------------------------------------------------------
# GraphSAGE with PyTorch Geometric
# ---------------------------------------------------------------------------


def _try_torch_geometric() -> bool:
    """Check if torch-geometric is available."""
    try:
        import torch  # noqa: F401
        import torch_geometric  # noqa: F401
        return True
    except ImportError:
        return False


def train_graphsage(
    store: Any,
    hidden_dim: int = 64,
    output_dim: int = 64,
    num_layers: int = 2,
    epochs: int = 50,
    lr: float = 0.01,
) -> tuple[list[str], np.ndarray, list[float]]:
    """Train unsupervised GraphSAGE and return structural embeddings.

    If torch-geometric is available, uses the full GraphSAGE pipeline.
    Otherwise, falls back to a random-walk-based approximation using
    networkx + sklearn (Node2Vec-like via DeepWalk).

    Args:
        store: GraphStore backend.
        hidden_dim: Hidden layer dimension.
        output_dim: Final embedding dimension.
        num_layers: Number of GraphSAGE layers.
        epochs: Training epochs.
        lr: Learning rate.

    Returns:
        (node_ids, structural_embeddings, training_losses)
    """
    if _try_torch_geometric():
        return _train_graphsage_pyg(
            store, hidden_dim, output_dim, num_layers, epochs, lr,
        )
    else:
        logger.info(
            "torch_geometric_not_available",
            fallback="random_walk_embedding",
        )
        return _train_deepwalk_fallback(store, output_dim, epochs)


def _train_graphsage_pyg(
    store: Any,
    hidden_dim: int,
    output_dim: int,
    num_layers: int,
    epochs: int,
    lr: float,
) -> tuple[list[str], np.ndarray, list[float]]:
    """Full PyTorch Geometric GraphSAGE training."""
    import torch
    import torch.nn.functional as F
    from torch_geometric.data import Data  # type: ignore[import-untyped]
    from torch_geometric.nn import SAGEConv  # type: ignore[import-untyped]

    # Build adjacency from store
    nodes = list(store.get_all_nodes())
    edges = list(store.get_all_edges())
    node_ids = [n.id for n in nodes]
    node_idx = {nid: i for i, nid in enumerate(node_ids)}

    # Edge index (COO format)
    src_list, tgt_list = [], []
    for e in edges:
        if e.source_id in node_idx and e.target_id in node_idx:
            src_list.append(node_idx[e.source_id])
            tgt_list.append(node_idx[e.target_id])
            # Add reverse for undirected message passing
            src_list.append(node_idx[e.target_id])
            tgt_list.append(node_idx[e.source_id])

    edge_index = torch.tensor([src_list, tgt_list], dtype=torch.long)

    # Initial node features: one-hot type + random
    type_set = sorted({n.node_type for n in nodes})
    type_idx = {t: i for i, t in enumerate(type_set)}
    n_types = len(type_set)
    feat_dim = max(hidden_dim, n_types + 16)

    x = torch.zeros(len(nodes), feat_dim)
    for i, n in enumerate(nodes):
        # One-hot node type
        x[i, type_idx[n.node_type]] = 1.0
        # Small random component for breaking symmetry
        x[i, n_types:n_types + 16] = torch.randn(16) * 0.1

    data = Data(x=x, edge_index=edge_index)

    # Model
    class GraphSAGEEncoder(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.convs = torch.nn.ModuleList()
            self.convs.append(SAGEConv(feat_dim, hidden_dim))
            for _ in range(num_layers - 2):
                self.convs.append(SAGEConv(hidden_dim, hidden_dim))
            self.convs.append(SAGEConv(hidden_dim, output_dim))

        def forward(self, x: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
            for i, conv in enumerate(self.convs[:-1]):
                x = conv(x, edge_index)
                x = F.relu(x)
                x = F.dropout(x, p=0.2, training=self.training)
            x = self.convs[-1](x, edge_index)
            return x

    model = GraphSAGEEncoder()
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)

    # Unsupervised loss: connected nodes should have similar embeddings
    losses: list[float] = []
    model.train()
    for epoch in range(epochs):
        optimizer.zero_grad()
        z = model(data.x, data.edge_index)
        # Positive pairs: actual edges
        pos_loss = -torch.log(
            torch.sigmoid(
                (z[data.edge_index[0]] * z[data.edge_index[1]]).sum(dim=1)
            ) + 1e-15
        ).mean()
        # Negative sampling
        neg_src = torch.randint(0, len(nodes), (data.edge_index.shape[1],))
        neg_tgt = torch.randint(0, len(nodes), (data.edge_index.shape[1],))
        neg_loss = -torch.log(
            1 - torch.sigmoid(
                (z[neg_src] * z[neg_tgt]).sum(dim=1)
            ) + 1e-15
        ).mean()
        loss = pos_loss + neg_loss
        loss.backward()
        optimizer.step()
        losses.append(float(loss.item()))

    # Extract embeddings
    model.eval()
    with torch.no_grad():
        z = model(data.x, data.edge_index)
        embeddings = z.numpy()

    logger.info(
        "graphsage_training_complete",
        epochs=epochs, final_loss=losses[-1] if losses else 0.0,
        embedding_dim=output_dim,
    )

    return node_ids, embeddings, losses


def _train_deepwalk_fallback(
    store: Any,
    output_dim: int,
    epochs: int,
) -> tuple[list[str], np.ndarray, list[float]]:
    """Fallback: DeepWalk-style random walk + Word2Vec embeddings.

    Works without torch-geometric — only needs networkx + gensim/sklearn.
    """
    from kgbuilder.analytics.structural import graph_store_to_networkx

    G = graph_store_to_networkx(store)
    nodes = list(G.nodes())

    if len(nodes) == 0:
        return [], np.empty((0, output_dim)), []

    # Random walks
    rng = np.random.default_rng(42)
    walks: list[list[str]] = []
    walk_length = 20
    num_walks = 10

    for _ in range(num_walks):
        for node in nodes:
            walk = [node]
            current = node
            for _step in range(walk_length - 1):
                neighbors = list(G.neighbors(current))
                if not neighbors:
                    break
                current = rng.choice(neighbors)
                walk.append(current)
            walks.append(walk)

    # Use SVD on co-occurrence matrix (sklearn-only, no gensim needed)
    from sklearn.decomposition import TruncatedSVD  # type: ignore[import-untyped]

    node_idx = {n: i for i, n in enumerate(nodes)}
    n = len(nodes)
    window = 5

    # Build PMI-like co-occurrence matrix
    cooccur = np.zeros((n, n), dtype=np.float32)
    for walk in walks:
        for i, w in enumerate(walk):
            for j in range(max(0, i - window), min(len(walk), i + window + 1)):
                if i != j:
                    cooccur[node_idx[w], node_idx[walk[j]]] += 1.0

    # Log-transform
    cooccur = np.log1p(cooccur)

    dim = min(output_dim, n - 1)
    svd = TruncatedSVD(n_components=dim, random_state=42)
    embeddings = svd.fit_transform(cooccur)

    logger.info(
        "deepwalk_fallback_complete",
        nodes=n, dim=dim, walks=len(walks),
    )

    return nodes, embeddings, []


# ---------------------------------------------------------------------------
# Comparison: structural vs semantic
# ---------------------------------------------------------------------------


def compare_embeddings(
    node_ids_structural: list[str],
    structural_matrix: np.ndarray,
    node_ids_semantic: list[str],
    semantic_matrix: np.ndarray,
    top_k: int = 20,
) -> GraphSAGEResult:
    """Compare structural (GraphSAGE) and semantic (LLM) embeddings.

    Performs:
    1. Per-node cosine similarity between the two spaces (after alignment).
    2. Procrustes analysis to measure overall space isomorphism.
    3. Identification of divergent/convergent nodes.

    Args:
        node_ids_structural: Node IDs from structural embeddings.
        structural_matrix: (N, D1) matrix.
        node_ids_semantic: Node IDs from semantic embeddings.
        semantic_matrix: (N, D2) matrix.
        top_k: Number of extreme nodes to report.

    Returns:
        GraphSAGEResult with comparison metrics.
    """
    from sklearn.preprocessing import normalize  # type: ignore[import-untyped]

    # Align on common nodes
    common_set = set(node_ids_structural) & set(node_ids_semantic)
    if len(common_set) < 3:
        logger.warning("compare_embeddings_skipped", reason="too_few_common_nodes")
        return GraphSAGEResult()

    common = sorted(common_set)
    idx_s = {nid: i for i, nid in enumerate(node_ids_structural)}
    idx_e = {nid: i for i, nid in enumerate(node_ids_semantic)}

    S = structural_matrix[[idx_s[n] for n in common]]
    E = semantic_matrix[[idx_e[n] for n in common]]

    # Normalise
    S_norm = normalize(S)
    E_norm = normalize(E)

    # Per-node cosine similarity via row-wise dot product
    # First project to common dimensionality via PCA
    from sklearn.decomposition import PCA  # type: ignore[import-untyped]

    common_dim = min(S.shape[1], E.shape[1], len(common), 32)

    pca_s = PCA(n_components=common_dim, random_state=42)
    pca_e = PCA(n_components=common_dim, random_state=42)
    S_proj = normalize(pca_s.fit_transform(S_norm))
    E_proj = normalize(pca_e.fit_transform(E_norm))

    # Per-node cosines
    cosines = np.sum(S_proj * E_proj, axis=1)

    # Procrustes: find best rotation between the two spaces
    procrustes_disp = _procrustes_disparity(S_proj, E_proj)

    # Sort by cosine similarity
    sorted_indices = np.argsort(cosines)
    divergent = [(common[i], float(cosines[i])) for i in sorted_indices[:top_k]]
    convergent = [(common[i], float(cosines[i])) for i in sorted_indices[-top_k:][::-1]]

    # Fused embeddings (concatenate + PCA)
    fused = np.concatenate([S_proj, E_proj], axis=1)
    fused_dim = min(common_dim, fused.shape[1])
    pca_fused = PCA(n_components=fused_dim, random_state=42)
    fused_reduced = pca_fused.fit_transform(fused)

    result = GraphSAGEResult(
        node_ids=common,
        structural_embeddings=S,
        embedding_dim=S.shape[1],
        cosine_similarities=cosines,
        mean_cosine_similarity=float(np.mean(cosines)),
        std_cosine_similarity=float(np.std(cosines)),
        divergent_nodes=divergent,
        convergent_nodes=convergent,
        procrustes_disparity=procrustes_disp,
        fused_embeddings=fused_reduced,
    )

    logger.info(
        "embedding_comparison_complete",
        common_nodes=len(common),
        mean_cosine=result.mean_cosine_similarity,
        procrustes=procrustes_disp,
    )

    return result


def _procrustes_disparity(A: np.ndarray, B: np.ndarray) -> float:
    """Compute Procrustes disparity between two point clouds.

    Lower values mean the two embedding spaces are more structurally
    similar (after optimal rotation/scaling).
    """
    from scipy.spatial import procrustes  # type: ignore[import-untyped]

    try:
        _, _, disparity = procrustes(A, B)
        return float(disparity)
    except Exception:
        return 1.0


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------


def run_graphsage_analysis(
    store: Any,
    semantic_node_ids: list[str] | None = None,
    semantic_matrix: np.ndarray | None = None,
    embedding_provider: Any | None = None,
    embedding_key: str = "embedding",
    hidden_dim: int = 64,
    output_dim: int = 64,
    epochs: int = 50,
) -> GraphSAGEResult:
    """Train GraphSAGE and compare structural vs semantic embeddings.

    Args:
        store: GraphStore backend.
        semantic_node_ids: Pre-collected semantic node IDs.
        semantic_matrix: Pre-collected semantic embedding matrix.
        embedding_provider: Fallback provider for semantic embeddings.
        embedding_key: Property key for stored embeddings.
        hidden_dim: GraphSAGE hidden dimension.
        output_dim: GraphSAGE output dimension.
        epochs: Training epochs.

    Returns:
        GraphSAGEResult with structural embeddings and comparison metrics.
    """
    logger.info("graphsage_analysis_starting")

    # Train structural embeddings
    node_ids, structural, losses = train_graphsage(
        store, hidden_dim=hidden_dim, output_dim=output_dim, epochs=epochs,
    )

    if len(node_ids) < 3:
        logger.warning("graphsage_analysis_skipped", reason="too_few_nodes")
        return GraphSAGEResult()

    # Get semantic embeddings if not provided
    if semantic_node_ids is None or semantic_matrix is None:
        from kgbuilder.analytics.embeddings import collect_embeddings
        semantic_node_ids, semantic_matrix = collect_embeddings(
            store, embedding_provider=embedding_provider, embedding_key=embedding_key,
        )

    if len(semantic_node_ids) < 3:
        logger.warning("graphsage_no_semantic_embeddings")
        return GraphSAGEResult(
            node_ids=node_ids,
            structural_embeddings=structural,
            embedding_dim=structural.shape[1] if structural.ndim == 2 else 0,
            training_loss=losses,
        )

    # Compare
    result = compare_embeddings(
        node_ids, structural, semantic_node_ids, semantic_matrix,
    )
    result.training_loss = losses

    return result
