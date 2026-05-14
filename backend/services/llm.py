from groq import Groq
from backend.config import get_settings
import logging
import json
import re
from typing import Optional

logger = logging.getLogger(__name__)
settings = get_settings()


class LLMService:
    """Groq API client for LLM calls"""
    
    def __init__(self):
        self.client = Groq(api_key=settings.groq_api_key)
        self.model = settings.llm_model
        self.temperature = settings.llm_temperature
        self.max_tokens = settings.llm_max_tokens
        logger.info(f"Initialized Groq client with model: {self.model}")
    
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Generate completion from Groq API
        
        Args:
            system_prompt: System instruction
            user_prompt: User message
            temperature: Override default temperature
            max_tokens: Override default max tokens
            
        Returns:
            Generated text
        """
        try:
            logger.debug(f"Calling Groq API with model: {self.model}")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=temperature or self.temperature,
                max_tokens=max_tokens or self.max_tokens
            )
            
            generated_text = response.choices[0].message.content
            logger.info(f"✅ LLM generated {len(generated_text)} characters")
            logger.debug(f"Response preview: {generated_text[:200]}...")
            return generated_text
            
        except Exception as e:
            logger.error(f"❌ Groq API error: {e}")
            raise
    
    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> dict:
        """
        Generate JSON response from Groq API with robust parsing
        
        Args:
            system_prompt: System instruction
            user_prompt: User message
            temperature: Override default temperature
            max_tokens: Override default max tokens
            
        Returns:
            Parsed JSON dict
            
        Raises:
            json.JSONDecodeError: If response cannot be parsed as JSON
        """
        response = self.generate(system_prompt, user_prompt, temperature, max_tokens)
        
        # Clean markdown code blocks
        response_clean = response.strip()
        
        # Remove ```json and ``` markers
        if response_clean.startswith("```json"):
            response_clean = response_clean[7:]
        elif response_clean.startswith("```"):
            response_clean = response_clean[3:]
        
        if response_clean.endswith("```"):
            response_clean = response_clean[:-3]
        
        response_clean = response_clean.strip()
        
        # Try to extract JSON if wrapped in text
        json_match = re.search(r'\{.*\}', response_clean, re.DOTALL)
        if json_match:
            response_clean = json_match.group(0)
        
        try:
            parsed = json.loads(response_clean)
            logger.info(f"✅ Successfully parsed JSON response")
            return parsed
        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse JSON response")
            logger.error(f"Error: {e}")
            logger.error(f"Response (first 500 chars): {response_clean[:500]}")
            raise


# Singleton instance
_llm_service = None


def get_llm_service() -> LLMService:
    """Get or create LLMService instance"""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service

# Made with Bob
