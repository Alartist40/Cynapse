#!/usr/bin/env python3
"""
AI Firewall Rule-Miner v2.0
Async orchestrator for English-to-Firewall-Rule conversion and verification.
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Import our modules
from voice_handler import VoiceHandler
from llm_handler import LLMHandler
from rule_generator import RuleGenerator
from verifier import RuleVerifier
from utils import setup_logging, save_rule_to_file, print_banner, load_config, validate_json_rule

logger = setup_logging()

class RuleMiner:
    """Main application class for AI Firewall Rule-Miner (Async Optimized)"""
    
    def __init__(self, config_path: str = "config.json"):
        self.config = load_config(config_path)
        self.voice_handler = VoiceHandler(self.config)
        self.llm_handler = LLMHandler(self.config)
        self.rule_generator = RuleGenerator(self.config)
        self.verifier = RuleVerifier(self.config)
        
    async def process_input(self, text_input: Optional[str] = None,
                           use_voice: bool = False) -> str:
        if use_voice:
            logger.info("[*] Voice mode activated")
            return await asyncio.to_thread(self.voice_handler.record_and_transcribe)
        elif text_input:
            logger.info(f"[*] Text mode: {text_input}")
            return text_input
        else:
            raise ValueError("Either text_input or use_voice must be provided")
    
    async def parse_to_json(self, sentence: str) -> Dict:
        logger.info("[*] Parsing rule with local LLM...")
        # LLM inference can be slow, run in thread to not block event loop
        rule_json = await asyncio.to_thread(self.llm_handler.english_to_json, sentence)

        # Security: Validate the JSON rule
        if not validate_json_rule(rule_json):
            logger.error("[!] Security Alert: LLM generated invalid or unsafe rule parameters.")
            raise ValueError("Unsafe rule parameters detected.")

        logger.info(f"[+] Generated JSON: {json.dumps(rule_json, indent=2)}")
        return rule_json
    
    async def generate_rules(self, rule_json: Dict,
                            platforms: Optional[List[str]] = None) -> Dict[str, str]:
        if platforms is None:
            platforms = ["pfSense", "iptables", "suricata", "windows"]
        
        rules = {}
        for platform in platforms:
            logger.info(f"[*] Generating {platform} rule...")
            try:
                # Rule generation is typically fast/synchronous
                rule = self.rule_generator.generate(rule_json, platform)
                rules[platform] = rule
            except Exception as e:
                logger.error(f"[!] Failed to generate {platform} rule: {e}")
                rules[platform] = f"# Error: {e}"
        
        return rules
    
    async def verify_rules(self, rules: Dict[str, str], rule_json: Dict,
                         skip_verification: bool = False) -> Dict[str, bool]:
        if skip_verification:
            logger.info("[!] Skipping verification")
            return {platform: None for platform in rules.keys()}
        
        results = {}
        # Parallel verification for platforms that support it (Docker-based)
        tasks = []
        for platform, rule in rules.items():
            if platform.lower() in ["iptables", "suricata"]:
                tasks.append(self._verify_single(platform, rule, rule_json))
            else:
                results[platform] = None
        
        if tasks:
            verified_results = await asyncio.gather(*tasks)
            for platform, passed in verified_results:
                results[platform] = passed

        return results

    async def _verify_single(self, platform, rule, rule_json):
        logger.info(f"[*] Verifying {platform} rule in Docker...")
        try:
            passed = await asyncio.to_thread(self.verifier.verify, platform, rule, rule_json)
            status = "✅ PASS" if passed else "❌ BLOCKED"
            logger.info(f"[+] {platform}: {status}")
            return platform, passed
        except Exception as e:
            logger.error(f"[!] Verification failed for {platform}: {e}")
            return platform, False
    
    async def run(self, text_input: Optional[str] = None, use_voice: bool = False,
                 platforms: Optional[List[str]] = None, skip_verification: bool = False,
                 output_dir: str = "output") -> None:
        print_banner()
        
        try:
            # 1. Input
            sentence = await self.process_input(text_input, use_voice)
            print(f"\n[+] Input: \"{sentence}\"\n")
            
            # 2. Parse
            rule_json = await self.parse_to_json(sentence)
            
            # 3. Generate
            rules = await self.generate_rules(rule_json, platforms)
            
            # 4. Display
            print("\n" + "="*60 + "\nGENERATED RULES\n" + "="*60)
            for platform, rule in rules.items():
                print(f"\n----- {platform.upper()} -----\n{rule}")
            
            # 5. Verify (Parallel)
            results = await self.verify_rules(rules, rule_json, skip_verification)
            
            # 6. Save
            Path(output_dir).mkdir(exist_ok=True)
            for platform, rule in rules.items():
                save_rule_to_file(platform, rule, output_dir)

            print("\n" + "="*60 + "\nSUMMARY\n" + "="*60)
            for platform, passed in results.items():
                status = "✅ PASS" if passed is True else ("❌ FAIL" if passed is False else "⚠️ N/A")
                print(f"{platform:12} : {status}")
            print(f"\n[+] All outputs saved to '{output_dir}/'")
            
        except Exception as e:
            logger.error(f"[!] Error: {e}")
            sys.exit(1)

async def main():
    parser = argparse.ArgumentParser(description="AI Firewall Rule-Miner v2.0")
    parser.add_argument("text", nargs="?", help="Rule description")
    parser.add_argument("--voice", action="store_true", help="Use voice")
    parser.add_argument("--platform", nargs="+", help="Specific platforms")
    parser.add_argument("--no-verify", action="store_true", help="Skip Docker")
    parser.add_argument("--output", default="output", help="Output dir")
    
    args = parser.parse_args()
    if not args.text and not args.voice:
        parser.error("Either text or --voice required")

    miner = RuleMiner()
    await miner.run(
        text_input=args.text,
        use_voice=args.voice,
        platforms=args.platform,
        skip_verification=args.no_verify,
        output_dir=args.output
    )

if __name__ == "__main__":
    asyncio.run(main())
