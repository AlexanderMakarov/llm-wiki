---
title: "Session: training-data-pipeline — 2026-01-20"
type: source
tags: [claude-code, session-transcript, demo, demo-ml-pipeline, gpt, data-pipeline, text-classification, tokenization, s3-parquet, huggingface-datasets]
date: 2026-01-20
source_file: raw/sessions/demo-ml-pipeline/2026-01-20-training-data-pipeline.md
project: demo-ml-pipeline
model: gpt-5.4
last_updated: 2026-07-29
---
## Summary

The session produced a 4-stage data pipeline for preparing training data for text classification models. The pipeline reads Parquet files from S3 (using LocalStack for development), deduplicates records by text+label hash, tokenizes text using tiktoken's cl100k_base encoder with batching in 1024-token chunks, and writes stratified 80/20 train/validation shards via Hugging Face datasets. The modular design allows individual stages to run independently, and end-to-end processing of 10k rows completes in 3.2 seconds.

## Key Claims

- The pipeline uses `pyarrow.parquet.read_table` to load data from S3 directly
- Tokenization uses tiktoken's `cl100k_base` encoder with 1024-token batching for throughput
- Outputs are written using `datasets.Dataset.save_to_disk` in Hugging Face datasets format
- Stages are composable—any subset can be run independently (e.g., re-tokenize without re-loading)
- Configuration-driven execution via YAML with a top-level `pipeline.run()` dispatcher
- Stratified 80/20 split ensures balanced class distribution between train and validation sets
- Local test on 10k rows runs in 3.2 seconds end-to-end

## Key Quotes

> "The stages will be composable so we can run any subset (e.g. just re-tokenize without re-loading)." — articulates the design principle of stage reusability and independence

> "Local test on 10k rows runs in 3.2s end to end." — demonstrates performance validation during development

## Connections

- [[demo-ml-pipeline]] — the project housing this pipeline
- [[PyArrow]] — used for reading Parquet files from S3
- [[tiktoken]] — tokenization library with cl100k_base encoder
- [[Hugging Face Datasets]] — output format and dataset writing API