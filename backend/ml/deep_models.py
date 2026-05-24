from __future__ import annotations

import torch
from torch import nn
import torch.nn.functional as F


class CharCNN(nn.Module):
    def __init__(
        self,
        vocab_size: int,
        embedding_dim: int = 64,
        num_filters: int = 128,
        kernel_sizes: tuple[int, ...] = (3, 4, 5),
        dropout: float = 0.3,
    ):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, embedding_dim, padding_idx=0)
        self.convs = nn.ModuleList(
            nn.Conv1d(embedding_dim, num_filters, kernel_size=kernel_size)
            for kernel_size in kernel_sizes
        )
        self.dropout = nn.Dropout(dropout)
        self.fc = nn.Linear(num_filters * len(kernel_sizes), 1)

    def forward(self, x):
        embedded = self.embedding(x).transpose(1, 2)
        conv_outputs = [F.relu(conv(embedded)) for conv in self.convs]
        pooled = [F.max_pool1d(output, kernel_size=output.size(2)).squeeze(2) for output in conv_outputs]
        features = self.dropout(torch.cat(pooled, dim=1))
        return self.fc(features).squeeze(1)


class CharBiLSTM(nn.Module):
    def __init__(
        self,
        vocab_size: int,
        embedding_dim: int = 64,
        hidden_size: int = 128,
        num_layers: int = 1,
        dropout: float = 0.3,
    ):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, embedding_dim, padding_idx=0)
        lstm_dropout = dropout if num_layers > 1 else 0.0
        self.lstm = nn.LSTM(
            embedding_dim,
            hidden_size,
            num_layers=num_layers,
            batch_first=True,
            bidirectional=True,
            dropout=lstm_dropout,
        )
        self.dropout = nn.Dropout(dropout)
        self.fc = nn.Linear(hidden_size * 2, 1)

    def forward(self, x):
        embedded = self.embedding(x)
        output, _ = self.lstm(embedded)
        features = torch.max(output, dim=1).values
        return self.fc(self.dropout(features)).squeeze(1)


def build_deep_model(model_type: str, vocab_size: int, config: dict):
    model_type = (model_type or "cnn").lower()
    if model_type == "bilstm":
        return CharBiLSTM(
            vocab_size=vocab_size,
            embedding_dim=int(config.get("embedding_dim", 64)),
            hidden_size=int(config.get("hidden_size", 128)),
            num_layers=int(config.get("num_layers", 1)),
            dropout=float(config.get("dropout", 0.3)),
        )
    return CharCNN(
        vocab_size=vocab_size,
        embedding_dim=int(config.get("embedding_dim", 64)),
        num_filters=int(config.get("num_filters", 128)),
        dropout=float(config.get("dropout", 0.3)),
    )
