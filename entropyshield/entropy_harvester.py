"""
Conversational Entropy Harvester — Contextual Entropy Boost for HEF

Collects unpredictable micro-features from LLM conversations and mixes
them with OS-level CSPRNG to produce seeds that attackers cannot reconstruct.

Design principle (same as Linux kernel's RDRAND mixing):
    final_seed = SHA-256(conversation_entropy + os.urandom)
                          ↑                      ↑
                      bonus entropy          security floor

Conversation entropy only ADDS to unpredictability — even if fully compromised,
security never falls below pure os.urandom.

Entropy sources:
    1. Response Timing Jitter — nanosecond-level API latency affected by
       server load, network path, TCP congestion, GPU kernel scheduling.
    2. Token-level Byte Entropy — SHA-256 of LLM responses; temperature
       sampling means identical prompts produce different token trajectories.
    3. Cross-message Delta — behavioral fingerprint combining message length,
       trailing/leading characters, and timing.
"""

import hashlib
import os
import struct
import time
from typing import Optional


class ConversationalEntropyHarvester:
    """
    Accumulates entropy from conversation turns and produces seeds.

    Usage:
        harvester = ConversationalEntropyHarvester()

        # Record each conversation turn
        t0 = time.time_ns()
        response = call_llm(user_message)
        t1 = time.time_ns()
        harvester.record_turn(user_message, response, latency_ns=t1 - t0)

        # Get a seed for fragmentation
        seed = harvester.make_seed()
    """

    def __init__(self) -> None:
        self._entropy_pool: list[bytes] = []
        # Mix in process-level boot entropy immediately
        self._mix_bytes(struct.pack(">Q", time.time_ns()))
        self._mix_bytes(struct.pack(">I", os.getpid()))

    def _mix_bytes(self, data: bytes) -> None:
        self._entropy_pool.append(data)

    def record_turn(
        self,
        user_message: str,
        model_response: str,
        latency_ns: Optional[int] = None,
    ) -> None:
        """
        Harvest entropy from a single conversation turn.

        Args:
            user_message:   The user's input text.
            model_response: The LLM's response text.
            latency_ns:     Request-to-response latency in nanoseconds.
                            If None, current time_ns is used as proxy.
        """
        if latency_ns is None:
            latency_ns = time.time_ns()

        # Source 1: Response Timing Jitter
        # Nanosecond latency is affected by server load, network path,
        # TCP congestion window, GPU kernel scheduling — unreproducible.
        self._mix_bytes(struct.pack(">Q", latency_ns))

        # Source 2: Token-level Byte Entropy
        # SHA-256 of the full response — temperature sampling means even
        # identical prompts yield different token trajectories.
        resp_hash = hashlib.sha256(model_response.encode("utf-8")).digest()
        self._mix_bytes(resp_hash)

        # Source 3: Cross-message Delta
        # Behavioral fingerprint: message length, trailing chars, leading
        # response chars, timing — the combinatorial space is enormous.
        tail_chars = user_message[-20:] if len(user_message) >= 20 else user_message
        head_chars = model_response[:20] if len(model_response) >= 20 else model_response
        delta = f"{len(user_message)}:{tail_chars}:{head_chars}:{latency_ns}"
        delta_hash = hashlib.sha256(delta.encode("utf-8")).digest()
        self._mix_bytes(delta_hash)

    @property
    def pool_size(self) -> int:
        """Number of entropy contributions accumulated."""
        return len(self._entropy_pool)

    def _compress_pool(self) -> bytes:
        """Compress all accumulated entropy into a single 256-bit digest."""
        combined = b"".join(self._entropy_pool)
        return hashlib.sha256(combined).digest()

    def make_seed(self) -> int:
        """
        Produce a 256-bit integer seed.

        final = SHA-256(conversation_entropy ‖ os.urandom(32))

        The os.urandom component guarantees a security floor —
        conversation entropy is purely additive.
        """
        conversation_entropy = self._compress_pool()
        system_entropy = os.urandom(32)
        final = hashlib.sha256(conversation_entropy + system_entropy).digest()
        return int.from_bytes(final, "big")

    def make_seed_bytes(self) -> bytes:
        """Produce 32 bytes (256-bit) of mixed seed material."""
        conversation_entropy = self._compress_pool()
        system_entropy = os.urandom(32)
        return hashlib.sha256(conversation_entropy + system_entropy).digest()


def make_seed(context_text: str = "") -> int:
    """
    Quick one-shot seed: os.urandom + timestamp + optional context hash.

    For callers that don't maintain a full ConversationalEntropyHarvester
    but still want better-than-default seeding.

    Args:
        context_text: Any available context string (user message, etc.)

    Returns:
        Integer seed suitable for random.seed() or random.Random().
    """
    parts = [
        os.urandom(32),
        struct.pack(">Q", time.time_ns()),
    ]
    if context_text:
        parts.append(hashlib.sha256(context_text.encode("utf-8")).digest())
    return int.from_bytes(hashlib.sha256(b"".join(parts)).digest(), "big")
