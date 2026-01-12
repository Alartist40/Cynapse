#!/usr/bin/env python3
"""
AI Firewall Rule-Miner (MVP)
Converts English (voice or text) into platform-specific firewall rules
and verifies them using Docker containers.
"""

import argparse
import sys
import json
import os
from pathlib import Path
from typing import Dict, List, Optional

# Import our modules
from voice_handler import VoiceHandler
from llm_handler import LLMHandler
from rule_generator import RuleGenerator
from verifier import RuleVerifier
from utils import setup_logging, save_rule_to_file, print_banner, load_config

logger = setup_logging()


class RuleMiner:
    """Main application class for AI Firewall Rule-Miner"""
    
    def __init__(self, config_path: str = "config.json"):
        """Initialize the Rule Miner with configuration"""
        self.config = load_config(config_path)
        self.voice_handler = VoiceHandler(self.config)
        self.llm_handler = LLMHandler(self.config)
        self.rule_generator = RuleGenerator(self.config)
        self.verifier = RuleVerifier(self.config)
        
    def process_input(self, text_input: Optional[str] = None, 
                     use_voice: bool = False) -> str:
        """
        Process input from either text or voice
        
        Args:
            text_input: Direct text input
            use_voice: Whether to use voice input
            
        Returns:
            Processed text string
        """
        if use_voice:
            logger.info("[*] Voice mode activated")
            return self.voice_handler.record_and_transcribe()
        elif text_input:
            logger.info(f"[*] Text mode: {text_input}")
            return text_input
        else:
            raise ValueError("Either text_input or use_voice must be provided")
    
    def parse_to_json(self, sentence: str) -> Dict:
        """
        Convert English sentence to structured JSON using LLM
        
        Args:
            sentence: English description of firewall rule
            
        Returns:
            Dictionary containing rule parameters
        """
        logger.info("[*] Parsing rule with local LLM...")
        rule_json = self.llm_handler.english_to_json(sentence)
        logger.info(f"[+] Generated JSON: {json.dumps(rule_json, indent=2)}")
        return rule_json
    
    def generate_rules(self, rule_json: Dict, 
                      platforms: Optional[List[str]] = None) -> Dict[str, str]:
        """
        Generate platform-specific firewall rules
        
        Args:
            rule_json: Parsed rule parameters
            platforms: List of platforms to generate for (default: all)
            
        Returns:
            Dictionary mapping platform names to rule strings
        """
        if platforms is None:
            platforms = ["pfSense", "iptables", "suricata", "windows"]
        
        rules = {}
        for platform in platforms:
            logger.info(f"[*] Generating {platform} rule...")
            try:
                rule = self.rule_generator.generate(rule_json, platform)
                rules[platform] = rule
                logger.info(f"[+] {platform} rule generated successfully")
            except Exception as e:
                logger.error(f"[!] Failed to generate {platform} rule: {e}")
                rules[platform] = f"# Error: {e}"
        
        return rules
    
    def verify_rules(self, rules: Dict[str, str], rule_json: Dict,
                    skip_verification: bool = False) -> Dict[str, bool]:
        """
        Verify generated rules using Docker containers
        
        Args:
            rules: Dictionary of platform rules
            rule_json: Original parsed rule parameters
            skip_verification: Skip Docker verification
            
        Returns:
            Dictionary mapping platforms to verification results
        """
        if skip_verification:
            logger.info("[!] Skipping verification (--no-verify flag)")
            return {platform: None for platform in rules.keys()}
        
        results = {}
        for platform, rule in rules.items():
            if platform in ["iptables", "suricata"]:
                logger.info(f"[*] Verifying {platform} rule in Docker...")
                try:
                    passed = self.verifier.verify(platform, rule, rule_json)
                    results[platform] = passed
                    status = "✅ PASS" if passed else "❌ BLOCKED"
                    logger.info(f"[+] {platform}: {status}")
                except Exception as e:
                    logger.error(f"[!] Verification failed for {platform}: {e}")
                    results[platform] = False
            else:
                logger.info(f"[!] Verification not implemented for {platform}")
                results[platform] = None
        
        return results
    
    def save_outputs(self, rules: Dict[str, str], rule_json: Dict,
                    output_dir: str = "output") -> None:
        """
        Save generated rules to files
        
        Args:
            rules: Dictionary of platform rules
            rule_json: Original parsed rule parameters
            output_dir: Directory to save outputs
        """
        Path(output_dir).mkdir(exist_ok=True)
        
        # Save JSON
        json_path = os.path.join(output_dir, "rule.json")
        with open(json_path, 'w') as f:
            json.dump(rule_json, f, indent=2)
        logger.info(f"[+] Saved JSON to {json_path}")
        
        # Save each platform rule
        for platform, rule in rules.items():
            filepath = save_rule_to_file(platform, rule, output_dir)
            logger.info(f"[+] Saved {platform} rule to {filepath}")
    
    def run(self, text_input: Optional[str] = None, use_voice: bool = False,
           platforms: Optional[List[str]] = None, skip_verification: bool = False,
           output_dir: str = "output") -> None:
        """
        Main execution flow
        
        Args:
            text_input: Direct text input
            use_voice: Use voice input instead
            platforms: List of platforms to generate for
            skip_verification: Skip Docker verification
            output_dir: Output directory for generated rules
        """
        print_banner()
        
        try:
            # Step 1: Get input
            sentence = self.process_input(text_input, use_voice)
            print(f"\n[+] Input: \"{sentence}\"\n")
            
            # Step 2: Parse to JSON
            rule_json = self.parse_to_json(sentence)
            
            # Step 3: Generate platform rules
            rules = self.generate_rules(rule_json, platforms)
            
            # Step 4: Display rules
            print("\n" + "="*60)
            print("GENERATED RULES")
            print("="*60)
            for platform, rule in rules.items():
                print(f"\n----- {platform.upper()} -----")
                print(rule)
            print("\n" + "="*60)
            
            # Step 5: Verify rules
            if not skip_verification:
                print("\n[*] Starting verification...\n")
                results = self.verify_rules(rules, rule_json, skip_verification)
                
                print("\n" + "="*60)
                print("VERIFICATION RESULTS")
                print("="*60)
                for platform, result in results.items():
                    if result is True:
                        print(f"{platform}: ✅ PASS")
                    elif result is False:
                        print(f"{platform}: ❌ BLOCKED")
                    else:
                        print(f"{platform}: ⚠️  NOT VERIFIED")
                print("="*60)
            
            # Step 6: Save outputs
            self.save_outputs(rules, rule_json, output_dir)
            print(f"\n[+] All outputs saved to '{output_dir}/' directory")
            print("[+] Done!\n")
            
        except KeyboardInterrupt:
            print("\n\n[!] Interrupted by user")
            sys.exit(1)
        except Exception as e:
            logger.error(f"[!] Error: {e}", exc_info=True)
            print(f"\n[!] Error: {e}")
            sys.exit(1)


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(
        description="AI Firewall Rule-Miner - Convert English to firewall rules",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Text input
  python rule_miner.py "Block SSH from 192.168.1.50 after 6 pm"
  
  # Voice input
  python rule_miner.py --voice
  
  # Specific platforms only
  python rule_miner.py "Allow HTTP from 10.0.0.0/24" --platform iptables suricata
  
  # Skip verification
  python rule_miner.py "Block RDP from any" --no-verify
        """
    )
    
    parser.add_argument(
        "text",
        nargs="?",
        help="English description of firewall rule (if not using --voice)"
    )
    
    parser.add_argument(
        "--voice",
        action="store_true",
        help="Use voice input instead of text"
    )
    
    parser.add_argument(
        "--platform",
        nargs="+",
        choices=["pfSense", "iptables", "suricata", "windows"],
        help="Specific platforms to generate rules for (default: all)"
    )
    
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip Docker verification step"
    )
    
    parser.add_argument(
        "--output",
        default="output",
        help="Output directory for generated rules (default: output)"
    )
    
    parser.add_argument(
        "--config",
        default="config.json",
        help="Path to configuration file (default: config.json)"
    )
    
    args = parser.parse_args()
    
    # Validate input
    if not args.text and not args.voice:
        parser.error("Either provide text input or use --voice flag")
    
    if args.text and args.voice:
        parser.error("Cannot use both text input and --voice flag")
    
    # Run the miner
    miner = RuleMiner(config_path=args.config)
    miner.run(
        text_input=args.text,
        use_voice=args.voice,
        platforms=args.platform,
        skip_verification=args.no_verify,
        output_dir=args.output
    )


if __name__ == "__main__":
    main()
