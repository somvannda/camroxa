"""Cloudflare Turnstile verification service for bot protection."""

import logging
from typing import Optional, TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from platform_api.config import Settings

logger = logging.getLogger(__name__)


class TurnstileService:
    """Service for verifying Cloudflare Turnstile tokens.
    
    Turnstile is Cloudflare's CAPTCHA replacement - privacy-focused,
    user-friendly alternative to reCAPTCHA.
    
    Usage:
        turnstile = TurnstileService(settings)
        is_valid = await turnstile.verify(token, client_ip)
    """
    
    VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
    
    def __init__(self, settings: "Settings"):
        self._secret_key = settings.cloudflare_turnstile_secret_key
        if not self._secret_key:
            logger.warning(
                "CLOUDFLARE_TURNSTILE_SECRET_KEY not set - "
                "Turnstile verification will fail"
            )
    
    async def verify(
        self, 
        token: str, 
        remote_ip: Optional[str] = None
    ) -> dict:
        """Verify a Turnstile token.
        
        Args:
            token: The Turnstile response token from frontend
            remote_ip: Client IP address (optional but recommended)
        
        Returns:
            Cloudflare siteverify response dict with keys:
            - success (bool): Whether verification passed
            - action (str): The action from the widget
            - hostname (str): The hostname where the token was generated
            - challenge_ts (str): Timestamp of the challenge
            - error-codes (list): Error codes if verification failed
        """
        logger.info(f"Turnstile verify called: token={token[:20]}..., remote_ip={remote_ip}")
        
        if not self._secret_key:
            logger.error("Cannot verify Turnstile - secret key not configured")
            return {"success": False, "error-codes": ["missing-input-secret"]}
        
        if not token:
            logger.warning("Empty Turnstile token provided")
            return {"success": False, "error-codes": ["missing-input-response"]}
        
        try:
            logger.info(f"Sending verification request to Cloudflare: {self.VERIFY_URL}")
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    self.VERIFY_URL,
                    data={
                        "secret": self._secret_key,
                        "response": token,
                        "remoteip": remote_ip  # Optional but helps prevent abuse
                    }
                )
                
                logger.info(f"Cloudflare response status: {response.status_code}")
                
                if response.status_code != 200:
                    logger.error(
                        f"Turnstile API returned {response.status_code}: "
                        f"{response.text}"
                    )
                    return {"success": False, "error-codes": [f"http-{response.status_code}"]}
                
                data = response.json()
                logger.info(f"Cloudflare response data: {data}")
                
                if not data.get("success", False):
                    error_codes = data.get("error-codes", [])
                    logger.error(
                        f"Turnstile verification FAILED - Error codes: {error_codes}, "
                        f"Full response: {data}"
                    )
                else:
                    logger.info("Turnstile verification successful")
                
                return data
                
        except httpx.TimeoutException as e:
            logger.error(f"Turnstile verification timed out: {e}", exc_info=True)
            return {"success": False, "error-codes": ["timeout"]}
        
        except httpx.HTTPError as e:
            logger.error(f"Turnstile verification HTTP error: {e}", exc_info=True)
            return {"success": False, "error-codes": ["http-error"]}
        
        except Exception as e:
            logger.error(f"Turnstile verification unexpected error: {type(e).__name__}: {e}", exc_info=True)
            return {"success": False, "error-codes": ["internal-error"]}
    
    async def verify_or_raise(
        self,
        token: str,
        remote_ip: Optional[str] = None,
        error_message: str = "Bot verification failed"
    ) -> None:
        """Verify token and raise exception if invalid.
        
        Convenience method for use in endpoints where you want to
        fail fast on invalid tokens.
        
        Args:
            token: Turnstile token
            remote_ip: Client IP
            error_message: Custom error message
        
        Raises:
            ValueError: If verification fails
        """
        is_valid = await self.verify(token, remote_ip)
        if not is_valid:
            raise ValueError(error_message)
