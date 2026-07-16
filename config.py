"""Neelvak AIOS Global Configuration Registry.

Separates infrastructure, models, and execution parameters from system logic.
Supports tri-provider dynamic routing with ordered failover chains.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Max concurrent runtimes handled by the supervisory queue
MAX_CONCURRENT_RUNTIMES = 5

# =====================================================================
# PROVIDER API KEY REGISTRY
# =====================================================================
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# =====================================================================
# PROVIDER HEALTH-PROBE ENDPOINTS
# =====================================================================
PROVIDER_PROBES = {
    "groq": "https://api.groq.com/openai/v1/models",
    "openrouter": "https://openrouter.ai/api/v1/models",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/models"
}

# =====================================================================
# PROVIDER API ENDPOINT REGISTRY
# =====================================================================
PROVIDER_CHAT_ENDPOINTS = {
    "groq": "https://api.groq.com/openai/v1/chat/completions",
    "openrouter": "https://openrouter.ai/api/v1/chat/completions",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
}

# =====================================================================
# PROVIDER → API KEY MAPPING
# =====================================================================
PROVIDER_KEY_MAP = {
    "groq": "GROQ_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "gemini": "GEMINI_API_KEY"
}

# =====================================================================
# MASTER CAPABILITY CATALOGUE — TRI-PROVIDER ROUTING CHAINS
#
# Each tier contains an ordered `routing_chain` of fallback models.
# The ModelRouter walks the chain top-to-bottom until a healthy
# provider responds successfully.
# =====================================================================
CAPABILITY_CATALOGUE = {
    "tier_1_fast": {
        "tier": "LOW",
        "routing_chain": [
            {
                "provider": "groq",
                "model": "llama-3.1-8b-instant",
                "cost_per_1k": 0.00005,
                "context_window_k": 128,
                "vision_capable": False
            },
            {
                "provider": "gemini",
                "model": "gemini-2.0-flash-lite",
                "cost_per_1k": 0.00004,
                "context_window_k": 1000,
                "vision_capable": False
            },
            {
                "provider": "openrouter",
                "model": "anthropic/claude-3.5-haiku",
                "cost_per_1k": 0.00025,
                "context_window_k": 200,
                "vision_capable": False
            }
        ]
    },
    "tier_2_standard": {
        "tier": "STANDARD",
        "routing_chain": [
            {
                "provider": "groq",
                "model": "llama-3.3-70b-versatile",
                "cost_per_1k": 0.00059,
                "context_window_k": 128,
                "vision_capable": False
            },
            {
                "provider": "gemini",
                "model": "gemini-2.0-flash",
                "cost_per_1k": 0.00010,
                "context_window_k": 1000,
                "vision_capable": True
            },
            {
                "provider": "openrouter",
                "model": "anthropic/claude-3.5-sonnet",
                "cost_per_1k": 0.00300,
                "context_window_k": 200,
                "vision_capable": True
            }
        ]
    },
    "tier_3_heavy": {
        "tier": "HIGH",
        "routing_chain": [
            {
                "provider": "groq",
                "model": "llama-3.3-70b-versatile",
                "cost_per_1k": 0.00059,
                "context_window_k": 128,
                "vision_capable": False
            },
            {
                "provider": "gemini",
                "model": "gemini-2.5-flash",
                "cost_per_1k": 0.00015,
                "context_window_k": 1000,
                "vision_capable": True
            },
            {
                "provider": "openrouter",
                "model": "anthropic/claude-sonnet-4",
                "cost_per_1k": 0.00300,
                "context_window_k": 200,
                "vision_capable": True
            }
        ]
    },
    "tier_4_deep_reasoning": {
        "tier": "DEEP_REASONING",
        "routing_chain": [
            {
                "provider": "gemini",
                "model": "gemini-2.5-pro",
                "cost_per_1k": 0.00125,
                "context_window_k": 1000,
                "vision_capable": True
            },
            {
                "provider": "openrouter",
                "model": "anthropic/claude-sonnet-4",
                "cost_per_1k": 0.00300,
                "context_window_k": 200,
                "vision_capable": True
            },
            {
                "provider": "groq",
                "model": "llama-3.3-70b-versatile",
                "cost_per_1k": 0.00059,
                "context_window_k": 128,
                "vision_capable": False
            }
        ]
    },
    "vision_core": {
        "tier": "STANDARD",
        "routing_chain": [
            {
                "provider": "gemini",
                "model": "gemini-2.0-flash",
                "cost_per_1k": 0.00010,
                "context_window_k": 1000,
                "vision_capable": True
            },
            {
                "provider": "openrouter",
                "model": "anthropic/claude-3.5-sonnet",
                "cost_per_1k": 0.00300,
                "context_window_k": 200,
                "vision_capable": True
            }
        ]
    },
    "high_context_overflow": {
        "tier": "HIGH",
        "routing_chain": [
            {
                "provider": "gemini",
                "model": "gemini-2.5-pro",
                "cost_per_1k": 0.00125,
                "context_window_k": 1000,
                "vision_capable": True
            },
            {
                "provider": "gemini",
                "model": "gemini-2.0-flash",
                "cost_per_1k": 0.00010,
                "context_window_k": 1000,
                "vision_capable": True
            }
        ]
    }
}
