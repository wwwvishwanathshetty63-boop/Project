import logging
import json
from openai import OpenAI
from backend.config import Config

logger = logging.getLogger(__name__)

def detect_api_url_from_key(api_key: str) -> dict:
    """
    Uses OpenAI to analyze an API key structure and guess the provider's base URL.
    
    Args:
        api_key: The API key string to analyze.
        
    Returns:
        dict: {
            "success": bool,
            "provider": str | None,
            "base_url": str | None,
            "error": str | None
        }
    """
    if not api_key or not api_key.strip():
        return {"success": False, "error": "API key is required."}
        
    if not Config.OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY is missing from configuration.")
        return {"success": False, "error": "AI detection is currently unavailable (Missing API Key)."}

    # Mask key for logging to prevent leaking sensitive info
    masked_key = f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) > 8 else "****"

    try:
        client = OpenAI(api_key=Config.OPENAI_API_KEY)
        
        prompt = f"""
        You are an expert API system analyzer. I will provide you with an API key. 
        Your job is to identify the likely API provider based on the format, prefixes, or entropy of the key, 
        and provide the primary health-check base URL for that provider.
        
        API Key to analyze: {api_key}
        
        Rules:
        1. If you can confidently identify the provider (e.g. Stripe, SendGrid, OpenAI, GitHub, Slack, etc.), return the provider name and the most general or common health-check 'base_url'. (e.g. 'https://api.stripe.com/v1/balance').
        2. If the key is a generic UUID, hex string, or you cannot identify the provider, return an error message "Unknown format".
        3. Respond ONLY with a raw JSON object, no markdown blocks, no extra text.
        
        Expected JSON format on success:
        {{"provider": "ExampleProvider", "base_url": "https://api.example.com/v1/status"}}
        
        Expected JSON format on failure:
        {{"error": "Unknown format"}}
        """
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a JSON-only API key analyzer."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0,
            response_format={ "type": "json_object" }
        )
        
        result_text = response.choices[0].message.content
        result_json = json.loads(result_text)
        
        if "error" in result_json:
            logger.info(f"AI Detector: Unknown format for key {masked_key}")
            return {"success": False, "error": result_json["error"]}
            
        provider = result_json.get("provider")
        base_url = result_json.get("base_url")
        
        if provider and base_url:
            logger.info(f"AI Detector: Identified {provider} for key {masked_key}")
            return {
                "success": True,
                "provider": provider,
                "base_url": base_url
            }
        else:
            return {"success": False, "error": "Invalid response format from AI"}
            
    except json.JSONDecodeError:
        logger.error(f"AI Detector: Failed to parse JSON response for key {masked_key}")
        return {"success": False, "error": "Failed to parse AI response."}
    except Exception as e:
        logger.error(f"AI Detector: Error during detection: {str(e)}")
        return {"success": False, "error": "An error occurred during AI detection."}
