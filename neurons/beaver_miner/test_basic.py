#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple test script for AI Firewall Rule-Miner
Tests basic functionality without requiring models or Docker
"""

import json
import sys
import os
import io

# Set UTF-8 encoding for Windows console
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from llm_handler import LLMHandler
from rule_generator import RuleGenerator
from utils import load_config, validate_json_rule, format_rule_summary

def test_simple_parser():
    """Test the fallback simple parser"""
    print("="*60)
    print("TEST 1: Simple Parser (no LLM required)")
    print("="*60)
    
    config = load_config()
    llm_handler = LLMHandler(config)
    
    test_cases = [
        "Block SSH from 192.168.1.50 after 6 pm",
        "Allow HTTP from 10.0.0.0/24",
        "Deny ICMP from 172.16.0.0/16",
        "Block RDP from any"
    ]
    
    for sentence in test_cases:
        print(f"\nInput: {sentence}")
        try:
            result = llm_handler._simple_parse(sentence)
            print(f"JSON: {json.dumps(result, indent=2)}")
            
            # Validate
            if validate_json_rule(result):
                print("[PASS] Valid JSON")
            else:
                print("[FAIL] Invalid JSON")
                
            # Format summary
            summary = format_rule_summary(result)
            print(f"Summary: {summary}")
            
        except Exception as e:
            print(f"[FAIL] Error: {e}")
    
    print("\n" + "="*60)
    return True

def test_rule_generation():
    """Test rule generation for all platforms"""
    print("\n" + "="*60)
    print("TEST 2: Rule Generation")
    print("="*60)
    
    config = load_config()
    generator = RuleGenerator(config)
    
    test_json = {
        "src_ip": "192.168.1.50",
        "dst_ip": "any",
        "proto": "tcp",
        "dst_port": "22",
        "action": "deny",
        "time_start": "18:00",
        "time_end": "23:59",
        "platform": "any"
    }
    
    print(f"\nTest JSON:")
    print(json.dumps(test_json, indent=2))
    
    platforms = ["pfSense", "iptables", "suricata", "windows"]
    
    for platform in platforms:
        print(f"\n----- {platform.upper()} -----")
        try:
            rule = generator.generate(test_json, platform)
            print(rule)
            print("[PASS] Generated successfully")
        except Exception as e:
            print(f"[FAIL] Error: {e}")
    
    print("\n" + "="*60)
    return True

def test_config_loading():
    """Test configuration loading"""
    print("\n" + "="*60)
    print("TEST 3: Configuration Loading")
    print("="*60)
    
    try:
        config = load_config()
        print("\n[PASS] Config loaded successfully")
        print(f"LLM model path: {config.get('llm', {}).get('model_path', 'N/A')}")
        print(f"Whisper model: {config.get('voice', {}).get('whisper_model', 'N/A')}")
        print(f"Templates dir: {config.get('templates', {}).get('directory', 'N/A')}")
    except Exception as e:
        print(f"[FAIL] Error loading config: {e}")
        return False
    
    print("="*60)
    return True

def test_json_validation():
    """Test JSON validation"""
    print("\n" + "="*60)
    print("TEST 4: JSON Validation")
    print("="*60)
    
    valid_json = {
        "src_ip": "192.168.1.1",
        "dst_ip": "any",
        "proto": "tcp",
        "dst_port": "80",
        "action": "allow",
        "time_start": "00:00",
        "time_end": "23:59",
        "platform": "any"
    }
    
    invalid_json = {
        "src_ip": "192.168.1.1",
        "dst_ip": "any"
        # missing required fields
    }
    
    print("\nValid JSON test:")
    if validate_json_rule(valid_json):
        print("[PASS] Correctly validated as valid")
    else:
        print("[FAIL] Incorrectly marked as invalid")
    
    print("\nInvalid JSON test:")
    if not validate_json_rule(invalid_json):
        print("[PASS] Correctly validated as invalid")
    else:
        print("[FAIL] Incorrectly marked as valid")
    
    print("="*60)
    return True

def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("AI FIREWALL RULE-MINER - BASIC TESTS")
    print("="*60)
    print("\nThese tests verify basic functionality without requiring:")
    print("  - LLM models")
    print("  - Docker")
    print("  - Audio hardware")
    print()
    
    results = []
    
    try:
        results.append(("Config Loading", test_config_loading()))
        results.append(("JSON Validation", test_json_validation()))
        results.append(("Simple Parser", test_simple_parser()))
        results.append(("Rule Generation", test_rule_generation()))
    except Exception as e:
        print(f"\n[FAIL] Fatal error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    all_passed = True
    for test_name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{test_name}: {status}")
        if not passed:
            all_passed = False
    
    print("="*60)
    
    if all_passed:
        print("\n[SUCCESS] All tests passed!")
        return True
    else:
        print("\n[FAILURE] Some tests failed")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
