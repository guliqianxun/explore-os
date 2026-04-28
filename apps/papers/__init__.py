"""ft-028: Paper-centric schema 顶层模块.

新增 ``Paper`` 顶层实体（``[A-Z2-9]{8}`` 稳定 key），并把现有 5 类
material + interpret 三表的 ``paper_arxiv_id`` 字段升级为 ``paper`` FK；
同时挂上 user_* 4 张表（status / comment / tag / backlink）。

全部模型保持 SQLite 友好：jsonb 走 ``JSONField``，无 ``ArrayField`` /
``tsvector`` / raw PG SQL。
"""
