#!/bin/bash
# NetPrompt_Research — Complete Research Demo
# Improvements: BM25 retrieval + Multi-LLM Voting

GREEN='\033[0;32m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
header() { echo -e "\n${BOLD}${GREEN}=== $1 ===${NC}"; }

source /home/shubham-pal/netprompt-env/bin/activate
export PYTHONPATH=/home/shubham-pal/NetPrompt_Research:$PYTHONPATH

header "PHASE 1: Improvement 1 — BM25 Page Index (vs ChromaDB)"
python3 /home/shubham-pal/NetPrompt_Research/research/bm25_retriever.py

header "PHASE 2: Benchmark — BM25 vs ChromaDB"
python3 /home/shubham-pal/NetPrompt_Research/research/benchmark.py

header "PHASE 3: Improvement 2 — Multi-LLM Consensus Voting"
sudo mn -c 2>/dev/null; sudo pkill -9 -f simple_switch 2>/dev/null
sudo rm -f /tmp/bmv2-*.ipc; sleep 2
sudo env PATH=$PATH PYTHONPATH=$PYTHONPATH python3 \
    /home/shubham-pal/NetPrompt_Research/research/multi_llm_voter.py

header "PHASE 4: Results Summary"
echo "BM25 Benchmark:"
cat /home/shubham-pal/NetPrompt_Research/research/benchmark_results.csv
echo ""
echo "Voting Results:"
cat /home/shubham-pal/NetPrompt_Research/experimentations/voting_results.csv

sudo mn -c 2>/dev/null; sudo pkill -9 -f simple_switch 2>/dev/null
echo -e "\n${GREEN}${BOLD}Research complete!${NC}"
