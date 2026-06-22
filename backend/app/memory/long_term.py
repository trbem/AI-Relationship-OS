class LongTermMemoryPipeline:
    def summarize(self, memories: list[dict]) -> dict:
        return {
            "count": len(memories),
            "high_importance": [item for item in memories if item.get("importance", 0) >= 0.8],
        }
