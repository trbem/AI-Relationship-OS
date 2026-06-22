import 'package:flutter/material.dart';

import '../../models/simulation_seed.dart';
import '../../services/api_service.dart';
import '../group/group_simulation_page.dart';
import '../import/import_page.dart';
import '../map/relationship_map_page.dart';
import '../persons/persons_page.dart';
import '../settings/settings_page.dart';
import '../simulation/simulation_page.dart';
import '../worlds/persona_worlds_page.dart';

class HomePage extends StatefulWidget {
  const HomePage({
    super.key,
    required this.apiService,
    required this.onLogout,
  });

  final ApiService apiService;
  final Future<void> Function() onLogout;

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  int _currentIndex = 0;
  SimulationSeed? _simulationSeed;

  void _openSimulation(SimulationSeed seed) {
    setState(() {
      _simulationSeed = seed;
      _currentIndex = 2;
    });
  }

  @override
  Widget build(BuildContext context) {
    final pages = [
      RelationshipMapPage(
        apiService: widget.apiService,
        onOpenSimulation: _openSimulation,
      ),
      PersonsPage(
        apiService: widget.apiService,
        onOpenSimulation: _openSimulation,
      ),
      SimulationPage(
        apiService: widget.apiService,
        seed: _simulationSeed,
      ),
      PersonaWorldsPage(apiService: widget.apiService),
      GroupSimulationPage(apiService: widget.apiService),
      ImportPage(apiService: widget.apiService),
      SettingsPage(
        apiService: widget.apiService,
        onLogout: widget.onLogout,
      ),
    ];

    return Scaffold(
      body: IndexedStack(index: _currentIndex, children: pages),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _currentIndex,
        onDestinationSelected: (index) => setState(() => _currentIndex = index),
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.hub_outlined),
            label: '关系',
          ),
          NavigationDestination(
            icon: Icon(Icons.people_outline),
            label: '人物',
          ),
          NavigationDestination(
            icon: Icon(Icons.psychology_outlined),
            label: '推演',
          ),
          NavigationDestination(
            icon: Icon(Icons.public_outlined),
            label: '角色世界',
          ),
          NavigationDestination(
            icon: Icon(Icons.groups_2_outlined),
            label: '多人',
          ),
          NavigationDestination(
            icon: Icon(Icons.upload_file_outlined),
            label: '导入',
          ),
          NavigationDestination(
            icon: Icon(Icons.settings_outlined),
            label: '设置',
          ),
        ],
      ),
    );
  }
}
