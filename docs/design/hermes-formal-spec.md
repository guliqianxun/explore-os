---
pm_id: spec-explore-os
pm_type: specification
title: explore-os Formal Specification v0.2 — 观点状态机 + 活跃度 + 记忆/编排双层
status: planned
version: 0.2.0
milestone: v1.4
created_at: 2026-05-04
depends_on: [ft-028]
---

# explore-os Formal Specification v0.2

**v0.1 → v0.2 变更**：
- 原子单元从 paper 改为**观点 (viewpoint / claim)**
- 废弃 per-topic 五态状态机（冷→接触→深入→掌握→冷退），替换为 $\sigma_v$（观点状态机）+ $A$（连续活跃度）
- 废弃 $N, M$ 硬阈值——观点粒度天然适应 paper 差异
- 引入"固化"概念：$\sigma_v \geq$ 确认的观点进入可检索记忆

---

## 0. Notation

| Symbol | Meaning |
|--------|---------|
| $\mathcal{V}$ | 观点空间（viewpoints / claims） |
| $\mathcal{E}$ | 证据单元（figures, tables, equations, sections） |
| $\mathcal{P}$ | 论文空间：$p = \{v_1, \dots, v_n\} \subset \mathcal{V}$ |
| $\mathcal{T}$ | 主题空间（topics） |
| $\mathcal{U}$ | 用户（$|\mathcal{U}| = 1$，但保留 $u$ 维度） |
| $\tau \in \mathbb{R}^+$ | 时间 |

---

## 1. Atom: Viewpoint — $\mathcal{V}$

一个观点 $v \in \mathcal{V}$：

$$
v = (\text{text}, \;\pi(v), \;\kappa(v), \;p, \;t)
$$

| 字段 | 含义 |
|------|------|
| $\text{text}$ | 作者的主张陈述（1-2 句） |
| $\pi(v) \subseteq \mathcal{E}$ | 支撑证据集 |
| $\kappa(v)$ | 证据方法论类型：$\{\text{ablation}, \text{benchmark}, \text{theoretical}, \text{anecdotal}\}$ |
| $p \in \mathcal{P}$ | 来源论文 |
| $t \in \mathcal{T}$ | 主题标签 |

### 1.1 不变性约束

$$
|\pi(v)| \geq 1
$$

无证据的观点**不是观点**——丢弃。

### 1.2 为什么观点是原子

一篇 30-claim 的 survey 和一篇 3-claim 的 short paper，在 paper 粒度无法比较。在观点粒度**天然可比**。

固化、关联、内化——这些认知动作都作用在观点上，不是论文上。

---

## 2. Decompose — $\Delta$

$$
\Delta: \mathcal{P} \longrightarrow 2^{\mathcal{V}}
$$

$$
\Delta(p) = \{v_1, \dots, v_n\}
$$

**实现**：`apps/interpret/` L1 LLM call（已完成）。Post-processing 确保 $|\pi(v)| \geq 1$。

---

## 3. 观点状态机 — $\sigma_v$

观点在用户认知中的迁移：

### 3.1 五态

$$
\sigma_v: \mathcal{U} \times \mathcal{V} \longrightarrow \Omega_v
$$

$$
\Omega_v = \{\text{unseen}, \text{exposed}, \text{confirmed}, \text{linked}, \text{internalized}\}
$$

| 态 | 含义 | 触发 |
|----|------|------|
| **unseen** | 论文读了但这个观点没被注意 | 默认始态 |
| **exposed** | 用户知道这个观点存在 | 读了 paper $p$，$v \in \Delta(p)$ 自动进入 |
| **confirmed** | 用户看了证据 | 展开 claim card / 放大 figure / 读了对应 section |
| **linked** | 用户把这个观点和另一个连起来了 | 创建 claim-level backlink $L(v_a, v_b)$ |
| **internalized** | 用户在此基础上形成了自己的思考 | 写入了 thread，引用了 $v$ |

### 3.2 转移规则

```
 unseen ─── READ(p) ──→ exposed ─── VIEW_EVIDENCE(v) ──→ confirmed
                                                              │
                                              LINK_CLAIM(v_a, v_b)
                                                              │
                                                              ▼
                                                           linked ──→ internalized
                                                              │         THREAD_WRITE(v)
                                                              │
                                                              ▼
                                                           linked
```

转移是**不可逆的**——用户不会"忘掉"一个验证过的观点。

唯一可逆的情况：$L(v_a, v_b)$ 被断开了 → linked → confirmed。

### 3.3 观点权重

每个态对活跃度贡献不同：

$$
w(\sigma_v) = \begin{cases}
0.00 & \text{unseen} \\
0.05 & \text{exposed} \\
0.15 & \text{confirmed} \\
0.30 & \text{linked} \\
0.50 & \text{internalized}
\end{cases}
$$

### 3.4 事件源 → $\sigma_v$ 转移

| 事件 | $\sigma_v$ 转移 |
|------|----------------|
| 用户读了论文 $p$ | $\forall v \in \Delta(p)$: unseen → exposed |
| 用户展开 claim card / 放大 figure | exposed → confirmed |
| 用户创建 $L(v_a, v_b)$ | $v_a, v_b$: confirmed → linked |
| 用户在 thread 中引用 $v$ | linked → internalized |
| 用户断开 $L(v_a, v_b)$ | $v_a$: linked → confirmed |

---

## 4. 活跃度 — $A$

活跃度是**连续标量**，不是状态机。回答"这个 topic 在我脑子里还热不热"。

$$
A: \mathcal{U} \times \mathcal{T} \times \tau \longrightarrow [0, 1]
$$

$$
A_\tau(u, t) = \frac{
  \displaystyle\sum_{v \in \mathcal{V}_t}
  w(\sigma_v(u, v)) \cdot e^{-(\tau - \tau_{\text{last}}(v)) / \lambda_A}
}{
  \displaystyle\max_{t'} \sum_{v \in \mathcal{V}_{t'}}
  w(\sigma_v(u, v)) \cdot e^{-(\tau - \tau_{\text{last}}(v)) / \lambda_A}
}
$$

- $\lambda_A = 14$ 天（活跃半衰期短——兴趣冷得快）
- $\tau_{\text{last}}(v)$ = 用户最后一次对 $v$ 做任何操作的时间
- 归一化方式：除以**当前最热 topic 的值**（不是 sum to 1——否则所有 topic 看起来都很冷）

### 4.1 活跃度决定系统行为

| $A(u, t)$ | 行为 |
|-----------|------|
| $> 0.5$ | 热点 topic。brief feed 加权 +30%。启用 gap 检测 |
| $0.2 \sim 0.5$ | 温 topic。加权 +10%。不主动推 gap |
| $< 0.2$ | 冷 topic。只被动响应 SEARCH。不推、不评、不建 gap |

---

## 5. 固化度 — $C$

固化度回答"这个 topic 我掌握了多少"，和活跃度**正交**。

$$
C: \mathcal{U} \times \mathcal{T} \longrightarrow [0, 1]
$$

$$
C(u, t) = \frac{
  |\{v \in \mathcal{V}_t : \sigma_v(u, v) \geq \text{confirmed}\}|
}{
  |\{v \in \mathcal{V}_t : \sigma_v(u, v) \geq \text{exposed}\}| + 1
}
$$

**与 $A$ 的关系**：

- 高活跃 + 低固化 → 正在大量阅读但还没消化（"curious" 阶段）
- 低活跃 + 高固化 → 已经掌握，长期没碰（"冷退"）
- 高活跃 + 高固化 → 正在 active 使用已掌握知识（"创造"阶段）
- 低活跃 + 低固化 → 不关心这个 topic

**没有固定阈值**——$A$ 和 $C$ 的乘积决定推荐强度。

---

## 6. 轨迹 — $\Gamma$

### 6.1 活跃度轨迹

$$
\Gamma_A(t): \tau \longmapsto A_\tau(u, t)
$$

### 6.2 固化度轨迹

$$
\Gamma_C(t): \tau \longmapsto C(u, t)
$$

### 6.3 漂移检测

$$
\text{drift}_A(t, \tau_1, \tau_2) = A_{\tau_2}(u, t) - A_{\tau_1}(u, t)
$$

$$
\text{drift}_C(t, \tau_1, \tau_2) = C_{\tau_2}(u, t) - C_{\tau_1}(u, t)
$$

$A$ 的陡升 → 新热点。$A$ 的陡降 → 兴趣转移。$C$ 的平稳上升 → 稳定学习。$C$ 的停滞 → 可能需要主动介入（推荐更深层的内容）。

### 6.4 转向论文

读完 $p$ 后 topic 活跃度分布发生显著变化：

$$
\text{pivot}(p) \iff D_{\text{KL}}(A_{\tau(p)} \;\|\; A_{\tau(p) + 7\text{d}}) > \theta_{\text{pivot}}
$$

$\theta_{\text{pivot}} = 0.30$。

---

## 7. 缺口 — $G$

### 7.1 主题关系图

$$
\mathcal{G} = (\mathcal{T}, \mathcal{R}), \quad \mathcal{R} \subseteq \mathcal{T} \times \mathcal{T} \times \{\text{prereq}, \text{sub}, \text{app}, \text{rel}\}
$$

### 7.2 前置缺口

用户在学 $t$ 但 prerequisite $t'$ 固化不足：

$$
G_{\text{prereq}}(u, \tau) = \{(t, t') \mid
(t, t', \text{prereq}) \in \mathcal{R}
\;\land\; A_\tau(u, t) > 0.3
\;\land\; C(u, t') < 0.3\}
$$

### 7.3 经典缺口

topic 内未被用户接触的高引用观点：

$$
G_{\text{canonical}}(u, \tau) = \{(t, v) \mid
A_\tau(u, t) > 0.3
\;\land\; \sigma_v(u, v) = \text{unseen}
\;\land\; \text{cited\_by}(v) > \theta_{\text{cite}}\}
$$

### 7.4 衰减缺口

已固化的 topic 长期无活跃：

$$
G_{\text{decay}}(u, \tau) = \{t \mid
C(u, t) > 0.5
\;\land\; \tau - \tau_{\text{last}}(t) > 90\text{d}\}
$$

触发"复习提醒"：推一篇该 topic 的经典论文。

---

## 8. 边界 — $B$

系统对自己知识覆盖的诚实声明。

### 8.1 三态诚实标记

用户查询 $q$ 映射到 topic $t$：

$$
B(u, q) = \begin{cases}
\text{known}     & \exists v \in \mathcal{V}_t: \sigma_v(u, v) \geq \text{confirmed} \\
\text{indexed}    & |\mathcal{V}_t| > 0 \;\land\; \forall v \in \mathcal{V}_t: \sigma_v(u, v) < \text{confirmed} \\
\text{unknown}    & \mathcal{V}_t = \varnothing
\end{cases}
$$

### 8.2 边界外的行为约束

$$
B(u, q) = \text{unknown} \implies \text{silence}
$$

不编造。不调用 LLM 生成"可能的答案"。只返回：**"系统未索引此方向的论文。"**

---

## 9. 交联 — $L$

观点间的用户建立的关联。

$$
L: \mathcal{V} \times \mathcal{V} \longrightarrow \{\text{agree}, \text{conflict}, \text{refine}, \text{null}\}
$$

### 9.1 自动建议（不自动建）

| $L(v_a, v_b)$ | 建议条件 |
|---------------|---------|
| agree | $\pi(v_a) \cap \pi(v_b) \neq \varnothing$ 且方向一致 |
| conflict | 共同 benchmark + 方向相反（"improves" vs "worsens"） |
| refine | $v_b$ 是 $v_a$ 的推广 / 泛化（$v_b$ 引用了 $v_a$ 作为 baseline） |

### 9.2 核心约束

**系统标记矛盾，不裁决对错。**

用户负责判断哪个观点更可信。系统只提供"这两个观点说不一致"的信号。

---

## 10. 回响 — Echo

### 10.1 线程

用户创建的跨论文思考线：

$$
\text{thread} = (\text{title}, \; \text{body}, \; V \subset \mathcal{V}, \; \vec{n}_\tau)
$$

其中 $\vec{n}_\tau = (n_{\tau_1}, n_{\tau_2}, \dots)$ 是追加式笔记序列。每步只追加——不可修改、不可删除。

### 10.2 约束

$$
\mathbb{1}[\text{system\_created}] \equiv 0
$$

线程**永不自动生成**。系统可以建议"这篇新论文和 thread X 相关"，但不代劳。

### 10.3 线程中的观点引用

当用户在 thread 中引用 $v$ → $\sigma_v$ 从 linked → internalized。

### 10.4 未决问题

$$
Q_{\text{open}}(u) = \{q_1, q_2, \dots\}
$$

系统监测新 $v$ 是否命中 $q_i$：

$$
\text{hit}(q, v) \iff \text{sim}(\text{embed}(q), \text{embed}(v.\text{text})) > \theta_{\text{hit}}
$$

命中 → 推送通知："这篇论文的这条观点可能回应了你的问题。"

---

## 11. 合成 — $\Psi$

### 11.1 对比矩阵

用户选取 $V_{\text{sel}} = \{v_1, \dots, v_k\}$：

$$
\text{Synth}_{\text{contrast}}(V_{\text{sel}}) =
\begin{bmatrix}
& v_1 & v_2 & \cdots \\
\text{topic}   & t_1 & t_2 & \cdots \\
\text{evidence} & |\pi(v_1)| & |\pi(v_2)| & \cdots \\
\kappa         & \kappa(v_1) & \kappa(v_2) & \cdots \\
L \text{ pairs} & \cdots & \cdots & \cdots \\
\text{user notes} & \cdots & \cdots & \cdots
\end{bmatrix}
$$

### 11.2 叙述骨架

$$
\Psi(V_{\text{sel}}, u): 2^{\mathcal{V}} \times \mathcal{U} \longrightarrow \text{Outline}
$$

确定性排列规则（按优先级）：
1. 时间序：按 $\tau_{\text{first\_exposed}}(v)$
2. 前置序：若 $(t_i, t_j, \text{prereq}) \in \mathcal{R}$，$v_{t_i}$ 排在 $v_{t_j}$ 之前
3. 细化序：若 $L(v_a, v_b) = \text{refine}$，$v_a$ 在 $v_b$ 前
4. 冲突并列：$L(v_a, v_b) = \text{conflict}$ → 并排

LLM 仅用于润色——排列本身是确定性的。

---

## 12. 校准 — Calibration

### 12.1 隐式纠偏信号

系统**高估**了 topic $t$：

$$
\text{overestimated}(t) \iff A_\tau(u, t) > 0.3 \;\land\; C(u, t) < 0.2 \;\land\; \exists v \in \mathcal{V}_t^{\text{recent}}: \tau_{\text{drop}}(v) < \tau_{\text{avg\_read}}
$$

用户活跃但不消化 → 系统推的太快、太深。

系统**低估**了 topic $t$：

$$
\text{underestimated}(t) \iff A_\tau(u, t) < 0.2 \;\land\; C(u, t) > 0.6
$$

用户固化了但长期不活跃 → 系统过早停止推送。

### 12.2 自适应

周期性调整：

$$
\lambda_A \leftarrow \lambda_A \cdot \left(1 + \alpha \cdot \frac{|\text{overestimated}|}{|\mathcal{T}_{\text{active}}|}\right)
$$

---

## 13. 冷启动 — Bootstrap

### 13.1 初始态

用户进入系统时：

$$
\forall v \in \mathcal{V}: \sigma_v(u, v) = \text{unseen}
$$

$$
A(u, \cdot) = \vec{0}, \quad C(u, \cdot) = \vec{0}
$$

### 13.2 启动策略

1. 用户声明兴趣关键词 → 映射到 $\mathcal{T}$ → 初始化 $\mathcal{R}$（prereq 关系）
2. 用户上传阅读历史 / Zotero `.bib` → 批量创建 $v$ → 标记为 exposed
3. 前 14 天主推送"热门论文"而非个性化推荐——$A$ 和 $C$ 在积累，gap 和 guidance 暂不可靠
4. 当 $|\{v: \sigma_v \geq \text{confirmed}\}| \geq 10$ → 冷启动结束，全功能激活

---

## 14. 系统动力学 — $\Phi$

$$
\Phi: (\mathcal{P}, \mathcal{V}, \mathcal{E}, \mathcal{T}, \mathcal{R}) \times (\sigma_v, A, C, L, \mathcal{TH}) \times \tau \longrightarrow (\sigma_v, A, C, L, \mathcal{TH})_{(\tau + \Delta\tau)}
$$

每步推进 $\Delta\tau = 24\text{h}$：

```
1. new p → Δ(p) → V 增长                     (Decompose)
2. user actions → σ_v 更新                    (Viewpoint state machine)
3. crunch: A, C 重算                          (Activity + Consolidation)
4. crunch: G, B 重算                          (Gap + Boundary)
5. user optional: L, TH updates               (Cross-link + Echo)
6. periodic: calibration adjusts λ_A           (Calibration)
```

---

## 15. 全局不变量

$$
\begin{aligned}
&(1) \quad \forall v \in \mathcal{V}: |\pi(v)| \geq 1 \\
&(2) \quad \sigma_v \text{ transitions are forward-only (except linked → confirmed on unlink)} \\
&(3) \quad B(u, q) = \text{unknown} \implies \text{no generated answer} \\
&(4) \quad \text{system never creates threads or claim-level links} \\
&(5) \quad \text{conflict is labeled, not adjudicated}
\end{aligned}
$$

---

## 16. 数据表

| 表 | 用途 | 要素 |
|----|------|------|
| `interpret_claims` | $v$ 本体（已有） | $\mathcal{V}$ |
| `interpret_claim_evidence` | $\pi(v)$ 映射（已有） | $\pi$ |
| `papers_user_status` | $p$ 阅读状态（已有） | exposed 触发 |
| `papers_user_comment` | 用户笔记（已有） | Echo 原料 |
| `papers_user_tag` | 标签映射到 $t$（已有） | topic 种子 |
| **`hermes_vp_state`** | $\sigma_v(u, v)$ per-user per-viewpoint | Viewpoint state machine |
| **`hermes_vp_event`** | viewpoint 事件日志（append-only） | $\sigma_v$ 转移溯源 |
| **`hermes_topic`** | topic 节点 | $\mathcal{T}$ |
| **`hermes_topic_edge`** | topic 关系 | $\mathcal{R}$ |
| **`hermes_activity`** | $A(u, t, \tau)$ 时间序列 | Activity |
| **`hermes_claim_link`** | $L(v_a, v_b)$ | Cross-link |
| **`hermes_thread`** | 线程 | Echo |
| **`hermes_thread_note`** | 线程笔记序列 | Echo |
| **`hermes_open_question`** | 未决问题 | Echo |

---

## 17. 实施阶段（修正）

| Phase | 内容 | 新表 |
|-------|------|------|
| **H0** | $\sigma_v$ 状态机 + 事件日志 | `hermes_vp_state`, `hermes_vp_event` |
| **H1** | $A$ 活跃度计算 | `hermes_activity` |
| **H2** | $C$ 固化度 + topic taxonomy 种子 | `hermes_topic`, `hermes_topic_edge` |
| **H3** | $G$ 缺口 + $B$ 边界 | 纯计算 |
| **H4** | $L$ 交联 + $\Psi$ 合成骨架 | `hermes_claim_link` |
| **H5** | Echo 线程 + $Q_{\text{open}}$ | `hermes_thread`, `hermes_thread_note`, `hermes_open_question` |
| **H6** | Calibration 自适应 | 参数更新 |

---

## 18. 参考

- ft-028 Paper-centric schema + user_* 层
- ft-033 Brief 内容处理层
- CLAUDE.md: 确定性产出 → 工具化；语义理解 → LLM
- CLAUDE.md: "两条路" 解压 vs 解读
