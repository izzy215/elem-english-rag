#!/bin/bash
if ! curl -s -m 3 http://localhost:11434/api/tags > /dev/null 2>&1; then
    CUDA_VISIBLE_DEVICES=1 \
    OLLAMA_MODELS=/home/research1/workspace/team2/elem-english-rag/ollama-models \
    OLLAMA_HOST=0.0.0.0:11434 \
    nohup /home/research1/ollama/bin/ollama serve > /home/research1/workspace/team2/elem-english-rag/ollama.log 2>&1 &
fi
