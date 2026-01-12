#!/usr/bin/env python3
"""
LLM integration module
Handles conversion of English text to structured JSON using local LLM
"""

import json
import re
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class LLMHandler:
    """Handles LLM inference for parsing English to firewall rule JSON"""
    
    def __init__(self, config: dict):
        """
        Initialize LLM handler
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.model_path = config.get("llm", {}).get("model_path", "models/mistral7b_int4.gguf")
        self.temperature = config.get("llm", {}).get("temperature", 0.1)
        self.max_tokens = config.get("llm", {}).get("max_tokens", 256)
        self.n_ctx = config.get("llm", {}).get("n_ctx", 2048)
        
        self.llm = None
        self._check_dependencies()
    
    def _check_dependencies(self):
        """Check if llama-cpp-python is installed"""
        try:
            from llama_cpp import Llama
            self.Llama = Llama
        except ImportError:
            logger.warning(
                "llama-cpp-python not installed. LLM features will not work. "
                "Install with: pip install llama-cpp-python"
            )
            self.Llama = None
    
    def _load_model(self):
        """Lazy load the LLM model"""
        if self.llm is None and self.Llama is not None:
            logger.info(f"[*] Loading LLM model from {self.model_path}...")
            
            import os
            if not os.path.exists(self.model_path):
                raise FileNotFoundError(
                    f"Model file not found: {self.model_path}\n"
                    "Please download the model and update config.json with the correct path.\n"
                    "See README.md for download instructions."
                )
            
            try:
                self.llm = self.Llama(
                    model_path=self.model_path,
                    n_ctx=self.n_ctx,
                    n_threads=4,
                    verbose=False
                )
                logger.info("[+] LLM model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load model: {e}")
                raise
    
    def _create_prompt(self, sentence: str) -> str:
        """
        Create few-shot prompt for the LLM
        
        Args:
            sentence: English description of firewall rule
            
        Returns:
            Formatted prompt string
        """
        prompt = """You are a firewall rule parser. Convert English sentences into strict JSON format with these fields:
- src_ip: source IP address or "any" or CIDR
- dst_ip: destination IP address or "any" or CIDR  
- proto: protocol (tcp, udp, icmp, or "any")
- dst_port: destination port number or "any"
- action: "allow" or "deny"
- time_start: start time in HH:MM format or "00:00"
- time_end: end time in HH:MM format or "23:59"
- platform: "any" or specific platform

Examples:

Sentence: "Block SSH from 192.168.1.50 after 6 pm"
JSON: {"src_ip":"192.168.1.50","dst_ip":"any","proto":"tcp","dst_port":"22","action":"deny","time_start":"18:00","time_end":"23:59","platform":"any"}

Sentence: "Allow HTTP from 10.0.0.0/24"
JSON: {"src_ip":"10.0.0.0/24","dst_ip":"any","proto":"tcp","dst_port":"80","action":"allow","time_start":"00:00","time_end":"23:59","platform":"any"}

Sentence: "Block RDP from any between 9 pm and 6 am"
JSON: {"src_ip":"any","dst_ip":"any","proto":"tcp","dst_port":"3389","action":"deny","time_start":"21:00","time_end":"06:00","platform":"any"}

Sentence: "Deny ICMP from 172.16.0.0/16"
JSON: {"src_ip":"172.16.0.0/16","dst_ip":"any","proto":"icmp","dst_port":"any","action":"deny","time_start":"00:00","time_end":"23:59","platform":"any"}

Now convert this sentence:

Sentence: "{sentence}"
JSON:"""
        
        return prompt.format(sentence=sentence)
    
    def _extract_json(self, response: str) -> Dict:
        """
        Extract JSON from LLM response
        
        Args:
            response: Raw LLM output
            
        Returns:
            Parsed JSON dictionary
        """
        # Try to find JSON object in response
        json_match = re.search(r'\{[^}]+\}', response)
        
        if json_match:
            json_str = json_match.group(0)
            try:
                return json.loads(json_str)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON: {e}")
        
        # Fallback: try to parse the entire response
        try:
            return json.loads(response.strip())
        except json.JSONDecodeError:
            pass
        
        # Last resort: create default rule
        logger.warning("Could not extract valid JSON, using fallback")
        return {
            "src_ip": "any",
            "dst_ip": "any",
            "proto": "tcp",
            "dst_port": "any",
            "action": "deny",
            "time_start": "00:00",
            "time_end": "23:59",
            "platform": "any"
        }
    
    def _validate_and_normalize(self, rule_json: Dict) -> Dict:
        """
        Validate and normalize the parsed JSON
        
        Args:
            rule_json: Raw parsed JSON
            
        Returns:
            Validated and normalized JSON
        """
        # Ensure all required fields exist
        defaults = {
            "src_ip": "any",
            "dst_ip": "any",
            "proto": "tcp",
            "dst_port": "any",
            "action": "deny",
            "time_start": "00:00",
            "time_end": "23:59",
            "platform": "any"
        }
        
        for key, default_value in defaults.items():
            if key not in rule_json:
                rule_json[key] = default_value
        
        # Normalize values
        rule_json["action"] = rule_json["action"].lower()
        rule_json["proto"] = rule_json["proto"].lower()
        
        # Convert port to string if it's a number
        if isinstance(rule_json["dst_port"], int):
            rule_json["dst_port"] = str(rule_json["dst_port"])
        
        return rule_json
    
    def english_to_json(self, sentence: str) -> Dict:
        """
        Convert English sentence to firewall rule JSON
        
        Args:
            sentence: English description of firewall rule
            
        Returns:
            Dictionary containing structured rule parameters
        """
        if self.Llama is None:
            # Fallback to simple pattern matching if LLM not available
            logger.warning("LLM not available, using simple parser")
            return self._simple_parse(sentence)
        
        self._load_model()
        
        prompt = self._create_prompt(sentence)
        
        logger.debug(f"Prompt: {prompt}")
        
        try:
            # Generate response from LLM
            response = self.llm(
                prompt,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                stop=["Sentence:", "\n\n"],
                echo=False
            )
            
            response_text = response["choices"][0]["text"].strip()
            logger.debug(f"LLM response: {response_text}")
            
            # Extract and parse JSON
            rule_json = self._extract_json(response_text)
            
            # Validate and normalize
            rule_json = self._validate_and_normalize(rule_json)
            
            return rule_json
            
        except Exception as e:
            logger.error(f"LLM inference failed: {e}")
            logger.warning("Falling back to simple parser")
            return self._simple_parse(sentence)
    
    def _simple_parse(self, sentence: str) -> Dict:
        """
        Simple pattern-based fallback parser when LLM is not available
        
        Args:
            sentence: English description
            
        Returns:
            Parsed rule dictionary
        """
        sentence_lower = sentence.lower()
        
        # Determine action
        if any(word in sentence_lower for word in ["block", "deny", "drop", "reject"]):
            action = "deny"
        else:
            action = "allow"
        
        # Determine protocol
        proto = "tcp"
        if "udp" in sentence_lower:
            proto = "udp"
        elif "icmp" in sentence_lower:
            proto = "icmp"
        
        # Extract port
        port = "any"
        port_keywords = {
            "ssh": "22",
            "http": "80",
            "https": "443",
            "rdp": "3389",
            "ftp": "21",
            "smtp": "25",
            "dns": "53"
        }
        for keyword, port_num in port_keywords.items():
            if keyword in sentence_lower:
                port = port_num
                break
        
        # Extract IP
        ip_pattern = r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?:/\d{1,2})?'
        ip_matches = re.findall(ip_pattern, sentence)
        src_ip = ip_matches[0] if ip_matches else "any"
        
        # Extract time
        time_start = "00:00"
        time_end = "23:59"
        
        time_patterns = [
            (r'after (\d{1,2})\s*pm', lambda h: (f"{int(h)+12:02d}:00", "23:59")),
            (r'after (\d{1,2})\s*am', lambda h: (f"{int(h):02d}:00", "23:59")),
            (r'between (\d{1,2})\s*pm and (\d{1,2})\s*am', 
             lambda h1, h2: (f"{int(h1)+12:02d}:00", f"{int(h2):02d}:00")),
        ]
        
        for pattern, time_func in time_patterns:
            match = re.search(pattern, sentence_lower)
            if match:
                time_start, time_end = time_func(*match.groups())
                break
        
        return {
            "src_ip": src_ip,
            "dst_ip": "any",
            "proto": proto,
            "dst_port": port,
            "action": action,
            "time_start": time_start,
            "time_end": time_end,
            "platform": "any"
        }
