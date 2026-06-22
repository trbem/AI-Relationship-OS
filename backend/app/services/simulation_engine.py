from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.models import Person
from app.prompts.simulation_prompt import SIMULATION_SYSTEM_PROMPT
from app.services.ai_client import AIClient, AIClientError
from app.services.evidence_service import EvidenceService
from app.services.persona_service import PersonaService


class SimulationEngine:
    def run(
        self,
        db: Session,
        person: Person,
        question: str,
        *,
        conversation_context: str = "",
    ) -> dict:
        evidence_service = EvidenceService()
        evidence = evidence_service.collect(db, person, question)
        confidence = evidence_service.confidence(evidence, len(person.messages))
        persona = PersonaService().generate_persona(
            person.name, [message.content for message in person.messages]
        )
        prompt = self._prompt(
            person.name,
            question,
            persona,
            evidence,
            conversation_context,
        )
        try:
            raw = AIClient().chat_json(
                system_prompt=SIMULATION_SYSTEM_PROMPT,
                user_prompt=prompt,
                temperature=0.25,
            )
        except (AIClientError, TypeError, ValueError):
            raw = self._fallback(evidence)
        predictions = self._predictions(raw, confidence, evidence)
        reasons = raw.get("reason", []) if isinstance(raw, dict) else []
        if not isinstance(reasons, list) or not reasons:
            reasons = [
                item["excerpt"] for item in evidence[:3]
            ] or ["There is not enough relevant history for a strong inference."]
        return {
            "prediction": predictions,
            "reason": [str(item) for item in reasons[:6]],
            "evidence": evidence,
            "confidence_summary": confidence,
            "data_coverage": {
                "message_count": len(person.messages),
                "memory_count": len(person.memories),
                "evidence_count": len(evidence),
            },
            "disclaimer": (
                "This is a probabilistic summary of historical patterns, not a "
                "prediction of a real person's certain behavior."
            ),
        }

    def _predictions(
        self,
        raw: dict,
        confidence: dict,
        evidence: list[dict],
    ) -> list[dict]:
        values = raw.get("predictions", []) if isinstance(raw, dict) else []
        if not isinstance(values, list) or not values:
            values = self._fallback(evidence)["predictions"]
        parsed: list[dict] = []
        for item in values[:5]:
            if not isinstance(item, dict):
                continue
            probability = min(1.0, max(0.0, float(item.get("probability", 0))))
            parsed.append(
                {
                    "text": str(item.get("text", "Possible response")),
                    "probability": probability,
                    "confidence": confidence["score"],
                    "evidence_strength": confidence["evidence_strength"],
                    "evidence_ids": [
                        evidence_item["id"] for evidence_item in evidence[:5]
                    ],
                    "supporting_factors": self._strings(
                        item.get("supporting_factors")
                    )
                    or [item["excerpt"] for item in evidence[:2]],
                    "counter_factors": self._strings(item.get("counter_factors"))
                    or ["Context and current emotion may differ from historical patterns."],
                }
            )
        total = sum(item["probability"] for item in parsed)
        if total <= 0:
            total = 1
        for item in parsed:
            item["probability"] = round(item["probability"] / total, 4)
        return parsed

    @staticmethod
    def _prompt(
        person_name: str,
        question: str,
        persona: dict,
        evidence: list[dict],
        conversation_context: str,
    ) -> str:
        evidence_json = json.dumps(evidence[:8], ensure_ascii=False)
        persona_json = json.dumps(persona, ensure_ascii=False)
        return f"""
Target person: {person_name}
Question or scenario: {question}
Prior conversation context: {conversation_context or "none"}
Persona summary: {persona_json}
Historical evidence: {evidence_json}

Return strict JSON:
{{
  "predictions": [
    {{
      "text": "possible response",
      "probability": 0.5,
      "supporting_factors": ["factor"],
      "counter_factors": ["factor"]
    }}
  ],
  "reason": ["short evidence-grounded reason"]
}}
Provide 2-4 alternatives. Probabilities must be non-negative. Do not claim certainty.
""".strip()

    @staticmethod
    def _fallback(evidence: list[dict]) -> dict:
        support = evidence[0]["excerpt"] if evidence else "Limited relevant history"
        return {
            "predictions": [
                {
                    "text": "Ask for more context before responding",
                    "probability": 0.45,
                    "supporting_factors": [support],
                },
                {
                    "text": "Accept the request with conditions",
                    "probability": 0.32,
                    "supporting_factors": [support],
                },
                {
                    "text": "Express concern and continue discussing",
                    "probability": 0.23,
                    "supporting_factors": [support],
                },
            ],
            "reason": [support],
        }

    @staticmethod
    def _strings(value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item) for item in value if str(item).strip()]
