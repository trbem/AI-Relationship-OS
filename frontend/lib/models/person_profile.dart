class PersonProfile {
  const PersonProfile({
    required this.id,
    required this.name,
    required this.traits,
    required this.communication,
    required this.confidence,
  });

  final String id;
  final String name;
  final List<String> traits;
  final List<String> communication;
  final double confidence;
}
