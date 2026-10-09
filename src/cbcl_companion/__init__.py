"""CBCL Companion: parent-friendly guide + pre-consultation Q&A for K-CBCL reports.

Design principle: the LLM never interprets numbers. A deterministic rules layer
classifies every score using the report's own thresholds and hands the LLM a
fixed list of facts. The LLM only rewrites those facts in plain Korean, and a
guard layer verifies the output never says more than the report does.
"""

__version__ = "0.1.0"
