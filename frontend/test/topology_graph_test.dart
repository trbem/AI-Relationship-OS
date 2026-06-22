import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:relationship_os/features/map/topology_graph.dart';
import 'package:relationship_os/models/relationship_graph.dart';

void main() {
  testWidgets('renders a 100 node and 200 edge topology', (tester) async {
    final nodes = List.generate(
      100,
      (index) => GraphNode(
        id: 'node-$index',
        name: 'Node $index',
        type: index == 0 ? 'center' : 'person',
        group: 'group-${index % 5}',
        weight: 50,
        emotion: 'neutral',
        intimacy: 0.5,
        interaction: index,
        trust: 0.5,
        recentActive: true,
        activeScore: 0.5,
        relationshipScore: 50,
        hint: null,
        scoreComponents: const {},
        changeReasons: const [],
      ),
    );
    final links = List.generate(
      200,
      (index) => GraphLink(
        source: 'node-${index % 100}',
        target: 'node-${(index * 7 + 1) % 100}',
        strength: 0.5,
        interaction: index,
        emotion: 'neutral',
        width: 1.5,
        relationType: 'relationship',
      ),
    );
    final graph = RelationshipGraph(
      nodes: nodes,
      links: links,
      insights: const GraphInsights(
        topChanges: [],
        activeCount: 100,
        strongestTie: 'Node 1',
        stressCount: 0,
      ),
    );

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SizedBox(
            width: 1200,
            height: 800,
            child: TopologyGraph(
              graph: graph,
              selectedNodeId: null,
              onNodeSelected: (_) {},
              showLabels: true,
            ),
          ),
        ),
      ),
    );
    await tester.pump();

    expect(find.byType(TopologyGraph), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('renders a 40 persona faction graph without a center node',
      (tester) async {
    final nodes = List.generate(
      40,
      (index) => GraphNode(
        id: 'persona-$index',
        name: '角色 $index',
        type: 'persona',
        group: ['蜀汉', '曹魏', '东吴', '群雄'][index % 4],
        weight: 1,
        emotion: 'setting',
        intimacy: 0,
        interaction: 0,
        trust: 0,
        recentActive: false,
        activeScore: 0,
        relationshipScore: 60,
        hint: '设定完整度 60%',
        scoreComponents: const {'setting_completeness': 0.6},
        changeReasons: const ['来源：curated'],
      ),
    );
    final links = List.generate(
      80,
      (index) => GraphLink(
        source: 'persona-${index % 40}',
        target: 'persona-${(index * 5 + 3) % 40}',
        strength: 0.7,
        interaction: 0,
        emotion: 'setting',
        width: 3,
        relationType: '联盟',
      ),
    );

    await tester.pumpWidget(
      MaterialApp(
        home: SizedBox(
          width: 1200,
          height: 800,
          child: TopologyGraph(
            graph: RelationshipGraph(
              nodes: nodes,
              links: links,
              insights: const GraphInsights(
                topChanges: [],
                activeCount: 0,
                strongestTie: null,
                stressCount: 0,
              ),
            ),
            selectedNodeId: null,
            onNodeSelected: (_) {},
            showLabels: true,
          ),
        ),
      ),
    );
    await tester.pump();

    expect(find.byType(TopologyGraph), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
