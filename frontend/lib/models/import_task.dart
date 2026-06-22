import 'import_result.dart';

enum ImportStage {
  queued,
  parsing,
  storing,
  memory,
  vectors,
  completed,
  failed
}

class ImportTask {
  const ImportTask({
    required this.id,
    required this.stage,
    required this.progress,
    this.message = '',
    this.result,
    this.canRetry = false,
  });

  final String id;
  final ImportStage stage;
  final double progress;
  final String message;
  final ImportResult? result;
  final bool canRetry;

  bool get isFinished =>
      stage == ImportStage.completed || stage == ImportStage.failed;

  factory ImportTask.fromJson(Map<String, dynamic> json) {
    final rawStage =
        (json['stage'] ?? json['status'] ?? 'queued').toString().toLowerCase();
    final stage = switch (rawStage) {
      'parsing' || 'parse' => ImportStage.parsing,
      'storing' || 'database' || 'persisting' => ImportStage.storing,
      'memory' || 'extracting_memory' => ImportStage.memory,
      'vectors' || 'embedding' || 'embeddings' => ImportStage.vectors,
      'completed' || 'complete' || 'success' => ImportStage.completed,
      'failed' || 'error' => ImportStage.failed,
      _ => ImportStage.queued,
    };
    final rawProgress = (json['progress'] as num?)?.toDouble() ?? 0;
    final resultJson = json['result'];
    return ImportTask(
      id: (json['task_id'] ?? json['id'] ?? json['import_id'] ?? '').toString(),
      stage: stage,
      progress: (rawProgress > 1 ? rawProgress / 100 : rawProgress)
          .clamp(0.0, 1.0)
          .toDouble(),
      message: (json['message'] ?? json['detail'] ?? '').toString(),
      result: resultJson is Map<String, dynamic>
          ? ImportResult.fromJson(resultJson)
          : stage == ImportStage.completed
              ? ImportResult(
                  status: 'success',
                  contacts: (json['contacts'] as num?)?.toInt() ??
                      (json['person_id'] == null ? 0 : 1),
                  messages: (json['messages'] as num?)?.toInt() ??
                      (json['imported_count'] as num?)?.toInt() ??
                      0,
                  importId:
                      (json['task_id'] ?? json['import_id'] ?? '').toString(),
                )
              : null,
      canRetry: json['can_retry'] as bool? ?? stage == ImportStage.failed,
    );
  }
}
