"""apps.llm — LLM 中台层（ft-034 P0-1 / P0-2）.

集中管理：
- HTTP client（chat / chat_json / extract_json / build_image_content）
- error 体系（LLMError + Timeout / RateLimit / JsonParse 子类）
- prompt registry（7 个能力 SYSTEM 字符串）
- ModelProfile registry（能力 → model+max_tokens+temperature）
- budgets（截断阈值常量集中地）

老 ``interpret/llm.py`` 已降级为 thin re-export wrapper（保留 1 周观察期）。
"""
