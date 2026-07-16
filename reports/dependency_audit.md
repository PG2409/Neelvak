# Dependency Audit

## Internal Verification
- no circular imports
- no duplicate implementations
- no duplicate contracts
- no orphan modules

## External Warnings
- StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated.
- RuntimeWarning: coroutine was never awaited (internal gc.collect tracking during stress tests).
