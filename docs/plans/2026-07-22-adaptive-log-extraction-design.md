# Adaptive Log Extraction Design

## Goal

Make error-log extraction adaptive and observable. Logs with 500 lines or fewer are sent to the extraction model as one unit. Larger logs are split into bounded, overlapping chunks, extracted concurrently, and merged before knowledge-base retrieval and final diagnosis.

## Data Flow

1. Download and validate the configured log file.
2. Resolve the machine-specific extraction prompt.
3. Count lines. Use one chunk for logs with at most 500 lines; otherwise split on line boundaries using the extraction model context budget.
4. Extract each chunk with its global start/end line metadata and aggregate successful results.
5. Preserve repeated errors with an occurrence count and global line positions. If every chunk fails, use the regex context extractor.
6. Merge all extracted log files for an SN into one text artifact.
7. Use the merged artifact in both the RAGFlow query and the final diagnosis prompt.
8. Return the merged artifact in the diagnosis response and cache so the frontend can download it as UTF-8 text.

## Progress

The SN diagnosis endpoint streams progress events for device lookup, SIMS lookup, log download, log splitting, chunk extraction, aggregation, case matching, knowledge retrieval, and final LLM diagnosis. The final event contains the existing diagnosis response.

## Failure Handling

Partial chunk failures keep successful results and report extraction coverage. All-chunk failure triggers regex extraction. Empty downloads and missing log configuration remain hard failures. The download path is validated before URL construction.

## Verification

Backend tests cover the 500-line boundary, large-log splitting, partial and total AI failures, global line aggregation, and merged response fields. Frontend type-checking and production build verify stream parsing and download controls.
