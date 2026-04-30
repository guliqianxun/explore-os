---
pm_id: iter-021
pm_type: iteration
title: Sprint 21 — 桌面通知 + brief 未决分组
milestone: v1.2
status: planned
start_at: 2026-04-30
end_at: 2026-05-01
---

# iter-021 Sprint 21：桌面通知 + brief 未决分组

## 战略上下文

iter-020 首位用户实测后，留下两块"低悬果"：

1. **订阅跑完没反馈**：~70s 后台跑完 14 篇 paper，UI 无任何提示
2. **未决 paper 分桶感知缺失**：speed cards 区扁平列表，新跑的 vs 累积的混在一起

合做一刀，无 schema 改动，纯 UI + Electron IPC 新增。详见 ft-031。

## 目标

| # | Feature | 优先级 | 状态 |
|---|---|---|---|
| 1 | ft-031 桌面通知 + brief 未决分组 | P1 | planned |

## Scope（按 ft-031 三块）

- A. Electron Notification API + IPC `explore:notify` + frontend notify 库 + useJobPolling 触发
- B. brief 速读区按 `created_at` 三段分桶（今日/本周/更早），更早默认折叠
- C. NavBar Papers 旁挂未决数 badge

## 关键设计决策（lock）

1. 不引第三方通知库，走 Electron 内置 `Notification` + 浏览器 Notification API 回退
2. 不改 schema，分桶只算 created_at
3. 通知只覆盖 sub run 完成，不覆盖 ingest job
4. 通知点击 = 聚焦窗口 + 跳 `#/papers?status=new`

## 验收

- pytest ≥ 371 passed
- frontend tsc 0 error
- build 主 chunk ≤ +20KB
- Electron prod 跑 sub → OS 通知弹 + 点击聚焦
- brief 速读区分今日/本周/更早三段
- NavBar badge 显示未决数

## 里程碑

- D1 上半天：A 桌面通知链路（main IPC + preload + frontend notify）
- D1 下半天：B 未决分桶 + C NavBar badge
- D1 末：实测两条订阅跑完，确认通知 + 跳转 + badge 刷新

## 风险后顾占位

填于 done 时：
- Win 11 focus assist 干扰
- 浏览器 Notification 权限授权流程
- 未决 paper 老积压会不会让"更早未决"无限增长 → 是否需要 archive 入口
