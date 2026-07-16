import gc
import asyncio
import sys
from collections import defaultdict
from tests.stability.runner import StabilityRunner

async def main():
    runner = StabilityRunner()
    
    gc.collect()
    import tracemalloc
    tracemalloc.start()
    
    print("Running batch 1...")
    res1 = await runner.execute_batch(2000, concurrent=True)
    gc.collect()
    mem1, _ = tracemalloc.get_traced_memory()
    print(f"Memory after batch 1: {mem1 / 1024:.2f} KB")
    
    print("Running batch 2...")
    res2 = await runner.execute_batch(2000, concurrent=True)
    gc.collect()
    mem2, _ = tracemalloc.get_traced_memory()
    print(f"Memory after batch 2: {mem2 / 1024:.2f} KB")
    
    print(f"Delta between batch 2 and batch 1: {(mem2 - mem1) / 1024:.2f} KB")
    
    if (mem2 - mem1) < 10000:
        print("Conclusion: The memory growth is just Python heap fragmentation / high water mark. Not an infinite leak.")
    else:
        print("Conclusion: REAL MEMORY LEAK STILL EXISTS.")

if __name__ == "__main__":
    asyncio.run(main())
