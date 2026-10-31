"""Unit guard matrix; paired with real HTTP/PG audit-boundaries.spec.ts."""
from uuid import UUID
import ast
from pathlib import Path
import pytest
from fastapi import HTTPException
from auth.audit_router import _require_visit_access, _require_visit_child

X, Y, V, OWNER, ASSIGNED, OTHER = [UUID(int=n) for n in range(1,7)]

class GuardDB:
    def __init__(self, actor, visit):
        self.actor, self.visit, self.queries = actor, visit, []
    async def fetchrow(self, sql, *args):
        self.queries.append((sql,args))
        if 'FROM users' in sql:
            assert args[0] == self.actor['id']
            return self.actor
        if 'FROM audit_visits' in sql:
            assert 'id=$1 AND ' in sql
            column = 'provider_id' if 'provider_id = $2' in sql else 'auditor_id'
            assert column == 'provider_id' or 'auditor_id = $2' in sql
            return self.visit if UUID(str(args[0])) == V and args[1] == self.visit[column] else None
        raise AssertionError(sql)
    async def fetchval(self, sql, *args):
        self.queries.append((sql,args))
        assert 'WHERE id=$1 AND visit_id=$2' in sql
        return None

@pytest.mark.asyncio
@pytest.mark.parametrize('owner,tenant,actor_id,role,status,allowed',[
    (True,X,OWNER,'cb_admin','active',True),
    (False,X,ASSIGNED,'auditor','active',True),
    (True,Y,OTHER,'cb_admin','active',False),
    (False,X,OTHER,'auditor','active',False),
    (True,X,OWNER,'platform_admin','active',False),
    (True,X,OWNER,'cb_admin','suspended',False),
])
async def test_current_canonical_actor_controls_audit_access(owner,tenant,actor_id,role,status,allowed):
    actor={'id':actor_id,'tenant_id':tenant,'is_owner':owner,'role':'provider','status':status}
    visit={'id':V,'provider_id':X,'auditor_id':ASSIGNED,'status':'in_progress'}
    db=GuardDB(actor,visit)
    # Deliberately forged/stale owner and tenant claims cannot widen scope.
    user={'role':'provider','is_owner':True,'tenant_id':str(X),'app_user_id':str(actor_id),'realm_roles':[role]}
    if allowed:
        assert await _require_visit_access(str(V),user,db,lock=True) == visit
        assert any(sql.endswith(' FOR UPDATE') for sql,args in db.queries)
    else:
        with pytest.raises(HTTPException) as exc:await _require_visit_access(str(V),user,db,lock=True)
        assert exc.value.status_code in (403,404)

@pytest.mark.asyncio
@pytest.mark.parametrize('status',['report_submitted','report_accepted'])
async def test_frozen_observations_cannot_be_edited(status):
    actor={'id':OWNER,'tenant_id':X,'is_owner':True,'role':'provider','status':'active'}
    db=GuardDB(actor,{'id':V,'provider_id':X,'auditor_id':ASSIGNED,'status':status})
    user={'role':'provider','app_user_id':str(OWNER),'realm_roles':['cb_admin']}
    with pytest.raises(HTTPException) as exc:await _require_visit_access(str(V),user,db,lock=True,mutable=True)
    assert exc.value.status_code == 409

@pytest.mark.asyncio
async def test_owner_cannot_generate_an_assigned_auditor_report():
    actor={'id':OWNER,'tenant_id':X,'is_owner':True,'role':'provider','status':'active'}
    db=GuardDB(actor,{'id':V,'provider_id':X,'auditor_id':ASSIGNED,'status':'completed'})
    user={'role':'provider','app_user_id':str(OWNER),'realm_roles':['cb_admin']}
    with pytest.raises(HTTPException) as exc:await _require_visit_access(str(V),user,db,assigned_only=True)
    assert exc.value.status_code == 403

@pytest.mark.asyncio
async def test_wrong_parent_child_id_fails_before_any_file_or_row_write():
    db=GuardDB({}, {})
    with pytest.raises(HTTPException) as exc:await _require_visit_child(str(V),str(OTHER),'audit_visit_items',db)
    assert exc.value.status_code == 404
    with pytest.raises(ValueError):await _require_visit_child(str(V),str(OTHER),'users; DROP TABLE users',db)
    assert len(db.queries) == 1

def test_every_visit_route_has_resource_guard_and_transaction_dependency():
    source=Path(__file__).parents[1]/'auth/audit_router.py'
    tree=ast.parse(source.read_text())
    checked=[]
    for node in tree.body:
        if not isinstance(node,ast.AsyncFunctionDef):continue
        routes=[d for d in node.decorator_list if isinstance(d,ast.Call) and isinstance(d.func,ast.Attribute) and d.args and isinstance(d.args[0],ast.Constant) and str(d.args[0].value).startswith('/{vid}')]
        if not routes:continue
        calls=[n for n in ast.walk(node) if isinstance(n,ast.Call)]
        assert any(getattr(n.func,'id',None)=='_require_visit_access' for n in calls),node.name
        assert any(getattr(n.func,'id',None)=='Depends' and n.args and getattr(n.args[0],'id',None)=='get_scoped_audit_db' for n in calls),node.name
        checked.append(node.name)
    assert len(checked)>=22
