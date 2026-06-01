"""Tokenization + batching helpers for SFT on VulRL trajectories.

Input parquet schema (produced by ``sft_data_gen/build_sft_dataset.py``)::

    messages              JSON string of List[{role, content}] —— full conversation
    n_messages            int
    n_assistant_turns     int (>=1)
    source_cve_id         str
    source_trial_idx      int
    source_reward         float
    source_success        bool
    agent_config_name     str

We expand each row into one SFT sample **per assistant turn**: the prompt is
the conversation prefix up to that assistant message, the response is that
assistant message's content. This matches the (prompt, response) format that
SkyRL's ``examples/sft/sft_trainer.py`` consumes.

Why per-turn instead of one multi-turn sample per row?

* SkyRL's ``cross_entropy_loss`` only supervises the tail ``num_actions``
  tokens of each sequence (see ``ppo_utils.py:cross_entropy_loss`` and the
  ``response_length`` metadata field). One assistant turn per sample is the
  pattern that already works end-to-end.
* The prefix tokens are still attended to, just not scored. Training cost
  per sample scales linearly with prompt length, but compared to the GPU
  cost of LM forward+backward, the redundant tokenization is negligible.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd
import torch

from skyrl_train.training_batch import TrainingInputBatch


@dataclass
class SFTSample:
    """One (prompt, response) tokenization-ready training sample."""
    input_ids: List[int]        # full sequence (prompt + response)
    attention_mask: List[int]   # all 1s (we left-pad later)
    num_actions: int            # response length in tokens
    source_cve_id: str
    source_trial_idx: int
    source_reward: float


# ---------------------------------------------------------------------------
# Per-row expansion
# ---------------------------------------------------------------------------

def expand_row_to_samples(
    messages: List[Dict[str, str]],
    tokenizer,
    max_length: int,
    *,
    source_cve_id: str = "",
    source_trial_idx: int = -1,
    source_reward: float = 0.0,
) -> List[SFTSample]:
    """Expand one full conversation into one SFTSample per assistant turn.

    For each assistant turn at index ``k``:
        prompt = apply_chat_template(messages[:k], add_generation_prompt=True)
        full   = apply_chat_template(messages[:k+1])
        num_actions = len(full) - len(prompt)

    Samples whose full sequence exceeds ``max_length`` are dropped (instead of
    truncated) to avoid silently losing the supervision target.
    """
    samples: List[SFTSample] = []

    for k, msg in enumerate(messages):
        if msg.get("role") != "assistant":
            continue
        if not msg.get("content"):
            continue

        prefix = messages[:k]
        full = messages[:k + 1]

        # apply_chat_template returns a List[int] when tokenize=True
        try:
            prompt_ids = tokenizer.apply_chat_template(
                prefix, add_generation_prompt=True, tokenize=True
            )
            full_ids = tokenizer.apply_chat_template(
                full, add_generation_prompt=False, tokenize=True
            )
        except Exception:
            # Some chat templates choke on system-only or empty prefixes — skip.
            continue

        if not isinstance(prompt_ids, list):
            prompt_ids = list(prompt_ids)
        if not isinstance(full_ids, list):
            full_ids = list(full_ids)

        # Sanity check: full sequence should start with the prompt
        if len(full_ids) <= len(prompt_ids):
            continue

        # Drop oversize samples instead of truncating the response
        if len(full_ids) > max_length:
            continue

        num_actions = len(full_ids) - len(prompt_ids)
        samples.append(SFTSample(
            input_ids=full_ids,
            attention_mask=[1] * len(full_ids),
            num_actions=num_actions,
            source_cve_id=source_cve_id,
            source_trial_idx=source_trial_idx,
            source_reward=source_reward,
        ))

    return samples


def load_and_tokenize_parquet(
    parquet_path: str,
    tokenizer,
    max_length: int,
    limit: Optional[int] = None,
) -> List[SFTSample]:
    df = pd.read_parquet(parquet_path)
    required = {"messages"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Parquet missing required columns: {missing}")

    samples: List[SFTSample] = []
    for _, row in df.iterrows():
        messages_field = row["messages"]
        if isinstance(messages_field, str):
            try:
                messages = json.loads(messages_field)
            except json.JSONDecodeError:
                continue
        else:
            messages = list(messages_field) if messages_field is not None else []

        if not messages:
            continue

        row_samples = expand_row_to_samples(
            messages,
            tokenizer,
            max_length=max_length,
            source_cve_id=str(row.get("source_cve_id", "")),
            source_trial_idx=int(row.get("source_trial_idx", -1) or -1),
            source_reward=float(row.get("source_reward", 0.0) or 0.0),
        )
        samples.extend(row_samples)

        if limit is not None and len(samples) >= limit:
            samples = samples[:limit]
            break

    return samples


# ---------------------------------------------------------------------------
# Batch collation (mirrors SkyRL examples/sft/sft_trainer.collate_sft_batch)
# ---------------------------------------------------------------------------

def collate_sft_batch(
    samples: Sequence[SFTSample],
    tokenizer,
) -> TrainingInputBatch:
    """Collate samples into a TrainingInputBatch with left-padding.

    Output shapes::

        sequences         [B, max_len]            # token IDs
        attention_mask    [B, max_len]            # 1 for tokens, 0 for pad
        loss_mask         [B, max_num_actions]    # 1 for response tokens only
    """
    assert len(samples) > 0
    max_len = max(len(s.input_ids) for s in samples)
    max_num_actions = max(s.num_actions for s in samples)

    pad_id = tokenizer.pad_token_id
    if pad_id is None:
        pad_id = tokenizer.eos_token_id

    sequences: List[List[int]] = []
    attention_masks: List[List[int]] = []
    loss_masks: List[List[int]] = []

    for s in samples:
        pad_len = max_len - len(s.input_ids)
        sequences.append([pad_id] * pad_len + s.input_ids)
        attention_masks.append([0] * pad_len + s.attention_mask)
        action_pad = max_num_actions - s.num_actions
        loss_masks.append([0] * action_pad + [1] * s.num_actions)

    batch = TrainingInputBatch({
        "sequences":      torch.tensor(sequences, dtype=torch.long),
        "attention_mask": torch.tensor(attention_masks, dtype=torch.long),
        "loss_mask":      torch.tensor(loss_masks, dtype=torch.long),
    })
    batch.metadata = {"response_length": max_num_actions}
    return batch


def iter_batches(
    samples: Sequence[SFTSample],
    tokenizer,
    batch_size: int,
    shuffle: bool = True,
    seed: int = 42,
) -> Iterable[TrainingInputBatch]:
    """Yield collated training batches; one pass over the dataset."""
    order = list(range(len(samples)))
    if shuffle:
        import random
        random.Random(seed).shuffle(order)

    for start in range(0, len(order), batch_size):
        batch_idx = order[start:start + batch_size]
        if not batch_idx:
            continue
        batch_samples = [samples[i] for i in batch_idx]
        yield collate_sft_batch(batch_samples, tokenizer)
