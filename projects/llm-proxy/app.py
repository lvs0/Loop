"""
LLM Proxy - Unified API for Multiple LLM Providers

A middleware that routes LLM requests to the cheapest/available provider
with fallback, caching, and usage analytics.

Features:
- Multi-provider support (OpenAI, Anthropic, MiniMax, Ollama)
- Automatic fallback on failure
- Request caching with Redis
- Usage tracking and analytics
- Rate limiting per API key
- Cost optimization

Author: Orretter
Created: 2026-04-01
"""

from flask import Flask, request, jsonify
from functools import wraps
import os
import time
import hashlib
import json
import redis
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import httpx
from dataclasses import dataclass, asdict
from threading import Lock

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
class Config:
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')
    MINIMAX_API_KEY = os.getenv('MINIMAX_API_KEY', '')
    OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
    CACHE_TTL = int(os.getenv('CACHE_TTL', 3600))  # 1 hour default
    
    # Provider pricing (per 1M tokens)
    PROVIDER_PRICING = {
        'openai': {'input': 15.0, 'output': 60.0},  # gpt-4o-mini
        'anthropic': {'input': 15.0, 'output': 75.0},  # claude-3-haiku
        'minimax': {'input': 1.0, 'output': 5.0},  # Very cheap
        'ollama': {'input': 0.0, 'output': 0.0},  # Free (local)
    }
    
    # Provider fallback order
    FALLBACK_ORDER = ['ollama', 'minimax', 'openai', 'anthropic']
    
    # Rate limits (requests per minute)
    RATE_LIMITS = {
        'free': 10,
        'pro': 100,
        'enterprise': 1000
    }

config = Config()

# Initialize Redis
try:
    redis_client = redis.from_url(config.REDIS_URL, decode_responses=True)
    redis_client.ping()
    logger.info("Redis connected successfully")
except Exception as e:
    logger.warning(f"Redis not available: {e}. Caching disabled.")
    redis_client = None

# In-memory storage fallback
api_keys: Dict[str, dict] = {}
usage_stats: List[dict] = []
stats_lock = Lock()

@dataclass
class APIKey:
    key: str
    tier: str
    requests_used: int
    requests_limit: int
    created_at: datetime
    
    def to_dict(self):
        return {
            'key': self.key,
            'tier': self.tier,
            'requests_used': self.requests_used,
            'requests_limit': self.requests_limit,
            'created_at': self.created_at.isoformat()
        }

def generate_api_key() -> str:
    """Generate a new API key."""
    return hashlib.sha256(str(time.time()).encode()).hexdigest()[:32]

def get_cached_response(prompt: str, model: str) -> Optional[dict]:
    """Get cached response if available."""
    if not redis_client:
        return None
    
    cache_key = f"cache:{hashlib.sha256(f'{prompt}:{model}'.encode()).hexdigest()}"
    try:
        cached = redis_client.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception as e:
        logger.error(f"Cache read error: {e}")
    return None

def set_cached_response(prompt: str, model: str, response: dict):
    """Cache a response."""
    if not redis_client:
        return
    
    cache_key = f"cache:{hashlib.sha256(f'{prompt}:{model}'.encode()).hexdigest()}"
    try:
        redis_client.setex(cache_key, config.CACHE_TTL, json.dumps(response))
    except Exception as e:
        logger.error(f"Cache write error: {e}")

def check_rate_limit(api_key: str) -> bool:
    """Check if request is within rate limit."""
    if api_key not in api_keys:
        return False
    
    key_data = api_keys[api_key]
    return key_data['requests_used'] < key_data['requests_limit']

def increment_usage(api_key: str):
    """Increment usage counter for API key."""
    if api_key in api_keys:
        api_keys[api_key]['requests_used'] += 1

def get_provider_cost(provider: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate cost for a provider."""
    pricing = config.PROVIDER_PRICING.get(provider, {'input': 0, 'output': 0})
    return (input_tokens * pricing['input'] + output_tokens * output['output']) / 1_000_000

def find_cheapest_provider(providers: List[str]) -> Optional[str]:
    """Find cheapest available provider."""
    for provider in providers:
        # Check if API key is configured
        if provider == 'openai' and not config.OPENAI_API_KEY:
            continue
        if provider == 'anthropic' and not config.ANTHROPIC_API_KEY:
            continue
        if provider == 'minimax' and not config.MINIMAX_API_KEY:
            continue
        return provider
    return None

async def call_openai(messages: List[dict], model: str = 'gpt-4o-mini') -> dict:
    """Call OpenAI API."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            'https://api.openai.com/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {config.OPENAI_API_KEY}',
                'Content-Type': 'application/json'
            },
            json={
                'model': model,
                'messages': messages
            },
            timeout=60.0
        )
        return response.json()

async def call_anthropic(messages: List[dict], model: str = 'claude-3-haiku-20240307') -> dict:
    """Call Anthropic API."""
    # Convert messages format for Anthropic
    system = messages[0]['content'] if messages[0]['role'] == 'system' else ''
    anthropic_messages = [m for m in messages if m['role'] != 'system']
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            'https://api.anthropic.com/v1/messages',
            headers={
                'x-api-key': config.ANTHROPIC_API_KEY,
                'anthropic-version': '2023-06-01',
                'Content-Type': 'application/json'
            },
            json={
                'model': model,
                'max_tokens': 1024,
                'system': system,
                'messages': anthropic_messages
            },
            timeout=60.0
        )
        return response.json()

async def call_ollama(messages: List[dict], model: str = 'llama3') -> dict:
    """Call local Ollama instance."""
    async with httpx.AsyncClient() as client:
        # Convert to Ollama format
        ollama_messages = []
        system_msg = None
        
        for msg in messages:
            if msg['role'] == 'system':
                system_msg = msg['content']
            else:
                ollama_messages.append(msg)
        
        payload = {
            'model': model,
            'messages': ollama_messages,
            'stream': False
        }
        if system_msg:
            payload['system'] = system_msg
            
        response = await client.post(
            f'{config.OLLAMA_BASE_URL}/api/chat',
            json=payload,
            timeout=120.0
        )
        
        result = response.json()
        # Convert to OpenAI format
        return {
            'choices': [{
                'message': {
                    'role': result.get('message', {}).get('role', 'assistant'),
                    'content': result.get('message', {}).get('content', '')
                },
                'finish_reason': 'stop'
            }],
            'usage': {
                'prompt_tokens': result.get('eval_count', 0),
                'completion_tokens': result.get('prompt_eval_count', 0),
                'total_tokens': result.get('eval_count', 0) + result.get('prompt_eval_count', 0)
            },
            'model': model
        }

async def call_provider(provider: str, messages: List[dict], model: str) -> dict:
    """Call a specific provider."""
    if provider == 'openai':
        return await call_openai(messages, model)
    elif provider == 'anthropic':
        return await call_anthropic(messages, model)
    elif provider == 'ollama':
        return await call_ollama(messages, model)
    else:
        raise ValueError(f"Unknown provider: {provider}")

async def call_with_fallback(messages: List[dict], model: str, preferred_provider: str = None) -> dict:
    """Call provider with automatic fallback."""
    providers_to_try = []
    
    if preferred_provider:
        providers_to_try = [preferred_provider] + [p for p in config.FALLBACK_ORDER if p != preferred_provider]
    else:
        providers_to_try = config.FALLBACK_ORDER.copy()
    
    errors = []
    
    for provider in providers_to_try:
        try:
            logger.info(f"Trying provider: {provider}")
            result = await call_provider(provider, messages, model)
            result['provider'] = provider
            return result
        except Exception as e:
            logger.warning(f"Provider {provider} failed: {e}")
            errors.append({'provider': provider, 'error': str(e)})
            continue
    
    return {
        'error': 'All providers failed',
        'details': errors
    }

def track_usage(api_key: str, provider: str, model: str, input_tokens: int, output_tokens: int, cost: float):
    """Track API usage."""
    with stats_lock:
        usage_stats.append({
            'timestamp': datetime.utcnow().isoformat(),
            'api_key': api_key[:8] + '...',
            'provider': provider,
            'model': model,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'cost': cost
        })
        
        # Keep only last 10000 entries
        if len(usage_stats) > 10000:
            usage_stats[:] = usage_stats[-10000:]

# API Routes

@app.route('/v1/chat/completions', methods=['POST'])
async def chat_completions():
    """Main endpoint for chat completions."""
    # Get API key
    api_key = request.headers.get('Authorization', '').replace('Bearer ', '')
    
    if not api_key or api_key not in api_keys:
        return jsonify({'error': 'Invalid or missing API key'}), 401
    
    if not check_rate_limit(api_key):
        return jsonify({'error': 'Rate limit exceeded'}), 429
    
    # Parse request
    data = request.get_json()
    messages = data.get('messages', [])
    model = data.get('model', 'gpt-4o-mini')
    
    # Check cache
    cache_key = f"{messages[-1]['content'][:100]}:{model}"
    cached = get_cached_response(cache_key, model)
    if cached:
        cached['cached'] = True
        increment_usage(api_key)
        return jsonify(cached)
    
    # Make request with fallback
    result = await call_with_fallback(messages, model)
    
    if 'error' in result:
        return jsonify(result), 500
    
    # Track usage
    usage = result.get('usage', {})
    input_tokens = usage.get('prompt_tokens', 0)
    output_tokens = usage.get('completion_tokens', 0)
    cost = get_provider_cost(result.get('provider', 'unknown'), input_tokens, output_tokens)
    
    track_usage(api_key, result.get('provider', 'unknown'), model, input_tokens, output_tokens, cost)
    increment_usage(api_key)
    
    # Cache response
    set_cached_response(cache_key, model, result)
    
    return jsonify(result)

@app.route('/v1/models', methods=['GET'])
def list_models():
    """List available models."""
    models = {
        'openai': ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo'],
        'anthropic': ['claude-3-opus-20240229', 'claude-3-sonnet-20240229', 'claude-3-haiku-20240307'],
        'ollama': ['llama3', 'mistral', 'codellama', 'mixtral'],
        'minimax': ['abab5.5-chat', 'abab6-chat']
    }
    return jsonify({'data': models})

@app.route('/v1/keys', methods=['POST'])
def create_api_key():
    """Create a new API key."""
    data = request.get_json()
    tier = data.get('tier', 'free')
    
    if tier not in config.RATE_LIMITS:
        tier = 'free'
    
    key = generate_api_key()
    api_keys[key] = {
        'key': key,
        'tier': tier,
        'requests_used': 0,
        'requests_limit': config.RATE_LIMITS[tier],
        'created_at': datetime.utcnow()
    }
    
    return jsonify({
        'api_key': key,
        'tier': tier,
        'rate_limit': config.RATE_LIMITS[tier]
    })

@app.route('/v1/keys/<key>', methods=['GET'])
def get_key_info(key: str):
    """Get API key information."""
    if key not in api_keys:
        return jsonify({'error': 'Key not found'}), 404
    
    key_data = api_keys[key]
    return jsonify({
        'tier': key_data['tier'],
        'requests_used': key_data['requests_used'],
        'requests_limit': key_data['requests_limit'],
        'remaining': key_data['requests_limit'] - key_data['requests_used']
    })

@app.route('/v1/usage', methods=['GET'])
def get_usage():
    """Get usage statistics."""
    api_key = request.headers.get('X-API-Key', '')
    
    # Filter stats for this key
    user_stats = [s for s in usage_stats if s['api_key'] == api_key[:8] + '...']
    
    total_requests = len(user_stats)
    total_cost = sum(s['cost'] for s in user_stats)
    
    return jsonify({
        'total_requests': total_requests,
        'total_cost': total_cost,
        'recent': user_stats[-10:]
    })

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'redis': redis_client is not None,
        'active_keys': len(api_keys)
    })

@app.route('/')
def index():
    """Index page."""
    return jsonify({
        'name': 'LLM Proxy API',
        'version': '1.0.0',
        'endpoints': {
            'chat_completions': '/v1/chat/completions',
            'models': '/v1/models',
            'create_key': '/v1/keys (POST)',
            'usage': '/v1/usage'
        }
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
