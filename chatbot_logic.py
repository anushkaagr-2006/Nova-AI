import os
import logging
from typing import List, Dict
from dotenv import load_dotenv
from huggingface_hub import InferenceClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class NovaAssistant:
    """
    Nova AI Assistant - Using Hugging Face InferenceClient
    Works with the new Chat Completion API (2025)
    """
    
    def __init__(
        self, 
        model: str = "meta-llama/Llama-3.2-3B-Instruct",
        temperature: float = 0.7,
        max_tokens: int = 500
    ):
        """
        Initialize Nova Assistant with Hugging Face InferenceClient.
        
        Args:
            model: Hugging Face model to use
            temperature: Controls randomness (0-1)
            max_tokens: Maximum response length
        """
        self.api_key = os.getenv("HUGGINGFACE_API_KEY")
        if not self.api_key:
            raise ValueError("HUGGINGFACE_API_KEY not found in environment variables")
        
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.conversation_history: List[Dict[str, str]] = []
        
        # Initialize InferenceClient
        self.client = InferenceClient(token=self.api_key)
        
        # System prompt defining Nova's personality
        self.system_prompt = (
            "You are Nova, a friendly and knowledgeable AI assistant. "
            "You provide helpful, accurate, and concise responses. "
            "You maintain a professional yet approachable tone."
        )
        
        logger.info(f"Nova Assistant initialized with model: {model}")
    
    def ask(self, question: str, use_context: bool = True) -> str:
        """
        Ask Nova a question with optional conversation context.
        
        Args:
            question: User's question
            use_context: Whether to include conversation history
            
        Returns:
            Nova's response
        """
        if not question or not question.strip():
            return "⚠️ Please provide a valid question."
        
        try:
            # Build messages list
            messages = [{"role": "system", "content": self.system_prompt}]
            
            # Add conversation history if requested
            if use_context and self.conversation_history:
                messages.extend(self.conversation_history[-6:])  # Last 3 exchanges
            
            # Add current question
            messages.append({"role": "user", "content": question})
            
            # Get response from API
            logger.info(f"Processing query: {question[:50]}...")
            
            completion = self.client.chat_completion(
                messages=messages,
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            response_content = completion.choices[0].message.content
            
            # Update conversation history
            self.conversation_history.append({
                "role": "user",
                "content": question
            })
            self.conversation_history.append({
                "role": "assistant",
                "content": response_content
            })
            
            logger.info("Response generated successfully")
            return response_content
            
        except Exception as e:
            error_msg = str(e).lower()
            logger.error(f"Error: {e}")
            
            if "rate limit" in error_msg or "429" in error_msg:
                return "⚠️ Rate limit reached. Please try again in a moment."
            elif "authentication" in error_msg or "401" in error_msg:
                return "⚠️ Authentication error. Please check your API key."
            elif "model" in error_msg or "404" in error_msg:
                return "⚠️ Model not available. Please try again later."
            elif "timeout" in error_msg:
                return "⚠️ Request timed out. Please try again."
            else:
                logger.exception("Unexpected error occurred")
                return "⚠️ Sorry, Nova encountered an error. Please try again."
    
    def clear_history(self) -> None:
        """Clear conversation history."""
        self.conversation_history.clear()
        logger.info("Conversation history cleared")
    
    def get_history(self) -> List[Dict[str, str]]:
        """Get conversation history."""
        return self.conversation_history.copy()
    
    def set_system_prompt(self, prompt: str) -> None:
        """Update Nova's system prompt."""
        self.system_prompt = prompt
        logger.info("System prompt updated")


# Convenience function for backward compatibility
def ask_nova(question: str) -> str:
    """
    Simple interface to ask Nova a question without context.
    
    Args:
        question: User's question
        
    Returns:
        Nova's response
    """
    assistant = NovaAssistant()
    return assistant.ask(question, use_context=False)


# Example usage
if __name__ == "__main__":
    # Initialize assistant
    nova = NovaAssistant()
    
    # Single question
    response = nova.ask("Hello, how are you?")
    print(f"Nova: {response}\n")
    
    # Conversation with context
    response = nova.ask("What is Python?")
    print(f"Nova: {response}\n")
    
    # View conversation history
    print(f"Total exchanges: {len(nova.get_history()) // 2}")