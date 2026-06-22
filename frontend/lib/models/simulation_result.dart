class SimulationEvidence {
  const SimulationEvidence({
    required this.id,
    required this.type,
    required this.sourceId,
    required this.personId,
    required this.excerpt,
    required this.relevance,
    this.senderName,
    this.occurredAt,
  });

  final String id;
  final String type;
  final String sourceId;
  final String personId;
  final String excerpt;
  final double relevance;
  final String? senderName;
  final String? occurredAt;

  factory SimulationEvidence.fromJson(Map<String, dynamic> json) {
    return SimulationEvidence(
      id: json['id']?.toString() ?? '',
      type: json['type']?.toString() ?? '',
      sourceId: json['source_id']?.toString() ?? '',
      personId: json['person_id']?.toString() ?? '',
      excerpt: json['excerpt']?.toString() ?? '',
      relevance: (json['relevance'] as num?)?.toDouble() ?? 0,
      senderName: json['sender_name']?.toString(),
      occurredAt: json['occurred_at']?.toString(),
    );
  }
}

class SimulationPrediction {
  const SimulationPrediction({
    required this.text,
    required this.probability,
    required this.confidence,
    required this.evidenceStrength,
    required this.evidenceIds,
    required this.supportingFactors,
    required this.counterFactors,
  });

  final String text;
  final double probability;
  final double confidence;
  final String evidenceStrength;
  final List<String> evidenceIds;
  final List<String> supportingFactors;
  final List<String> counterFactors;

  factory SimulationPrediction.fromJson(Map<String, dynamic> json) {
    List<String> strings(String key) => (json[key] as List<dynamic>? ?? [])
        .map((item) => item.toString())
        .toList();
    return SimulationPrediction(
      text: json['text'] as String? ?? '',
      probability: (json['probability'] as num?)?.toDouble() ?? 0,
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0,
      evidenceStrength: json['evidence_strength']?.toString() ?? 'weak',
      evidenceIds: strings('evidence_ids'),
      supportingFactors: strings('supporting_factors'),
      counterFactors: strings('counter_factors'),
    );
  }
}

class SimulationResult {
  const SimulationResult({
    required this.prediction,
    required this.reason,
    required this.evidence,
    required this.confidenceSummary,
    required this.disclaimer,
  });

  final List<SimulationPrediction> prediction;
  final List<String> reason;
  final List<SimulationEvidence> evidence;
  final Map<String, dynamic> confidenceSummary;
  final String disclaimer;

  factory SimulationResult.fromJson(Map<String, dynamic> json) {
    return SimulationResult(
      prediction: (json['prediction'] as List<dynamic>? ?? [])
          .map((item) =>
              SimulationPrediction.fromJson(item as Map<String, dynamic>))
          .toList(),
      reason: (json['reason'] as List<dynamic>? ?? [])
          .map((item) => item.toString())
          .toList(),
      evidence: (json['evidence'] as List<dynamic>? ?? [])
          .map((item) =>
              SimulationEvidence.fromJson(item as Map<String, dynamic>))
          .toList(),
      confidenceSummary:
          json['confidence_summary'] as Map<String, dynamic>? ?? const {},
      disclaimer: json['disclaimer'] as String? ?? '',
    );
  }
}
