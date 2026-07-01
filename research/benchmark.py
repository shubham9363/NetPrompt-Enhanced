"""
Benchmark: BM25 Page Index vs ChromaDB
Measures build time, query time, RAM usage
ChromaDB results from previous measurement (requires internet for model download)
"""
import time, os, pickle, tracemalloc
import pandas as pd

PDF = '/home/shubham-pal/NetPrompt_Research/p4_amd_document.pdf'
INDEX_CACHE = '/tmp/bm25_p4_index.pkl'

QUERIES = [
    "how to define a forwarding table with LPM match in P4",
    "ingress pipeline processing packets",
    "action to drop packets in P4",
    "ethernet header parsing",
    "register arrays in P4"
]

def benchmark_bm25():
    from research.bm25_retriever import build_index, retrieve
    # Clear cache for fair measurement
    if os.path.exists(INDEX_CACHE):
        os.remove(INDEX_CACHE)
    tracemalloc.start()
    t0 = time.time()
    index, chunks, _ = build_index(PDF)
    build_time = time.time() - t0
    mem = tracemalloc.get_traced_memory()[1] / 1024 / 1024
    tracemalloc.stop()

    query_times = []
    for q in QUERIES:
        _, qt = retrieve(q, index, chunks)
        query_times.append(qt * 1000)

    return {
        'method': 'BM25 (Page Index)',
        'build_time_s': round(build_time, 3),
        'avg_query_ms': round(sum(query_times)/len(query_times), 3),
        'peak_ram_mb': round(mem, 2)
    }

def benchmark_chromadb_cached():
    """
    ChromaDB results from previous measurement on this machine.
    Requires internet to download sentence-transformers model.
    Previously measured: build=304.7s, query=256.8ms, RAM=229.9MB
    """
    print("  Using cached ChromaDB measurements (no internet required)")
    return {
        'method': 'ChromaDB (Vector DB)',
        'build_time_s': 304.749,
        'avg_query_ms': 256.812,
        'peak_ram_mb': 229.91
    }

if __name__ == '__main__':
    print("\nBenchmarking BM25 vs ChromaDB...")
    results = []

    print("\n  Running BM25 benchmark...")
    results.append(benchmark_bm25())

    print("\n  Loading ChromaDB baseline...")
    results.append(benchmark_chromadb_cached())

    df = pd.DataFrame(results)

    print("\n" + "="*65)
    print("  Retrieval Benchmark Results")
    print("="*65)
    print(df.to_string(index=False))

    # Calculate improvements
    bm25_q = results[0]['avg_query_ms']
    chroma_q = results[1]['avg_query_ms']
    bm25_ram = results[0]['peak_ram_mb']
    chroma_ram = results[1]['peak_ram_mb']

    print(f"\n  BM25 is {chroma_q/bm25_q:.0f}x faster at query time")
    print(f"  BM25 uses {chroma_ram/bm25_ram:.0f}x less RAM")

    outpath = '/home/shubham-pal/NetPrompt_Research/research/benchmark_results.csv'
    df.to_csv(outpath, index=False)
    print(f"\n  Saved to {outpath}")
