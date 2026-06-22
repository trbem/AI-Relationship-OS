class SimulationSeed {
  const SimulationSeed({
    required this.personId,
    required this.personName,
    this.question,
  });

  final String personId;
  final String personName;
  final String? question;
}
