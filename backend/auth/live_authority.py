"""Bounded-freshness Keycloak session and effective-role verification.

The cache contains only role tuples keyed by issuer and a token digest, never
an application profile/current user. Database authority is still read per request.
"""
import asyncio
import logging
from collections import OrderedDict
import hashlib
import os
import time
from urllib.parse import quote
from uuid import uuid4
import httpx
from fastapi import HTTPException
from . import keycloak_admin as admin

_TTL = max(0, min(30, int(os.getenv('KEYCLOAK_AUTHZ_TTL_SECONDS', '30'))))
_VERIFY_BUDGET_SECONDS = 7.0
_log = logging.getLogger(__name__)
_cache: OrderedDict[tuple[str,str], tuple[float,tuple[str,...]]] = OrderedDict()

def _unavailable(stage: str, reason: str, elapsed: float, upstream_status: int | None = None) -> HTTPException:
    # Never log exception text, URLs, subjects, credentials or response bodies.
    trace = uuid4().hex
    _log.warning("identity_authority_unavailable trace=%s stage=%s reason=%s upstream_status=%s elapsed_ms=%d",
                 trace, stage, reason, upstream_status, int(elapsed * 1000))
    return HTTPException(503, 'Identity authority verification unavailable', headers={
        'X-Aminra-Auth-Trace': trace, 'X-Aminra-Auth-Error': 'authority_unavailable',
    })

async def current_realm_roles(token: str, claims: dict) -> tuple[str,...]:
    key = (str(claims.get('iss')), hashlib.sha256(token.encode()).hexdigest())
    cached = _cache.get(key)
    if cached and cached[0] > time.monotonic():
        _cache.move_to_end(key)
        return cached[1]
    client_id = os.getenv('KEYCLOAK_AUTHZ_CLIENT_ID') or admin.ADMIN_CLI_CLIENT_ID
    secret = os.getenv('KEYCLOAK_AUTHZ_CLIENT_SECRET') or admin.ADMIN_CLI_SECRET
    if not secret:
        raise _unavailable("configuration", "missing_credential", 0.0)
    base = admin.KEYCLOAK_ADMIN_URL
    realm = quote(admin.KEYCLOAK_REALM, safe='')
    protocol = base+'/realms/'+realm+'/protocol/openid-connect'
    subject = quote(claims['sub'], safe='')
    started = time.monotonic()
    stage = "introspection"
    try:
        async with asyncio.timeout(_VERIFY_BUDGET_SECONDS):
            async with httpx.AsyncClient(timeout=3.0) as client:
                introspection = await client.post(protocol+'/token/introspect',data={'client_id':client_id,'client_secret':secret,'token':token,'token_type_hint':'access_token'})
                introspection.raise_for_status()
                active = introspection.json()
                if active.get('active') is not True or active.get('sub') != claims['sub']:
                    raise HTTPException(401, 'Session is no longer active')
                stage = "service_token"
                service = await client.post(protocol+'/token',data={'grant_type':'client_credentials','client_id':client_id,'client_secret':secret})
                service.raise_for_status()
                headers = {'Authorization':'Bearer '+service.json()['access_token']}
                url = base+'/admin/realms/'+realm+'/users/'+subject
                stage = "account"
                account = await client.get(url,headers=headers)
                if account.status_code == 404:
                    raise HTTPException(401, 'Account is no longer active')
                account.raise_for_status()
                if account.json().get('enabled') is not True or account.json().get('id') != claims['sub']:
                    raise HTTPException(401, 'Account is no longer active')
                stage = "effective_roles"
                response = await client.get(url+'/role-mappings/realm/composite',headers=headers)
                response.raise_for_status()
                roles = tuple(sorted({role['name'] for role in response.json() if isinstance(role,dict) and isinstance(role.get('name'),str)}))
    except (httpx.HTTPError, ValueError, KeyError, TypeError, TimeoutError) as exc:
        upstream_status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
        raise _unavailable(stage, type(exc).__name__, time.monotonic() - started, upstream_status) from None
    remaining = float(claims['exp']) - time.time()
    if remaining <= 0:
        raise HTTPException(401, 'Session expired')
    _cache[key] = (time.monotonic()+min(_TTL,remaining),roles)
    _cache.move_to_end(key)
    while len(_cache)>1024:
        _cache.popitem(last=False)
    return roles
