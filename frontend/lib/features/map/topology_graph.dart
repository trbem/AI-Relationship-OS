import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../models/relationship_graph.dart';

class TopologyGraph extends StatefulWidget {
  const TopologyGraph({
    super.key,
    required this.graph,
    required this.selectedNodeId,
    required this.onNodeSelected,
    required this.showLabels,
  });

  final RelationshipGraph graph;
  final String? selectedNodeId;
  final ValueChanged<GraphNode> onNodeSelected;
  final bool showLabels;

  @override
  State<TopologyGraph> createState() => _TopologyGraphState();
}

class _TopologyGraphState extends State<TopologyGraph> {
  static const _canvasSize = Size(1600, 1050);
  final _transformationController = TransformationController();
  final Map<String, Offset> _positions = {};
  final Set<String> _locked = {};

  @override
  void initState() {
    super.initState();
    _layout();
  }

  @override
  void didUpdateWidget(covariant TopologyGraph oldWidget) {
    super.didUpdateWidget(oldWidget);
    final oldIds = oldWidget.graph.nodes.map((item) => item.id).join('|');
    final newIds = widget.graph.nodes.map((item) => item.id).join('|');
    if (oldIds != newIds) _layout();
  }

  void _layout() {
    final nodes = widget.graph.nodes;
    final center = Offset(_canvasSize.width / 2, _canvasSize.height / 2);
    final next = <String, Offset>{};
    for (final node in nodes) {
      if (_positions.containsKey(node.id) && _locked.contains(node.id)) {
        next[node.id] = _positions[node.id]!;
        continue;
      }
      final hash = _stableHash(node.id);
      final angle = (hash % 6283) / 1000;
      final radius = node.type == 'center'
          ? 0.0
          : node.type == 'group'
              ? 220.0
              : node.type == 'event'
                  ? 480.0
                  : 360.0;
      next[node.id] =
          center + Offset(math.cos(angle) * radius, math.sin(angle) * radius);
    }
    for (var iteration = 0; iteration < 160; iteration++) {
      final forces = {for (final node in nodes) node.id: Offset.zero};
      for (var i = 0; i < nodes.length; i++) {
        for (var j = i + 1; j < nodes.length; j++) {
          final left = nodes[i];
          final right = nodes[j];
          final delta = next[right.id]! - next[left.id]!;
          final distance = math.max(24.0, delta.distance);
          final direction = delta / distance;
          final repulsion = math.min(16.0, 8500 / (distance * distance));
          forces[left.id] = forces[left.id]! - direction * repulsion;
          forces[right.id] = forces[right.id]! + direction * repulsion;
        }
      }
      for (final link in widget.graph.links) {
        final source = next[link.source];
        final target = next[link.target];
        if (source == null || target == null) continue;
        final delta = target - source;
        final distance = math.max(1.0, delta.distance);
        final desired = link.relationType == 'relationship' ? 210.0 : 125.0;
        final spring = (distance - desired) * 0.006;
        final direction = delta / distance;
        forces[link.source] = forces[link.source]! + direction * spring;
        forces[link.target] = forces[link.target]! - direction * spring;
      }
      for (final node in nodes) {
        if (_locked.contains(node.id) || node.type == 'center') continue;
        final towardCenter = (center - next[node.id]!) * 0.002;
        final position = next[node.id]! + forces[node.id]! + towardCenter;
        next[node.id] = Offset(
          position.dx.clamp(70, _canvasSize.width - 70),
          position.dy.clamp(70, _canvasSize.height - 70),
        );
      }
      final centerNode = nodes.where((item) => item.type == 'center');
      if (centerNode.isNotEmpty) next[centerNode.first.id] = center;
    }
    _positions
      ..clear()
      ..addAll(next);
  }

  void _reset() {
    _locked.clear();
    _positions.clear();
    _transformationController.value = Matrix4.identity();
    setState(_layout);
  }

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFF0B1021), Color(0xFF15112C), Color(0xFF07111F)],
        ),
      ),
      child: Stack(
        children: [
          Positioned.fill(
            child: CustomPaint(
              painter: _GridPainter(),
            ),
          ),
          Positioned.fill(
            child: InteractiveViewer(
              transformationController: _transformationController,
              minScale: 0.25,
              maxScale: 3.5,
              boundaryMargin: const EdgeInsets.all(500),
              constrained: false,
              child: SizedBox(
                width: _canvasSize.width,
                height: _canvasSize.height,
                child: Stack(
                  clipBehavior: Clip.none,
                  children: [
                    Positioned.fill(
                      child: CustomPaint(
                        painter: _EdgePainter(
                          graph: widget.graph,
                          positions: _positions,
                          selectedNodeId: widget.selectedNodeId,
                          showLabels: widget.showLabels,
                          colorForNode: _color,
                        ),
                      ),
                    ),
                    ...widget.graph.nodes.map(_node),
                  ],
                ),
              ),
            ),
          ),
          Positioned(
            right: 14,
            bottom: 14,
            child: FloatingActionButton.small(
              heroTag: 'reset-topology',
              onPressed: _reset,
              tooltip: '重置视角与布局',
              child: const Icon(Icons.center_focus_strong),
            ),
          ),
        ],
      ),
    );
  }

  Widget _node(GraphNode node) {
    final position = _positions[node.id] ?? Offset.zero;
    final radius = _radius(node);
    final selected = widget.selectedNodeId == node.id;
    return Positioned(
      left: position.dx - radius,
      top: position.dy - radius,
      child: GestureDetector(
        onTap: () => widget.onNodeSelected(node),
        onPanUpdate: (details) {
          final scale = _transformationController.value
              .getMaxScaleOnAxis()
              .clamp(0.25, 3.5);
          setState(() {
            _locked.add(node.id);
            final updated = position + details.delta / scale;
            _positions[node.id] = Offset(
              updated.dx.clamp(radius, _canvasSize.width - radius),
              updated.dy.clamp(radius, _canvasSize.height - radius),
            );
          });
        },
        child: SizedBox(
          width: radius * 2,
          height: radius * 2 + (widget.showLabels ? 30 : 0),
          child: Column(
            children: [
              AnimatedContainer(
                duration: const Duration(milliseconds: 180),
                width: radius * 2,
                height: radius * 2,
                decoration: BoxDecoration(
                  gradient: RadialGradient(
                    colors: [
                      Color.lerp(_color(node), Colors.white, 0.22)!,
                      _color(node),
                    ],
                  ),
                  shape: node.type == 'event'
                      ? BoxShape.rectangle
                      : BoxShape.circle,
                  borderRadius:
                      node.type == 'event' ? BorderRadius.circular(10) : null,
                  border: Border.all(
                    color: selected ? const Color(0xFFFFD166) : Colors.white70,
                    width: selected ? 4 : 2.5,
                  ),
                  boxShadow: [
                    BoxShadow(
                      blurRadius: selected ? 34 : 22,
                      spreadRadius: selected ? 8 : 3,
                      color: _color(node)
                          .withValues(alpha: selected ? 0.65 : 0.38),
                    ),
                    const BoxShadow(
                      blurRadius: 14,
                      color: Color(0x77000000),
                      offset: Offset(0, 5),
                    ),
                  ],
                ),
                child: Icon(
                  _icon(node),
                  color: Colors.white,
                  size: radius * 0.82,
                ),
              ),
              if (widget.showLabels)
                Container(
                  constraints: const BoxConstraints(maxWidth: 120),
                  padding:
                      const EdgeInsets.symmetric(horizontal: 5, vertical: 2),
                  decoration: BoxDecoration(
                    color: const Color(0xCC111827),
                    borderRadius: BorderRadius.circular(999),
                    border: Border.all(color: Colors.white24),
                  ),
                  child: Text(
                    node.name,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    textAlign: TextAlign.center,
                    style: const TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                      color: Color(0xFFE5E7EB),
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }

  double _radius(GraphNode node) {
    if (node.type == 'center') return 34;
    if (node.type == 'group') return 25;
    if (node.type == 'event') return 20;
    return 19 + node.relationshipScore.clamp(0, 100) * 0.09;
  }

  Color _color(GraphNode node) {
    if (node.type == 'center') return const Color(0xFF1F2937);
    if (node.type == 'group') return const Color(0xFF7B2D8E);
    if (node.type == 'persona') {
      const palette = [
        Color(0xFFB42318),
        Color(0xFF175CD3),
        Color(0xFF067647),
        Color(0xFF7A5AF8),
        Color(0xFFB54708),
        Color(0xFF344054),
      ];
      return palette[_stableHash(node.group) % palette.length];
    }
    if (node.type == 'event') {
      if (node.emotion == 'stress') return const Color(0xFFC5283D);
      if (node.emotion == 'positive') return const Color(0xFF1A936F);
      return const Color(0xFFE9724C);
    }
    if (node.emotion == 'stress') return const Color(0xFFEF5350);
    if (node.emotion == 'positive') return const Color(0xFF26A69A);
    return const Color(0xFF3B82F6);
  }

  IconData _icon(GraphNode node) {
    if (node.type == 'center') return Icons.person;
    if (node.type == 'group') return Icons.folder_open;
    if (node.type == 'event') return Icons.bolt;
    return Icons.person_outline;
  }

  static int _stableHash(String value) {
    var hash = 2166136261;
    for (final unit in value.codeUnits) {
      hash ^= unit;
      hash = (hash * 16777619) & 0x7fffffff;
    }
    return hash;
  }
}

class _EdgePainter extends CustomPainter {
  _EdgePainter({
    required this.graph,
    required this.positions,
    required this.selectedNodeId,
    required this.showLabels,
    required this.colorForNode,
  });

  final RelationshipGraph graph;
  final Map<String, Offset> positions;
  final String? selectedNodeId;
  final bool showLabels;
  final Color Function(GraphNode node) colorForNode;

  @override
  void paint(Canvas canvas, Size size) {
    final nodesById = {for (final node in graph.nodes) node.id: node};
    for (final link in graph.links) {
      final source = positions[link.source];
      final target = positions[link.target];
      if (source == null || target == null) continue;
      final sourceNode = nodesById[link.source];
      final targetNode = nodesById[link.target];
      final sourceColor =
          sourceNode == null ? _edgeColor(link) : colorForNode(sourceNode);
      final targetColor =
          targetNode == null ? _edgeColor(link) : colorForNode(targetNode);
      final highlighted =
          selectedNodeId == link.source || selectedNodeId == link.target;
      final path = Path()
        ..moveTo(source.dx, source.dy)
        ..quadraticBezierTo(
          (source.dx + target.dx) / 2,
          (source.dy + target.dy) / 2 - 18,
          target.dx,
          target.dy,
        );
      final glow = Paint()
        ..color = (highlighted ? const Color(0xFFFFD166) : _edgeColor(link))
            .withValues(alpha: highlighted ? 0.34 : 0.14)
        ..strokeWidth =
            (highlighted ? link.width + 8 : link.width + 5).clamp(3, 12)
        ..style = PaintingStyle.stroke
        ..strokeCap = StrokeCap.round
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 7);
      canvas.drawPath(path, glow);
      final paint = Paint()
        ..shader = LinearGradient(
          colors: [
            sourceColor.withValues(alpha: highlighted ? 0.95 : 0.55),
            targetColor.withValues(alpha: highlighted ? 0.95 : 0.55),
          ],
        ).createShader(Rect.fromPoints(source, target))
        ..strokeWidth = highlighted ? link.width + 1.5 : link.width.clamp(1, 5)
        ..style = PaintingStyle.stroke
        ..strokeCap = StrokeCap.round;
      canvas.drawPath(path, paint);
      _arrow(canvas, source, target,
          highlighted ? const Color(0xFFFFD166) : targetColor);
      if (showLabels && link.relationType != 'relationship') {
        final midpoint = Offset(
          (source.dx + target.dx) / 2,
          (source.dy + target.dy) / 2,
        );
        final text = TextPainter(
          text: TextSpan(
            text: link.relationType.replaceAll('_', ' '),
            style: const TextStyle(
              fontSize: 10,
              color: Color(0xFFE5E7EB),
              backgroundColor: Color(0xCC111827),
            ),
          ),
          textDirection: TextDirection.ltr,
        )..layout();
        text.paint(canvas, midpoint - Offset(text.width / 2, text.height / 2));
      }
    }
  }

  void _arrow(Canvas canvas, Offset source, Offset target, Color color) {
    final delta = target - source;
    if (delta.distance < 2) return;
    final unit = delta / delta.distance;
    final tip = target - unit * 22;
    final normal = Offset(-unit.dy, unit.dx);
    final path = Path()
      ..moveTo(tip.dx, tip.dy)
      ..lineTo(
        tip.dx - unit.dx * 9 + normal.dx * 4,
        tip.dy - unit.dy * 9 + normal.dy * 4,
      )
      ..lineTo(
        tip.dx - unit.dx * 9 - normal.dx * 4,
        tip.dy - unit.dy * 9 - normal.dy * 4,
      )
      ..close();
    canvas.drawPath(
      path,
      Paint()
        ..color = color.withValues(alpha: 0.85)
        ..style = PaintingStyle.fill,
    );
  }

  Color _edgeColor(GraphLink link) {
    if (link.emotion == 'stress') return const Color(0xFFEF5350);
    if (link.emotion == 'positive') return const Color(0xFF26A69A);
    return const Color(0xFF9CA3AF);
  }

  @override
  bool shouldRepaint(covariant _EdgePainter oldDelegate) => true;
}

class _GridPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final rect = Offset.zero & size;
    canvas.drawRect(
      rect,
      Paint()
        ..shader = const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFF070B1A), Color(0xFF171032), Color(0xFF061522)],
        ).createShader(rect),
    );
    final nebulaPaint = Paint()
      ..color = const Color(0x332E90FA)
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 70);
    canvas.drawCircle(
        Offset(size.width * 0.2, size.height * 0.25), 180, nebulaPaint);
    canvas.drawCircle(
      Offset(size.width * 0.78, size.height * 0.62),
      230,
      Paint()
        ..color = const Color(0x334C1D95)
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 80),
    );
    final paint = Paint()..color = const Color(0x55DDE7FF);
    for (double x = 12; x < size.width; x += 24) {
      for (double y = 12; y < size.height; y += 24) {
        final sparkle =
            ((_TopologyGraphState._stableHash('$x:$y') % 100) / 100);
        canvas.drawCircle(Offset(x, y), 0.6 + sparkle * 0.9, paint);
      }
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
