# Related Work: Prompt Injection Defense Landscape (2023–2026)

# 相關工作：Prompt Injection 防禦方案全景（2023–2026）

A survey of existing approaches, positioned against EntropyShield's deterministic fragmentation mechanism.

現有防禦方案的調查，與 EntropyShield 的決定性破碎化機制進行定位對比。

---

## 1. Preprocessing / Input Transformation Defenses 預處理層防禦

These defenses modify untrusted input *before* it reaches the LLM — the same category as EntropyShield.

這些方案在輸入送進 LLM *之前*就進行修改 — 與 EntropyShield 同一層級。

| Approach | Mechanism | Cost | Weakness | Reference |
|---|---|---|---|---|
| **Spotlighting** (Microsoft, 2024) | Delimiter/encoding to mark untrusted data | ~$0 | Syntax intact — relies on model learning to distinguish | [[1]](#references) |
| **SmoothLLM** (CMU, 2023) | N perturbed copies + output aggregation | N × LLM calls | Targets GCG suffixes; weak against natural language injection | [[2]](#references) |
| **Paraphrasing** | LLM rewrites input to strip injections | 1 LLM call | Probabilistic; paraphraser itself is attackable | [[3]](#references) |
| **IBProtector** (NeurIPS 2024) | Information bottleneck — trained compressor retains only essential info | 1 extractor pass | Requires training data and trainable component | [[4]](#references) |
| **Mixture of Encodings** (NAACL 2025) | Multiple encodings (Base64, Caesar, etc.) + aggregation | N × LLM calls | High latency from multiple forward passes | [[5]](#references) |
| **StruQ + SecAlign** (Berkeley, USENIX 2025) | Special delimiter tokens + fine-tune model to ignore data-zone instructions | $0 at inference | Requires fine-tuning; not applicable to closed-source APIs | [[6]](#references) |
| **EntropyShield** (2026) | Random character slicing (2–9 chars) destroys all syntactic structure | **$0, < 1ms** | 12.5% accuracy loss (addressable with word-boundary-aware slicing) | This work |

### Key Distinction 關鍵區別

All existing preprocessing defenses either **mark** untrusted data (Spotlighting), **encode** it (Mixture of Encodings), or **rewrite** it (Paraphrasing, IBProtector). They preserve the input's syntactic structure and rely on the model to *choose* not to follow embedded commands.

EntropyShield is the only approach that **physically destroys** syntactic structure at the character level. The defense is mathematical: if `max_len < Instruction_Trigger_Threshold`, no fragment contains a complete verb-object pair. The model cannot follow a command that no longer exists as a coherent sentence.

所有現有的預處理防禦要么**標記**不信任資料，要么**編碼**它，要么**改寫**它。它們保留了輸入的語法結構，依賴模型「選擇」不服從嵌入的指令。

EntropyShield 是唯一在字元層面**物理摧毀**語法結構的方案。防禦是數學性的：如果 `max_len < 指令觸發閾值`，任何碎片都不包含完整的動詞-受詞對。模型無法服從一個已不存在的指令。

---

## 2. Detection-Based Defenses 偵測型防禦

| Approach | Mechanism | Cost | Weakness | Reference |
|---|---|---|---|---|
| **PromptArmor** (2025) | LLM-based detector with curated system prompt | 1 LLM call | Detector model itself may be bypassed | [[7]](#references) |
| **PromptShield** (2025) | Fine-tuned classifier for injection detection | 1 classifier pass | Requires training data; novel attacks may evade | [[8]](#references) |
| **Lakera Guard** (Commercial) | Real-time API firewall with continuously updated threat database | Per-API-call pricing | Cloud-dependent; proprietary | [[9]](#references) |

Detection approaches must recognize each new attack pattern. EntropyShield is pattern-agnostic — it destroys all syntactic structure regardless of attack type, including zero-day attacks.

偵測型方案必須辨識每一種新的攻擊模式。EntropyShield 與攻擊模式無關 — 它摧毀所有語法結構，包括零日攻擊。

---

## 3. Model-Level Defenses 模型層防禦

| Approach | Mechanism | Cost | Weakness | Reference |
|---|---|---|---|---|
| **Instruction Hierarchy** (OpenAI, 2024) | Train model with explicit privilege levels (Root > System > User) | Training cost | Probabilistic; adaptive attacks can mimic higher privilege | [[10]](#references) |
| **DefensiveTokens** (ACM AISec, 2025) | Optimized special tokens prepended to input to activate security behavior | Embedding-level access required | 48.8% ASR against optimization attacks | [[11]](#references) |

Model-level defenses require access to model training or embeddings. EntropyShield works with any model as a black box — no fine-tuning, no API access, no model cooperation required.

模型層防禦需要模型訓練或嵌入層的存取權限。EntropyShield 以黑盒方式與任何模型協作 — 無需微調、無需 API 存取、無需模型配合。

---

## 4. Industry Approaches 大廠做法

| Company | Approach | Result | Key Insight |
|---|---|---|---|
| **Google DeepMind** | Iterative ART red-teaming + fine-tuning Gemini | ASR reduced by 47% | "More capable models aren't necessarily more secure" [[12]](#references) |
| **Anthropic** | RL training Claude against browser injection | ~1% ASR in browser ops | Multi-layered: permissions + classifiers + RL [[13]](#references) |
| **OpenAI** | Adversarial RL red-teaming + sandboxing | Watch Mode on sensitive sites | "Prompt injection, like social engineering, is unlikely to ever be fully solved" [[14]](#references) |

These approaches require massive engineering investment and model-level control. EntropyShield provides a complementary first-layer defense accessible to any developer.

這些方案需要巨大的工程投入和模型層控制。EntropyShield 提供任何開發者都能使用的互補性第一層防禦。

---

## 5. The Adaptive Attack Challenge 自適應攻擊的挑戰

Two landmark 2025 papers evaluated defenses against **adaptive attackers** — attackers who modify their strategy specifically to counter each defense:

2025 年兩篇里程碑論文評估了防禦方案對抗**自適應攻擊者** — 針對每種防禦專門調整策略的攻擊者：

- **"Adaptive Attacks Break Defenses Against Indirect Prompt Injection"** (NAACL 2025): Bypassed all 8 tested defenses with >50% ASR [[15]](#references)
- **"The Attacker Moves Second"** (arXiv, 2025): Bypassed all 12 tested defenses with >90% ASR using gradient descent, RL, random search, and human-guided exploration [[16]](#references)

**Key conclusion:** *"Simply adding more filters or stacking additional detectors does not resolve the underlying robustness problem."*

**關鍵結論：** *「單純堆疊更多過濾器或偵測器無法解決根本的穩健性問題。」*

### Implications for EntropyShield 對 EntropyShield 的啟示

These adaptive attacks exploit a fundamental pattern: they craft inputs that **survive the defense transformation** while remaining effective as commands. Against EntropyShield, an adaptive attacker would need to craft a payload that:

1. Functions as an executable command when randomly sliced into 2–9 character fragments
2. Maintains imperative syntax despite random character-boundary cuts and skips

This is a fundamentally harder constraint than bypassing detection (where the input remains intact) or bypassing encoding (where the transformation is reversible). However, **semantic-only attacks** — payloads that influence LLM behavior through keyword density rather than syntactic commands — remain a theoretical concern. See [Limitations](CONCEPT_PAPER.md#7-limitations-and-future-work).

這些自適應攻擊利用了一個根本模式：它們製作在**通過防禦轉換後仍然存活**的輸入。對抗 EntropyShield，攻擊者需要製作一個在被隨機切成 2-9 字元碎片後仍能作為可執行指令的載荷 — 這在本質上比繞過偵測（輸入完整）或繞過編碼（轉換可逆）更困難。然而，**純語意攻擊** — 透過關鍵詞密度而非語法指令影響 LLM 行為的載荷 — 仍是理論上的疑慮。

---

## 6. Available Benchmarks for Evaluation 可用的評估基準

| Benchmark | Scale | Type | Source |
|---|---|---|---|
| **AgentDojo** (ETH Zurich, NeurIPS 2024) | 97 tasks, 629 security test cases | Agent environment with tool use | `pip install agentdojo` [[17]](#references) |
| **OpenPromptInject** | Standardized attack/defense benchmark | Text-based injection classification | [[18]](#references) |
| **deepset/prompt-injections** | 662 prompts (263 injections + 399 legit) | Binary classification dataset | HuggingFace [[19]](#references) |
| **LLMail-Inject** (Microsoft, SaTML 2025) | 208,095 attack submissions from 839 participants | Adaptive injection in email agent | HuggingFace [[20]](#references) |

EntropyShield's current validation (Experiments 1 & 2) covers 14 attack vectors across 2 models. Scaling to these benchmarks is planned for v0.2.

EntropyShield 目前的驗證（實驗一和二）涵蓋 2 個模型上的 14 個攻擊向量。擴展至上述基準計畫在 v0.2 進行。

---

## References

1. Microsoft Research, "Defending Against Indirect Prompt Injection Attacks With Spotlighting," 2024. [Paper](https://www.microsoft.com/en-us/research/publication/defending-against-indirect-prompt-injection-attacks-with-spotlighting/)
2. Robey et al., "SmoothLLM: Defending Large Language Models Against Jailbreaking Attacks," 2023. [arXiv:2310.03684](https://arxiv.org/abs/2310.03684)
3. Jain et al., "Baseline Defenses for Adversarial Attacks Against Aligned Language Models," 2023. [Survey](https://github.com/tldrsec/prompt-injection-defenses)
4. Liu et al., "Protecting Your LLMs with Information Bottleneck," NeurIPS 2024. [arXiv:2404.13968](https://arxiv.org/abs/2404.13968)
5. "Defense against Prompt Injection Attacks via Mixture of Encodings," NAACL 2025. [Paper](https://aclanthology.org/2025.naacl-short.21/)
6. Chen et al., "StruQ: Defending Against Prompt Injection with Structured Queries," USENIX Security 2025. [Paper](https://www.usenix.org/conference/usenixsecurity25/presentation/chen-sizhe)
7. "PromptArmor: Simple yet Effective Prompt Injection Defenses," 2025. [arXiv:2507.15219](https://arxiv.org/abs/2507.15219)
8. "PromptShield: Deployable Detection of Prompt Injection Attacks," 2025. [arXiv:2501.15145](https://arxiv.org/abs/2501.15145)
9. Lakera, "Lakera Guard." [Product](https://www.lakera.ai/lakera-guard)
10. OpenAI, "The Instruction Hierarchy: Training LLMs to Prioritize Privileged Instructions," 2024. [Paper](https://openai.com/index/the-instruction-hierarchy/)
11. "Defending Against Prompt Injection With a Few DefensiveTokens," ACM AISec 2025. [arXiv:2507.07974](https://arxiv.org/abs/2507.07974)
12. Google DeepMind, "Lessons from Defending Gemini Against Indirect Prompt Injections," 2025. [arXiv:2505.14534](https://arxiv.org/abs/2505.14534)
13. Anthropic, "Mitigating the Risk of Prompt Injections in Browser Use," 2025. [Blog](https://www.anthropic.com/research/prompt-injection-defenses)
14. OpenAI, "Continuously Hardening ChatGPT Atlas Against Prompt Injection," 2025. [Blog](https://openai.com/index/hardening-atlas-against-prompt-injection/)
15. "Adaptive Attacks Break Defenses Against Indirect Prompt Injection Attacks on LLM Agents," NAACL 2025. [arXiv:2503.00061](https://arxiv.org/abs/2503.00061)
16. Sitawarin et al., "The Attacker Moves Second: Stronger Adaptive Attacks Bypass Defenses Against LLM Jailbreaks and Prompt Injections," 2025. [arXiv:2510.09023](https://arxiv.org/abs/2510.09023)
17. Debenedetti et al., "AgentDojo: A Dynamic Environment to Evaluate Attacks and Defenses for LLM Agents," NeurIPS 2024. [GitHub](https://github.com/ethz-spylab/agentdojo)
18. Liu et al., "Formalizing and Benchmarking Prompt Injection Attacks and Defenses," 2023. [GitHub](https://github.com/liu00222/Open-Prompt-Injection)
19. deepset, "Prompt Injections Dataset." [HuggingFace](https://huggingface.co/datasets/deepset/prompt-injections)
20. Microsoft, "LLMail-Inject: A Dataset from a Realistic Adaptive Prompt Injection Challenge," SaTML 2025. [arXiv:2506.09956](https://arxiv.org/abs/2506.09956)

---

*Last updated: 2026-02-16*
