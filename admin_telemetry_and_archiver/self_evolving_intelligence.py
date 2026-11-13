"""
Self-Evolving Intelligence & Fine-Tuning Pipeline (Project Aether-Human - Admin Omni-Observatory)
Analyzes conversational archives to extract trending slang, behavioral nuances,
and generates production-ready JSONL datasets for continuous LLM fine-tuning.
"""

from __future__ import annotations

import collections
import datetime
import json
import logging
import os
import re
from typing import Dict, List, Any

from admin_telemetry_and_archiver.passive_omni_archiver import omni_archiver

logger = logging.getLogger("Aether.Observatory.SelfEvolving")


class SelfEvolvingPipeline:
    """
    Synthesizes conversational data into fine-tuning datasets and linguistic evolutions.
    """

    def __init__(self, output_dir: str = "data/training_datasets"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def export_training_jsonl(
        self,
        recent_interactions: List[Dict[str, Any]],
        system_prompt: str = "أنت عمر، شاب سوري من دمشق عمره 24 سنة، تتحدث بالمصرية والشامية بذكاء وخفة دم وروح حية.",
    ) -> str:
        """
        Exports conversations into standardized OpenAI/Gemini fine-tuning JSONL format.
        """
        timestamp_str = datetime.datetime.now().strftime("%Y_%m_%d_%H%M%S")
        export_file = os.path.join(self.output_dir, f"dataset_{timestamp_str}.jsonl")

        exported_count = 0
        with open(export_file, "w", encoding="utf-8") as f:
            for item in recent_interactions:
                user_msg = item.get("user_message", "")
                assistant_reply = item.get("assistant_reply", "")

                if not user_msg or not assistant_reply:
                    continue

                sample = {
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_msg},
                        {"role": "assistant", "content": assistant_reply},
                    ]
                }
                f.write(json.dumps(sample, ensure_ascii=False) + "\n")
                exported_count += 1

        logger.info(f"✨ Successfully exported {exported_count} training samples to: {export_file}")
        return export_file


self_evolving_engine = SelfEvolvingPipeline()

