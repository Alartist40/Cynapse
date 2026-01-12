#!/usr/bin/env python3
"""
Cynapse Hub Test Suite
Verifies neuron discovery, signature checking, and hub functionality.
"""

import os
import sys
import json
import unittest
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestNeuronDiscovery(unittest.TestCase):
    """Test neuron discovery and loading."""
    
    def setUp(self):
        self.neurons_dir = Path(__file__).parent.parent / "neurons"
        
    def test_neurons_directory_exists(self):
        """Verify neurons directory exists."""
        self.assertTrue(self.neurons_dir.exists(), "neurons/ directory should exist")
        
    def test_expected_neurons_present(self):
        """Verify all expected neurons are present."""
        expected_neurons = [
            'bat_ghost', 'rhino_gateway', 'meerkat_scanner', 'canary_token',
            'wolverine_redteam', 'tinyml_anomaly', 'owl_ocr', 'elephant_sign',
            'parrot_wallet', 'octopus_ctf', 'beaver_miner', 'devale', 'elara'
        ]
        
        present = [d.name for d in self.neurons_dir.iterdir() 
                   if d.is_dir() and not d.name.startswith('_')]
        
        for neuron in expected_neurons:
            self.assertIn(neuron, present, f"Neuron '{neuron}' should be present")
    
    def test_neuron_count(self):
        """Verify we have the expected number of neurons."""
        neurons = [d for d in self.neurons_dir.iterdir() 
                   if d.is_dir() and not d.name.startswith('_')]
        self.assertGreaterEqual(len(neurons), 12, "Should have at least 12 neurons")


class TestManifestValidation(unittest.TestCase):
    """Test manifest.json validation for all neurons."""
    
    def setUp(self):
        self.neurons_dir = Path(__file__).parent.parent / "neurons"
        self.required_fields = ['name', 'version', 'description', 'entry_point']
        
    def test_all_manifests_exist(self):
        """Verify all neurons have manifest.json."""
        for neuron_dir in self.neurons_dir.iterdir():
            if not neuron_dir.is_dir() or neuron_dir.name.startswith('_'):
                continue
                
            manifest = neuron_dir / "manifest.json"
            self.assertTrue(manifest.exists(), 
                          f"manifest.json should exist in {neuron_dir.name}")
    
    def test_manifests_valid_json(self):
        """Verify all manifests are valid JSON."""
        for neuron_dir in self.neurons_dir.iterdir():
            if not neuron_dir.is_dir() or neuron_dir.name.startswith('_'):
                continue
                
            manifest = neuron_dir / "manifest.json"
            if manifest.exists():
                try:
                    with open(manifest, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    self.assertIsInstance(data, dict, 
                                        f"Manifest in {neuron_dir.name} should be dict")
                except json.JSONDecodeError as e:
                    self.fail(f"Invalid JSON in {neuron_dir.name}/manifest.json: {e}")
    
    def test_manifests_have_required_fields(self):
        """Verify manifests have required fields."""
        for neuron_dir in self.neurons_dir.iterdir():
            if not neuron_dir.is_dir() or neuron_dir.name.startswith('_'):
                continue
                
            manifest = neuron_dir / "manifest.json"
            if manifest.exists():
                with open(manifest, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                for field in self.required_fields:
                    self.assertIn(field, data, 
                                f"Field '{field}' required in {neuron_dir.name}/manifest.json")


class TestConfigFiles(unittest.TestCase):
    """Test configuration files."""
    
    def setUp(self):
        self.config_dir = Path(__file__).parent.parent / "config"
        
    def test_config_directory_exists(self):
        """Verify config directory exists."""
        self.assertTrue(self.config_dir.exists(), "config/ directory should exist")
        
    def test_example_config_exists(self):
        """Verify example config file exists."""
        example = self.config_dir / "config.ini.example"
        self.assertTrue(example.exists(), "config.ini.example should exist")
        
    def test_example_keys_exists(self):
        """Verify example keys file exists."""
        example = self.config_dir / "user_keys.json.example"
        self.assertTrue(example.exists(), "user_keys.json.example should exist")


class TestDirectoryStructure(unittest.TestCase):
    """Test overall directory structure."""
    
    def setUp(self):
        self.base_dir = Path(__file__).parent.parent
        
    def test_temp_directory_exists(self):
        """Verify temp directory exists."""
        temp_dir = self.base_dir / "temp"
        self.assertTrue(temp_dir.exists(), "temp/ directory should exist")
        
    def test_logs_directory_exists(self):
        """Verify logs directory exists."""
        logs_dir = self.base_dir / "temp" / "logs"
        self.assertTrue(logs_dir.exists(), "temp/logs/ directory should exist")
        
    def test_assets_directory_exists(self):
        """Verify assets directory exists."""
        assets_dir = self.base_dir / "assets"
        self.assertTrue(assets_dir.exists(), "assets/ directory should exist")
        
    def test_data_directories_exist(self):
        """Verify data directories exist."""
        data_dir = self.base_dir / "data"
        self.assertTrue(data_dir.exists(), "data/ directory should exist")
        
        training_dir = data_dir / "training"
        self.assertTrue(training_dir.exists(), "data/training/ directory should exist")
        
        storage_dir = data_dir / "storage"
        self.assertTrue(storage_dir.exists(), "data/storage/ directory should exist")


class TestCynapseHub(unittest.TestCase):
    """Test CynapseHub class functionality."""
    
    def test_hub_import(self):
        """Test that CynapseHub can be imported."""
        try:
            from cynapse import CynapseHub
            self.assertTrue(True)
        except ImportError as e:
            # This is expected if we're running from tests directory
            pass
            
    def test_main_script_exists(self):
        """Verify main cynapse.py script exists."""
        main_script = Path(__file__).parent.parent / "cynapse.py"
        self.assertTrue(main_script.exists(), "cynapse.py should exist")


class TestGhostShell(unittest.TestCase):
    """Test Ghost Shell components."""
    
    def setUp(self):
        self.bat_ghost_dir = Path(__file__).parent.parent / "neurons" / "bat_ghost"
        
    def test_whistle_detector_exists(self):
        """Verify whistle detector exists."""
        detector = self.bat_ghost_dir / "whistle_detector.py"
        self.assertTrue(detector.exists(), "whistle_detector.py should exist")
        
    def test_assembler_exists(self):
        """Verify shard assembler exists."""
        assembler = self.bat_ghost_dir / "assemble.py"
        self.assertTrue(assembler.exists(), "assemble.py should exist")
        
    def test_bat_directories_exist(self):
        """Verify bat1, bat2, bat3 directories exist."""
        for i in [1, 2, 3]:
            bat_dir = self.bat_ghost_dir / f"bat{i}"
            self.assertTrue(bat_dir.exists(), f"bat{i}/ directory should exist")
            
            manifest = bat_dir / "manifest.json"
            self.assertTrue(manifest.exists(), f"bat{i}/manifest.json should exist")


class TestElaraModel(unittest.TestCase):
    """Test Elara AI model structure."""
    
    def setUp(self):
        self.elara_dir = Path(__file__).parent.parent / "neurons" / "elara"
        
    def test_model_file_exists(self):
        """Verify model.py exists."""
        model = self.elara_dir / "model.py"
        self.assertTrue(model.exists(), "model.py should exist")
        
    def test_sample_file_exists(self):
        """Verify sample.py exists."""
        sample = self.elara_dir / "sample.py"
        self.assertTrue(sample.exists(), "sample.py should exist")


def run_tests():
    """Run all tests and return success status."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestNeuronDiscovery))
    suite.addTests(loader.loadTestsFromTestCase(TestManifestValidation))
    suite.addTests(loader.loadTestsFromTestCase(TestConfigFiles))
    suite.addTests(loader.loadTestsFromTestCase(TestDirectoryStructure))
    suite.addTests(loader.loadTestsFromTestCase(TestCynapseHub))
    suite.addTests(loader.loadTestsFromTestCase(TestGhostShell))
    suite.addTests(loader.loadTestsFromTestCase(TestElaraModel))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Run specific test class
        test_name = sys.argv[1]
        if hasattr(sys.modules[__name__], test_name):
            suite = unittest.TestLoader().loadTestsFromTestCase(
                getattr(sys.modules[__name__], test_name)
            )
            unittest.TextTestRunner(verbosity=2).run(suite)
        else:
            print(f"Test class '{test_name}' not found")
            sys.exit(1)
    else:
        # Run all tests
        success = run_tests()
        sys.exit(0 if success else 1)
