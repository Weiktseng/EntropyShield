#!/usr/bin/env python3
"""
Adaptive Resolution Reading demo — multi-resolution document triage.
"""

from entropyshield import AdaptiveReader

# Simulated academic paper (shortened)
SAMPLE_PAPER = """
Title: Advances in Neural Architecture Search for Edge Devices
Authors: A. Smith, B. Chen, C. Park
Published: 2026, Conference on Machine Learning

Abstract
This paper presents a novel approach to neural architecture search (NAS)
optimized for deployment on edge devices with limited compute budgets.
We achieve state-of-the-art accuracy-latency trade-offs on ImageNet.

1. Introduction
Deep neural networks have revolutionized computer vision, natural language
processing, and many other domains. However, deploying these models on
resource-constrained edge devices remains challenging due to their
computational and memory requirements. Previous work has explored various
compression techniques including pruning, quantization, and knowledge
distillation. In this paper, we take a different approach by directly
searching for architectures that are inherently efficient.

2. Related Work
Neural Architecture Search was first proposed by Zoph and Le (2017).
Since then, numerous improvements have been made to reduce the search
cost and improve the quality of discovered architectures. DARTS introduced
differentiable search, while EfficientNet demonstrated the effectiveness
of compound scaling. Our work builds on these foundations but introduces
a novel latency-aware search objective.

3. Method
Our approach consists of three key components:
3.1 Search Space: We define a hierarchical search space with macro-level
    topology decisions and micro-level operation choices.
3.2 Latency Predictor: A lightweight neural network that predicts
    inference latency for candidate architectures without actual deployment.
3.3 Multi-Objective Optimization: We jointly optimize accuracy and latency
    using a Pareto-optimal search strategy.

The search algorithm iterates through the following steps:
  1. Sample candidate architectures from the search space
  2. Predict accuracy using a supernet with weight sharing
  3. Predict latency using the trained predictor
  4. Update the search distribution using evolutionary strategies

4. Results
Table 1: Comparison on ImageNet
  | Model          | Top-1 Acc | Latency (ms) | FLOPs  |
  | EfficientNet-B0| 77.1%     | 12.3         | 390M   |
  | MobileNetV3    | 75.2%     | 8.1          | 219M   |
  | Ours-Small     | 76.8%     | 7.2          | 195M   |
  | Ours-Large     | 78.3%     | 11.8         | 370M   |

Figure 1 shows the Pareto frontier of our discovered architectures
compared to existing baselines.

5. Conclusion
We presented an efficient NAS framework for edge deployment that achieves
competitive accuracy with significantly reduced latency. Future work will
extend this approach to other modalities including NLP and speech.
""".strip()


def main():
    reader = AdaptiveReader(
        head_lines=8,
        tail_lines=5,
        low_res_sample_rate=0.3,
    )

    plan = reader.read(SAMPLE_PAPER)

    print("=== Adaptive Resolution Reading Demo ===\n")
    print(f"Total document: {plan.total_chars} chars")
    print(f"Preview size:   {plan.preview_chars} chars")
    print(f"Compression:    {plan.compression_ratio:.0%}")
    print(f"High-res sections found: {len(plan.high_res_sections)}")
    print()
    print("--- LLM Triage Prompt ---")
    print(plan.to_prompt())


if __name__ == "__main__":
    main()
