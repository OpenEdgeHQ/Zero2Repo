"""CalLLMCost — accurate 4-bucket LLM USD costing from raw usage + pricing JSON."""

from calllmcost.core import compute_step_cost_usd
from calllmcost.openrouter_sync import (
    fetch_openrouter_models_payload,
    fetch_pricing_table_from_openrouter,
    model_pricing_from_openrouter_record,
)
from calllmcost.pricing import (
    ModelPricing,
    PricingTable,
    dump_pricing_table,
    load_pricing_table,
    make_pricing_table,
    step_real_cost_usd,
    SUPPORTED_PRICING_SCHEMA_VERSIONS,
)
from calllmcost.trace_audit import audit_trace_cost_metrics
from calllmcost.usage import (
    normalize_usage,
    SUPPORTED_PROVIDERS,
    UsageBuckets,
)

__all__ = [
    "SUPPORTED_PRICING_SCHEMA_VERSIONS",
    "SUPPORTED_PROVIDERS",
    "ModelPricing",
    "PricingTable",
    "UsageBuckets",
    "audit_trace_cost_metrics",
    "compute_step_cost_usd",
    "dump_pricing_table",
    "fetch_openrouter_models_payload",
    "fetch_pricing_table_from_openrouter",
    "load_pricing_table",
    "make_pricing_table",
    "model_pricing_from_openrouter_record",
    "normalize_usage",
    "step_real_cost_usd",
]

__version__ = "0.2.0"
