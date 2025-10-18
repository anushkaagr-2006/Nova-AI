import os
import logging
from typing import Optional, List, Dict
from dotenv import load_dotenv
import openai
from tenacity import retry, stop_after_attempt, wait_exponential

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
    Nova AI Assistant - An intelligent chatbot with conversation memory,
    error handling, and retry logic.
    """
    
    def __init__(
        self, 
        model: str = "gpt-3.5-turbo",
        temperature: float = 0.7,
        max_tokens: int = 500
    ):
        """
        Initialize Nova Assistant with configurable parameters.
        
        Args:
            model: OpenAI model to use
            temperature: Controls randomness (0-2)
            max_tokens: Maximum response length
        """
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        
        openai.api_key = self.api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.conversation_history: List[Dict[str, str]] = []
        
        # System prompt defining Nova's personality
        self.system_prompt = {
            "role": "system",
            "content": (
                "You are Nova, a friendly and knowledgeable AI assistant. "
                "You provide helpful, accurate, and concise responses. "
                "You maintain a professional yet approachable tone."
            )
        }
        
        logger.info(f"Nova Assistant initialized with model: {model}")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def _call_openai_api(self, messages: List[Dict[str, str]]) -> str:
        """
        Make API call with retry logic for transient failures.
        
        Args:
            messages: List of message dictionaries
            
        Returns:
            AI response content
        """
        response = openai.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            top_p=0.9,
            frequency_penalty=0.0,
            presence_penalty=0.6
        )
        return response.choices[0].message.content
    
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
            messages = [self.system_prompt]
            
            # Add conversation history if requested
            if use_context and self.conversation_history:
                messages.extend(self.conversation_history[-10:])  # Last 10 exchanges
            
            # Add current question
            user_message = {"role": "user", "content": question}
            messages.append(user_message)
            
            # Get response from API
            logger.info(f"Processing query: {question[:50]}...")
            response_content = self._call_openai_api(messages)
            
            # Update conversation history
            self.conversation_history.append(user_message)
            self.conversation_history.append({
                "role": "assistant",
                "content": response_content
            })
            
            logger.info("Response generated successfully")
            return response_content
            
        except openai.AuthenticationError:
            logger.error("OpenAI API authentication failed")
            return "⚠️ Authentication error. Please check your API key."
        
        except openai.RateLimitError:
            logger.error("OpenAI API rate limit exceeded")
            return "⚠️ Rate limit exceeded. Please try again in a moment."
        
        except openai.APIError as e:
            logger.error(f"OpenAI API error: {e}")
            return "⚠️ API service temporarily unavailable. Please try again."
        
        except Exception as e:
            logger.exception(f"Unexpected error: {e}")
            return "⚠️ Sorry, Nova encountered an unexpected error. Please try again."
    
    def clear_history(self) -> None:
        """Clear conversation history."""
        self.conversation_history.clear()
        logger.info("Conversation history cleared")
    
    def get_history(self) -> List[Dict[str, str]]:
        """
        Get conversation history.
        
        Returns:
            List of conversation messages
        """
        return self.conversation_history.copy()
    
    def set_system_prompt(self, prompt: str) -> None:
        """
        Update Nova's system prompt.
        
        Args:
            prompt: New system prompt
        """
        self.system_prompt["content"] = prompt
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
    nova = NovaAssistant(temperature=0.7)
    
    # Single question
    response = nova.ask("What is artificial intelligence?")
    print(f"Nova: {response}\n")
    
    # Conversation with context
    response = nova.ask("What are its main applications?")
    print(f"Nova: {response}\n")
    
    # View conversation history
    print(f"Total exchanges: {len(nova.get_history()) // 2}")
    
    # Clear history
    nova.clear_history()