"""Bounded-freshness Keycloak session and effective-role verification.

The cache contains only role tuples keyed by issuer and a token digest, never
an application profile/current user. Database authority is still read per request.
"""
from collections import OrderedDict
import hashlib
import os
import time
from urllib.parse import quote
import httpx
from fastapi import HTTPException
from . import keycloak_admin as admin

_TTL = max(0, min(30, int(os.getenv('KEYCLOAK_AUTHZ_TTL_SECONDS', '30'))))
_cache: OrderedDict[tuple[str,str], tuple[float,tuple[str,...]]] = OrderedDict()

async def current_realm_roles(token: str, claims: dict) -> tuple[str,...]:
    key = (str(claims.get('iss')), hashlib.sha256(token.encode()).hexdigest())
    cached = _cache.get(key)
    if cached and cached[0] > time.monotonic():
        _cache.move_to_end(key)
        return cached[1]
    client_id = os.getenv('KEYCLOAK_AUTHZ_CLIENT_ID') or admin.ADMIN_CLI_CLIENT_ID
    secret = os.getenv('KEYCLOAK_AUTHZ_CLIENT_SECRET') or admin.ADMIN_CLI_SECRET
    if not secret:
        raise HTTPException(503, 'Identity authority verification unavailable')
    base = admin.KEYCLOAK_ADMIN_URL
    realm = quote(admin.KEYCLOAK_REALM, safe='')
    protocol = base+'/realms/'+realm+'/protocol/openid-connect'
    subject = quote(claims['sub'], safe='')
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            introspection = await client.post(protocol+'/token/introspect',data={'client_id':client_id,'client_secret':secret,'token':token,'token_type_hint':'access_token'})
            introspection.raise_for_status()
            active = introspection.json()
            if active.get('active') is not True or active.get('sub') != claims['sub']:
                raise HTTPException(401, 'Session is no longer active')
            service = await client.post(protocol+'/token',data={'grant_type':'client_credentials','client_id':client_id,'client_secret':secret})
            service.raise_for_status()
            headers = {'Authorization':'Bearer '+service.json()['access_token']}
            url = base+'/admin/realms/'+realm+'/users/'+subject
            account = await client.get(url,headers=headers)
            if account.status_code == 404:
                raise HTTPException(401, 'Account is no longer active')
            account.raise_for_status()
            if account.json().get('enabled') is not True or account.json().get('id') != claims['sub']:
                raise HTTPException(401, 'Account is no longer active')
            response = await client.get(url+'/role-mappings/realm/composite',headers=headers)
            response.raise_for_status()
            roles = tuple(sorted({role['name'] for role in response.json() if isinstance(role,dict) and isinstance(role.get('name'),str)}))
    except (httpx.HTTPError,ValueError,KeyError,TypeError):
        raise HTTPException(503, 'Identity authority verification unavailable') from None
    remaining = float(claims['exp']) - time.time()
    if remaining <= 0:
        raise HTTPException(401, 'Session expired')
    _cache[key] = (time.monotonic()+min(_TTL,remaining),roles)
    _cache.move_to_end(key)
    while len(_cache)>1024:
        _cache.popitem(last=False)
    return roles
