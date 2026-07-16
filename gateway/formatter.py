"""Response Formatter & Watchdog Sanitization.

Cleans internal telemetry logs and process tokens prior to client deliveries.
"""

import re
import logging

logger = logging.getLogger("neelvak_kernel")

class ResponseFormatter:
    """Regex scrubbing engine removing kernel metadata tags and internal addresses."""

    # Matches PCB_XXX, TCB_XXX, [Kernel], [System] and surrounding brackets
    METADATA_REGEX = re.compile(
        r"(PCB_[A-Z0-9]{1,12}|TCB_[A-Z0-9]{1,12}|\[Kernel\]|\[System\]|\[Loop\]|\[Watchdog\]|\[Surveillance\]|\[Fatal\])",
        re.IGNORECASE
    )

    def clean_output(self, raw_output: str) -> str:
        """Strips internal system identifiers, JSON envelopes, and brackets.

        Args:
            raw_output: Telemetry polluted text string.

        Returns:
            Scrubbed user-space clean output string.
        """
        logger.debug("ResponseFormatter: Scrubbing response metadata tags.")

        # Unwrap JSON envelope from CompetitiveRuntime: {"status":"success","result":"..."}
        stripped = raw_output.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                import json
                parsed = json.loads(stripped)
                if isinstance(parsed, dict) and "result" in parsed:
                    stripped = str(parsed["result"])
                    logger.debug("ResponseFormatter: Unwrapped JSON result envelope.")
            except Exception:
                pass  # Not valid JSON — proceed with raw string

        # Strip identifiers
        clean_text = self.METADATA_REGEX.sub("", stripped)

        # Clean hidden json tags like <json>...</json>
        clean_text = re.sub(r"<json>.*?</json>", "", clean_text, flags=re.IGNORECASE | re.DOTALL)

        # Clean double spaces or broken prefixes
        clean_text = re.sub(r"\s+", " ", clean_text)

        # Clean empty braces or brackets remaining
        clean_text = clean_text.replace("[]", "").replace("()", "")

        return clean_text.strip()
        
    def format_runtime_result(self, result) -> dict:
        """Packages a RuntimeResult into clean metadata fields.
        
        Args:
            result: RuntimeResult instance.
            
        Returns:
            Dict containing clean output and metadata analytics.
        """
        raw_output = getattr(result, "output", str(result))
        clean_out = self.clean_output(raw_output)
        
        metadata = {
            "estimated_cost_usd": getattr(result, "estimated_cost_usd", 0.0),
            "latency_ms": getattr(result, "latency_ms", 0.0),
            "provider": getattr(result, "provider", "unknown"),
            "model": getattr(result, "model", "unknown")
        }
        
        return {
            "output": clean_out,
            "metadata": metadata
        }
