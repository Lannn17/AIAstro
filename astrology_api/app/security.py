"""
Módulo de segurança para a aplicação AstroAPI.

Autenticação desativada para desenvolvimento local.
Para reativar: restaurar a lógica de APIKeyHeader e verify_api_key.
"""

async def verify_api_key():
    """Auth desativado — modo desenvolvimento local."""
    return None
