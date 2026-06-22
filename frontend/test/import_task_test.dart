import 'package:flutter_test/flutter_test.dart';
import 'package:relationship_os/models/import_task.dart';

void main() {
  test('normalizes percentage progress and embedding stage', () {
    final task = ImportTask.fromJson({
      'task_id': 'task-1',
      'stage': 'embedding',
      'progress': 75,
    });

    expect(task.id, 'task-1');
    expect(task.stage, ImportStage.vectors);
    expect(task.progress, 0.75);
    expect(task.isFinished, isFalse);
  });

  test('supports legacy synchronous import response', () {
    final task = ImportTask.fromJson({
      'status': 'success',
      'import_id': 'legacy-1',
      'contacts': 1,
      'messages': 119,
    });

    expect(task.stage, ImportStage.completed);
    expect(task.isFinished, isTrue);
    expect(task.result?.contacts, 1);
    expect(task.result?.messages, 119);
  });

  test('failed task is retryable by default', () {
    final task = ImportTask.fromJson({
      'task_id': 'task-2',
      'status': 'failed',
      'message': 'network error',
    });

    expect(task.stage, ImportStage.failed);
    expect(task.canRetry, isTrue);
  });
}
