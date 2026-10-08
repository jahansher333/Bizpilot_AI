"""Email-addressed invitations (SEC-P1 F5).

- Inviting an email gives the same response whether or not it has a BizPilot account, so the
  invite form cannot be used to enumerate accounts.
- Invitations are matched to an account only by the signed-in user's own email, expire after
  7 days, and never leak another account's name or ID.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.organizations.models import OrganizationInvitation, OrganizationMember
from app.modules.trace.models import InternalTraceEvent

PASSWORD = "Invite-Security-2026!"
VOLATILE_FIELDS = {"id", "email", "created_at", "updated_at", "expires_at"}


@pytest.fixture
async def client(test_app: FastAPI, db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def _override_get_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    test_app.dependency_overrides[get_session] = _override_get_session
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://testserver") as c:
        yield c
    test_app.dependency_overrides.pop(get_session, None)


def _email(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}@example.com"


async def _register(client: AsyncClient, email: str) -> None:
    resp = await client.post("/api/auth/register", json={"email": email, "password": PASSWORD, "display_name": f"Name of {email}"})
    assert resp.status_code == 202


async def _token(client: AsyncClient, email: str) -> dict[str, str]:
    resp = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _owner_with_org(client: AsyncClient) -> tuple[dict[str, str], str]:
    email = _email("owner")
    await _register(client, email)
    headers = await _token(client, email)
    org = await client.post("/api/organizations", json={"display_name": "Invite Traders"}, headers=headers)
    assert org.status_code == 201
    return headers, org.json()["id"]


async def _invite(client: AsyncClient, owner: dict[str, str], org_id: str, email: str, role: str = "staff"):
    return await client.post(f"/api/organizations/{org_id}/members", json={"email": email, "role": role}, headers=owner)


# 1. No account enumeration through the invite form


@pytest.mark.asyncio
async def test_invite_response_is_identical_for_registered_and_unknown_emails(client: AsyncClient) -> None:
    owner, org_id = await _owner_with_org(client)
    registered = _email("registered")
    await _register(client, registered)
    unknown = _email("nobody")

    resp_registered = await _invite(client, owner, org_id, registered)
    resp_unknown = await _invite(client, owner, org_id, unknown)

    assert resp_registered.status_code == resp_unknown.status_code == 201
    body_registered, body_unknown = resp_registered.json(), resp_unknown.json()
    assert set(body_registered) == set(body_unknown)
    stable = lambda body: {k: v for k, v in body.items() if k not in VOLATILE_FIELDS}  # noqa: E731
    assert stable(body_registered) == stable(body_unknown)
    assert body_registered["email"] == registered and body_unknown["email"] == unknown
    # Nothing about the registered account leaks: no user ID, no display name.
    for body, text in ((body_registered, resp_registered.text), (body_unknown, resp_unknown.text)):
        assert "user_id" not in body and "display_name" not in body
        assert f"Name of {registered}" not in text
    assert set(resp_registered.headers) == set(resp_unknown.headers)


@pytest.mark.asyncio
async def test_inactive_accounts_are_indistinguishable_too(client: AsyncClient, db_session: AsyncSession) -> None:
    from app.modules.auth.models import User

    owner, org_id = await _owner_with_org(client)
    disabled = _email("disabled")
    await _register(client, disabled)
    await db_session.execute(update(User).where(User.email_normalized == disabled).values(status="disabled"))
    resp_disabled = await _invite(client, owner, org_id, disabled)
    resp_unknown = await _invite(client, owner, org_id, _email("nobody"))
    assert resp_disabled.status_code == resp_unknown.status_code == 201
    assert set(resp_disabled.json()) == set(resp_unknown.json())


@pytest.mark.asyncio
async def test_owner_lists_show_invitations_by_email_only(client: AsyncClient) -> None:
    owner, org_id = await _owner_with_org(client)
    registered = _email("registered")
    await _register(client, registered)
    await _invite(client, owner, org_id, registered)

    members = (await client.get(f"/api/organizations/{org_id}/members", headers=owner)).json()
    assert [m["email"] for m in members if m["email"] == registered] == []
    invitations = (await client.get(f"/api/organizations/{org_id}/invitations", headers=owner)).json()
    assert [i["email"] for i in invitations] == [registered]
    assert "display_name" not in invitations[0] and "user_id" not in invitations[0]


@pytest.mark.asyncio
async def test_trace_events_store_no_invited_email(client: AsyncClient, db_session: AsyncSession) -> None:
    owner, org_id = await _owner_with_org(client)
    email = _email("traced")
    invitation_id = (await _invite(client, owner, org_id, email)).json()["id"]
    events = (
        await db_session.execute(select(InternalTraceEvent).where(InternalTraceEvent.target_id == uuid.UUID(invitation_id)))
    ).scalars().all()
    assert events and events[0].target_type == "organization_invitation"
    assert all(email not in str(event.event_metadata) for event in events)


# 2. Invitations reach only the person whose email they name


@pytest.mark.asyncio
async def test_unregistered_invitee_can_register_later_and_accept(client: AsyncClient) -> None:
    owner, org_id = await _owner_with_org(client)
    invitee = _email("later")
    assert (await _invite(client, owner, org_id, invitee.upper(), role="manager")).status_code == 201

    await _register(client, invitee)
    headers = await _token(client, invitee)
    mine = (await client.get("/api/organizations/invitations", headers=headers)).json()
    assert [(i["organization_id"], i["role"]) for i in mine] == [(org_id, "manager")]

    accepted = await client.post(f"/api/organizations/{org_id}/members/accept", headers=headers)
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "active" and accepted.json()["role"] == "manager"
    assert (await client.get(f"/api/organizations/{org_id}", headers=headers)).status_code == 200
    assert (await client.get("/api/organizations/invitations", headers=headers)).json() == []


@pytest.mark.asyncio
async def test_other_accounts_cannot_see_or_accept_an_invitation(client: AsyncClient) -> None:
    owner, org_id = await _owner_with_org(client)
    await _invite(client, owner, org_id, _email("intended"))
    intruder = _email("intruder")
    await _register(client, intruder)
    headers = await _token(client, intruder)
    assert (await client.get("/api/organizations/invitations", headers=headers)).json() == []
    resp = await client.post(f"/api/organizations/{org_id}/members/accept", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_expired_invitation_cannot_be_seen_or_accepted(client: AsyncClient, db_session: AsyncSession) -> None:
    owner, org_id = await _owner_with_org(client)
    invitee = _email("expired")
    created = (await _invite(client, owner, org_id, invitee)).json()
    expires = datetime.fromisoformat(created["expires_at"])
    assert timedelta(days=6, hours=23) < expires - datetime.now(timezone.utc) <= timedelta(days=7)

    await db_session.execute(
        update(OrganizationInvitation)
        .where(OrganizationInvitation.id == uuid.UUID(created["id"]))
        .values(expires_at=datetime.now(timezone.utc) - timedelta(minutes=1))
    )
    await _register(client, invitee)
    headers = await _token(client, invitee)
    assert (await client.get("/api/organizations/invitations", headers=headers)).json() == []
    assert (await client.post(f"/api/organizations/{org_id}/members/accept", headers=headers)).status_code == 404
    assert (await client.get(f"/api/organizations/{org_id}/invitations", headers=owner)).json() == []

    # Re-inviting renews the same invitation for another 7 days.
    renewed = await _invite(client, owner, org_id, invitee)
    assert renewed.status_code == 201 and renewed.json()["id"] == created["id"]
    assert (await client.post(f"/api/organizations/{org_id}/members/accept", headers=headers)).status_code == 200


@pytest.mark.asyncio
async def test_reinvite_updates_role_and_keeps_one_invitation(client: AsyncClient) -> None:
    owner, org_id = await _owner_with_org(client)
    email = _email("twice")
    first = (await _invite(client, owner, org_id, email, role="staff")).json()
    second = await _invite(client, owner, org_id, email, role="manager")
    assert second.status_code == 201
    assert second.json()["id"] == first["id"] and second.json()["role"] == "manager"
    assert len((await client.get(f"/api/organizations/{org_id}/invitations", headers=owner)).json()) == 1


@pytest.mark.asyncio
async def test_inviting_a_current_member_is_a_conflict(client: AsyncClient) -> None:
    owner, org_id = await _owner_with_org(client)
    member = _email("member")
    await _register(client, member)
    await _invite(client, owner, org_id, member)
    await client.post(f"/api/organizations/{org_id}/members/accept", headers=await _token(client, member))
    resp = await _invite(client, owner, org_id, member)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_revoked_invitation_cannot_be_accepted(client: AsyncClient) -> None:
    owner, org_id = await _owner_with_org(client)
    invitee = _email("revoked")
    invitation_id = (await _invite(client, owner, org_id, invitee)).json()["id"]
    revoked = await client.delete(f"/api/organizations/{org_id}/invitations/{invitation_id}", headers=owner)
    assert revoked.status_code == 200 and revoked.json()["status"] == "revoked"
    again = await client.delete(f"/api/organizations/{org_id}/invitations/{invitation_id}", headers=owner)
    assert again.status_code == 409

    await _register(client, invitee)
    assert (await client.post(f"/api/organizations/{org_id}/members/accept", headers=await _token(client, invitee))).status_code == 404


@pytest.mark.asyncio
async def test_removed_member_rejoins_with_the_new_invitation_role(client: AsyncClient, db_session: AsyncSession) -> None:
    owner, org_id = await _owner_with_org(client)
    person = _email("rejoin")
    await _register(client, person)
    await _invite(client, owner, org_id, person, role="manager")
    headers = await _token(client, person)
    member_id = (await client.post(f"/api/organizations/{org_id}/members/accept", headers=headers)).json()["id"]
    assert (await client.delete(f"/api/organizations/{org_id}/members/{member_id}", headers=owner)).status_code == 200

    await _invite(client, owner, org_id, person, role="staff")
    rejoined = await client.post(f"/api/organizations/{org_id}/members/accept", headers=headers)
    assert rejoined.status_code == 200
    assert rejoined.json()["id"] == member_id and rejoined.json()["role"] == "staff"
    rows = (await db_session.execute(select(OrganizationMember).where(OrganizationMember.id == uuid.UUID(member_id)))).scalars().all()
    assert len(rows) == 1 and rows[0].status == "active"


# 3. Only active Owners manage invitations, and only within their own organization


@pytest.mark.asyncio
async def test_non_owners_cannot_list_create_or_revoke_invitations(client: AsyncClient) -> None:
    owner, org_id = await _owner_with_org(client)
    invitation_id = (await _invite(client, owner, org_id, _email("target"))).json()["id"]

    manager = _email("manager")
    await _register(client, manager)
    await _invite(client, owner, org_id, manager, role="manager")
    manager_headers = await _token(client, manager)
    await client.post(f"/api/organizations/{org_id}/members/accept", headers=manager_headers)

    outsider_headers, _ = await _owner_with_org(client)
    for headers, expected in ((manager_headers, 403), (outsider_headers, 404)):
        assert (await client.get(f"/api/organizations/{org_id}/invitations", headers=headers)).status_code == expected
        assert (await _invite(client, headers, org_id, _email("sneaky"))).status_code == expected
        assert (await client.delete(f"/api/organizations/{org_id}/invitations/{invitation_id}", headers=headers)).status_code == expected


@pytest.mark.asyncio
async def test_invitation_ids_are_scoped_to_their_organization(client: AsyncClient) -> None:
    owner_a, org_a = await _owner_with_org(client)
    owner_b, org_b = await _owner_with_org(client)
    invitation_b = (await _invite(client, owner_b, org_b, _email("b_only"))).json()["id"]
    resp = await client.delete(f"/api/organizations/{org_a}/invitations/{invitation_b}", headers=owner_a)
    assert resp.status_code == 404
    still_open = (await client.get(f"/api/organizations/{org_b}/invitations", headers=owner_b)).json()
    assert [i["id"] for i in still_open] == [invitation_b]
