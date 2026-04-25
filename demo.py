#!/usr/bin/env python3
"""
Demo: Write and read a .loop file.
This shows the basic usage of the looplib library.

Usage:
    python3 demo.py
"""

from looplib import LoopWriter, LoopReader

# Example conversation data
conversations = [
    {
        "system": "Tu es un assistant utile.",
        "messages": [
            {"role": "user", "content": "Qu'est-ce que Polygone ?"},
            {"role": "assistant", "content": "Un réseau de confidentialité éphémère post-quantique."},
            {"role": "user", "content": "Comment ça marche ?"},
            {"role": "assistant", "content": "ML-KEM-1024 + Shamir 4-of-7 + AES-256-GCM."},
        ],
    },
    {
        "system": "You are a coding assistant.",
        "messages": [
            {"role": "user", "content": "Write a hello world in Rust"},
            {"role": "assistant", "content": "fn main() { println!(\"Hello, world!\"); }"},
        ],
    },
]

# Write to .loop file
output_file = "demo.loop"

print(f"Writing {len(conversations)} conversations to {output_file}...")
with LoopWriter(output_file, metadata={"name": "demo", "version": "1.0"}) as writer:
    for conv in conversations:
        writer.write(conv)

print("✓ Written successfully")

# Read back and verify
print(f"\nReading {output_file} back...")
with LoopReader(output_file) as reader:
    meta = reader.metadata()
    print(f"  Metadata: {meta}")
    count = 0
    for record in reader:
        count += 1
        print(f"  Record {count}: {len(record['messages'])} messages")

print(f"\n✓ Read {count} conversations from {output_file}")

# Clean up
import os
os.remove(output_file)
print("✓ Cleaned up demo.loop")