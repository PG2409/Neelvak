# Risk Register
The following operational and security risks were evaluated:

- **Zero-day Prompt Injection (Low)**: Attackers might construct complex semantic overrides that bypass PolicyEngine regex filters. *Mitigation*: The ToolManager execution sandbox prevents any harmful action even if an injection bypasses the compiler.
- **File System Write Latency (Medium)**: Local checkpoint serialization depends on I/O. *Mitigation*: Run data stores on SSD/NVMe volumes.
- **Coprocessor Provider Offline (Low)**: Simultaneous failure of Groq and OpenRouter could trigger fallback routing. *Mitigation*: Dynamic ModelRouter failback mapping assigns local/alternative providers instantly.
