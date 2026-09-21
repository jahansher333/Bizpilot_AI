"""PostgreSQL integration tests for authentication persistence and constraints."""

import uuid
from datetime import datetime, timezone, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.enums import UserStatus
from app.modules.auth.models import (
    PasswordResetToken,
    RefreshToken,
    User,
    UserCredential,
    generate_uuid,
)
from app.modules.auth.repository import AuthRepository


@pytest.mark.asyncio
async def test_persist_and_retrieve_user(db_session: AsyncSession) -> None:
    """Verify user persistence and retrieval by ID and normalized email."""
    repo = AuthRepository(db_session)
    email = f"user_{uuid.uuid4().hex[:8]}@example.com"

    created = await repo.create_user(
        email_normalized=email,
        display_name="Test User",
        status=UserStatus.ACTIVE,
    )

    assert created.id is not None
    assert created.email_normalized == email
    assert created.display_name == "Test User"
    assert created.status == "active"

    # Query by ID
    by_id = await repo.get_user_by_id(created.id)
    assert by_id is not None
    assert by_id.id == created.id
    assert by_id.email_normalized == email

    # Query by email
    by_email = await repo.get_user_by_email(email)
    assert by_email is not None
    assert by_email.id == created.id


@pytest.mark.asyncio
async def test_unique_email_normalized_constraint(db_session: AsyncSession) -> None:
    """Verify database-level unique constraint on users.email_normalized."""
    repo = AuthRepository(db_session)
    email = f"duplicate_{uuid.uuid4().hex[:8]}@example.com"

    await repo.create_user(email_normalized=email, display_name="User One")

    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await repo.create_user(email_normalized=email, display_name="User Two")


@pytest.mark.asyncio
async def test_user_status_check_constraint(db_session: AsyncSession) -> None:
    """Verify database-level check constraint on users.status (ck_users_status)."""
    repo = AuthRepository(db_session)
    email = f"status_test_{uuid.uuid4().hex[:8]}@example.com"

    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            user = User(
                email_normalized=email,
                display_name="Invalid Status User",
                status="banned",  # Violates ck_users_status
            )
            db_session.add(user)
            await db_session.flush()


@pytest.mark.asyncio
async def test_persist_and_retrieve_credential(db_session: AsyncSession) -> None:
    """Verify credential persistence and retrieval by user_id."""
    repo = AuthRepository(db_session)
    user = await repo.create_user(
        email_normalized=f"cred_{uuid.uuid4().hex[:8]}@example.com",
        display_name="Cred User",
    )

    fake_hash = "$argon2id$v=19$m=65536,t=3,p=4$dummyhashforauth001persistence"
    cred = await repo.create_credential(
        user_id=user.id,
        password_hash=fake_hash,
    )

    assert cred.id is not None
    assert cred.user_id == user.id
    assert cred.password_hash == fake_hash

    fetched = await repo.get_credential_by_user_id(user.id)
    assert fetched is not None
    assert fetched.id == cred.id
    assert fetched.password_hash == fake_hash


@pytest.mark.asyncio
async def test_unique_user_credential_constraint(db_session: AsyncSession) -> None:
    """Verify unique constraint on user_credentials.user_id (1:1 relation)."""
    repo = AuthRepository(db_session)
    user = await repo.create_user(
        email_normalized=f"cred_uniq_{uuid.uuid4().hex[:8]}@example.com",
        display_name="Cred Unique User",
    )

    await repo.create_credential(user_id=user.id, password_hash="hash1")

    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await repo.create_credential(user_id=user.id, password_hash="hash2")


@pytest.mark.asyncio
async def test_persist_and_retrieve_refresh_token(db_session: AsyncSession) -> None:
    """Verify refresh token persistence with family ID and expiry."""
    repo = AuthRepository(db_session)
    user = await repo.create_user(
        email_normalized=f"token_{uuid.uuid4().hex[:8]}@example.com",
        display_name="Token User",
    )

    token_hash = uuid.uuid4().hex + uuid.uuid4().hex  # 64 chars
    family_id = generate_uuid()
    expires_at = datetime.now(timezone.utc) + timedelta(days=30)

    rt = await repo.create_refresh_token(
        user_id=user.id,
        token_hash=token_hash,
        token_family_id=family_id,
        expires_at=expires_at,
    )

    assert rt.id is not None
    assert rt.user_id == user.id
    assert rt.token_hash == token_hash
    assert rt.token_family_id == family_id
    assert rt.revoked_at is None

    fetched = await repo.get_refresh_token_by_hash(token_hash)
    assert fetched is not None
    assert fetched.id == rt.id
    assert fetched.user_id == user.id


@pytest.mark.asyncio
async def test_unique_refresh_token_hash_constraint(db_session: AsyncSession) -> None:
    """Verify unique constraint on refresh_tokens.token_hash."""
    repo = AuthRepository(db_session)
    user = await repo.create_user(
        email_normalized=f"token_dup_{uuid.uuid4().hex[:8]}@example.com",
        display_name="Token Dup User",
    )

    token_hash = "c" * 64
    family_id = generate_uuid()
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)

    await repo.create_refresh_token(
        user_id=user.id,
        token_hash=token_hash,
        token_family_id=family_id,
        expires_at=expires_at,
    )

    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await repo.create_refresh_token(
                user_id=user.id,
                token_hash=token_hash,
                token_family_id=generate_uuid(),
                expires_at=expires_at,
            )


@pytest.mark.asyncio
async def test_persist_and_retrieve_password_reset_token(db_session: AsyncSession) -> None:
    """Verify password reset token persistence and retrieval."""
    repo = AuthRepository(db_session)
    user = await repo.create_user(
        email_normalized=f"reset_{uuid.uuid4().hex[:8]}@example.com",
        display_name="Reset User",
    )

    token_hash = "d" * 64
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

    prt = await repo.create_password_reset_token(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
    )

    assert prt.id is not None
    assert prt.user_id == user.id
    assert prt.token_hash == token_hash
    assert prt.consumed_at is None

    fetched = await repo.get_password_reset_token_by_hash(token_hash)
    assert fetched is not None
    assert fetched.id == prt.id
    assert fetched.user_id == user.id


@pytest.mark.asyncio
async def test_unique_password_reset_token_hash_constraint(db_session: AsyncSession) -> None:
    """Verify unique constraint on password_reset_tokens.token_hash."""
    repo = AuthRepository(db_session)
    user = await repo.create_user(
        email_normalized=f"reset_dup_{uuid.uuid4().hex[:8]}@example.com",
        display_name="Reset Dup User",
    )

    token_hash = "e" * 64
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

    await repo.create_password_reset_token(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
    )

    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await repo.create_password_reset_token(
                user_id=user.id,
                token_hash=token_hash,
                expires_at=expires_at,
            )


# -----------------------------------------------------------------------------
# Restrictive Foreign Key Delete Tests (Founder Decision Option A)
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_restrictive_fk_rejects_user_deletion_when_credentials_exist(
    db_session: AsyncSession,
) -> None:
    """Verify that deleting a parent user is rejected when user_credentials exist.

    Confirms Option A: PostgreSQL restrictive/default FK behavior without CASCADE.
    """
    repo = AuthRepository(db_session)
    user = await repo.create_user(
        email_normalized=f"fk_cred_{uuid.uuid4().hex[:8]}@example.com",
        display_name="FK Cred User",
    )
    cred = await repo.create_credential(
        user_id=user.id,
        password_hash="test-hash-fk",
    )

    # Attempt to hard delete the parent user: must fail with IntegrityError
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.delete(user)
            await db_session.flush()

    # Explicit cleanup: deleting child first then parent succeeds
    await db_session.delete(cred)
    await db_session.flush()
    await db_session.delete(user)
    await db_session.flush()

    # Verify user is gone
    assert await repo.get_user_by_id(user.id) is None


@pytest.mark.asyncio
async def test_restrictive_fk_rejects_user_deletion_when_refresh_tokens_exist(
    db_session: AsyncSession,
) -> None:
    """Verify that deleting a parent user is rejected when refresh_tokens exist.

    Confirms Option A: PostgreSQL restrictive/default FK behavior without CASCADE.
    """
    repo = AuthRepository(db_session)
    user = await repo.create_user(
        email_normalized=f"fk_rt_{uuid.uuid4().hex[:8]}@example.com",
        display_name="FK RT User",
    )
    token = await repo.create_refresh_token(
        user_id=user.id,
        token_hash="f" * 64,
        token_family_id=generate_uuid(),
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )

    # Attempt to hard delete parent user: must fail
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.delete(user)
            await db_session.flush()

    # Explicit cleanup
    await db_session.delete(token)
    await db_session.flush()
    await db_session.delete(user)
    await db_session.flush()

    assert await repo.get_user_by_id(user.id) is None


@pytest.mark.asyncio
async def test_restrictive_fk_rejects_user_deletion_when_reset_tokens_exist(
    db_session: AsyncSession,
) -> None:
    """Verify that deleting a parent user is rejected when password_reset_tokens exist.

    Confirms Option A: PostgreSQL restrictive/default FK behavior without CASCADE.
    """
    repo = AuthRepository(db_session)
    user = await repo.create_user(
        email_normalized=f"fk_prt_{uuid.uuid4().hex[:8]}@example.com",
        display_name="FK PRT User",
    )
    token = await repo.create_password_reset_token(
        user_id=user.id,
        token_hash="1" * 64,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )

    # Attempt to hard delete parent user: must fail
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.delete(user)
            await db_session.flush()

    # Explicit cleanup
    await db_session.delete(token)
    await db_session.flush()
    await db_session.delete(user)
    await db_session.flush()

    assert await repo.get_user_by_id(user.id) is None


@pytest.mark.asyncio
async def test_repository_transaction_rollback(db_session: AsyncSession) -> None:
    """Verify uncommitted transactions roll back cleanly and leave no trace."""
    repo = AuthRepository(db_session)
    email = f"rollback_{uuid.uuid4().hex[:8]}@example.com"

    with pytest.raises(RuntimeError, match="Intentional rollback"):
        async with db_session.begin_nested():
            user = await repo.create_user(email_normalized=email, display_name="Rollback User")
            user_id = user.id
            # Explicit rollback via nested transaction exit
            raise RuntimeError("Intentional rollback")

    # After rollback, record must not exist
    user_after = await repo.get_user_by_id(user_id)
    assert user_after is None
    by_email = await repo.get_user_by_email(email)
    assert by_email is None


@pytest.mark.asyncio
async def test_repository_update_password_hash(db_session: AsyncSession) -> None:
    """Verify updating credential password hash in PostgreSQL."""
    repo = AuthRepository(db_session)
    user = await repo.create_user(
        email_normalized=f"update_hash_{uuid.uuid4().hex[:8]}@example.com",
        display_name="Update Hash User",
    )
    initial_hash = "$argon2id$v=19$m=8192,t=1,p=1$initialhashvalue1234"
    new_hash = "$argon2id$v=19$m=16384,t=2,p=2$updatedhashvalue5678"

    cred = await repo.create_credential(user.id, initial_hash)
    original_updated_at = cred.password_updated_at

    # Update hash
    updated = await repo.update_password_hash(user.id, new_hash)
    assert updated is not None
    assert updated.password_hash == new_hash
    assert updated.password_updated_at is not None

    # Verify query returns updated hash
    queried = await repo.get_credential_by_user_id(user.id)
    assert queried is not None
    assert queried.password_hash == new_hash

    # Updating non-existent user returns None
    assert await repo.update_password_hash(uuid.uuid4(), new_hash) is None
