# Real-World PASH Compression Benchmarks

Tested via native Windows integration with Odysseus MCP client.

## Scenario: GitHub Repo Analysis
- **Tool:** `demo_github_repo`
- **Raw Response Size:** ~30,685 bytes (~7,671 tokens)
- **PASH Response Size:** ~7,542 bytes (~1,885 tokens)
- **Savings:** **75.4%**
- **Latency:** 91.55 ms

## Scenario: Filesystem Search
- **Tool:** `demo_filesystem_search`
- **Raw Response Size:** ~24,973 bytes (~6,243 tokens)
- **PASH Response Size:** ~2,559 bytes (~639 tokens)
- **Savings:** **89.8%**
- **Latency:** 5.28 ms

## Scenario: Web Scraping
- **Tool:** `demo_web_scraping`
- **Raw Response Size:** ~68,883 bytes (~17,220 tokens)
- **PASH Response Size:** ~1,787 bytes (~446 tokens)
- **Savings:** **97.4%**
- **Latency:** 5.01 ms

## Summary
- **Average Token Savings:** **87.5%**
- **Setup Time:** < 5 minutes (Native PowerShell, no Docker)
- **Latency Overhead:** < 92 ms
