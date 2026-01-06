#!/usr/bin/env python3
"""Utility script to validate the Light-RAG integration."""

from __future__ import annotations

import asyncio
from pathlib import Path

from epip.config import LightRAGConfig
from epip.core.kg_builder import KGBuilder


async def verify_integration() -> None:
    print("=" * 60)
    print("Light-RAG Integration Verification")
    print("=" * 60)

    config = LightRAGConfig()
    print("\n[1] Loaded configuration:")
    print(f"    Working dir : {config.working_dir}")
    print(f"    Graph store : {config.graph_storage}")
    print(f"    LLM backend : {config.llm_backend}")
    print(f"    Embeddings  : {config.embedding_model} ({config.embedding_dim}d)")

    print("\n[2] Initializing KGBuilder...")
    builder = KGBuilder(config=config)
    print("    KGBuilder created.")

    temp_doc = Path("/tmp/lightrag_verify_doc.txt")
    temp_doc.write_text(
        "Light-RAG verification document describing Hong Kong public health statistics."
    )

    try:
        print("\n[3] Testing document insertion...")
        insert_result = await builder.insert_documents([temp_doc])
        print(f"    Inserted files : {insert_result.file_count}")
        print(f"    Entities count : {insert_result.entity_count}")
        print(f"    Relations count: {insert_result.relation_count}")
        if insert_result.errors:
            print("    Errors:")
            for err in insert_result.errors:
                print(f"        - {err}")

        print("\n[4] Testing query pipeline...")
        response = await builder.query("What does the verification document discuss?")
        print(f"    Response snippet: {response[:120]}{'...' if len(response) > 120 else ''}")

        print("\n[5] Fetching KG statistics...")
        stats = await builder.get_statistics()
        print(f"    Total entities : {stats.total_entities}")
        print(f"    Total relations: {stats.total_relations}")
    finally:
        if temp_doc.exists():
            temp_doc.unlink()

    print("\nVerification completed.")


if __name__ == "__main__":
    asyncio.run(verify_integration())
