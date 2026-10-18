"""The one shared role check (FR-11.2), following the permissions table in FRD chapter 2."""

from enum import StrEnum


class TenantType(StrEnum):
    COMPANY = "company"
    INVESTOR = "investor"
    # Reserved for M&A deal teams. No screens or flows use it (FR-2.9).
    DEAL_TEAM = "deal_team"


class Role(StrEnum):
    OWNER = "owner"
    CEO = "ceo"
    DEPARTMENT_LEAD = "department_lead"
    CONTRIBUTOR = "contributor"
    INVESTOR = "investor"


COMPANY_ROLES: frozenset[Role] = frozenset(
    {Role.OWNER, Role.CEO, Role.DEPARTMENT_LEAD, Role.CONTRIBUTOR}
)


class Department(StrEnum):
    """The five departments of the guidance (BR-4.2)."""

    FINANCE = "finance"
    SALES = "sales"
    DELIVERY = "delivery"
    PEOPLE = "people"
    PLAN = "plan"


class Action(StrEnum):
    VIEW_COMPANY = "view_company"
    VIEW_TEAM = "view_team"
    VIEW_INVESTORS = "view_investors"
    UPLOAD_FILES = "upload_files"
    EDIT_UPDATE = "edit_update"
    APPROVE_UPDATE = "approve_update"
    INVITE_USERS = "invite_users"
    INVITE_INVESTORS = "invite_investors"
    REMOVE_INVESTOR = "remove_investor"
    MANAGE_SETTINGS = "manage_settings"
    VIEW_AUDIT = "view_audit"
    COMMENT = "comment"
    DELETE_WORKSPACE = "delete_workspace"


ALL: frozenset[Role] = frozenset(Role)

# Who may attempt each action. Department scope and the approval setting are
# checked on top of this where the FRD table says "own departments" or "if granted".
MATRIX: dict[Action, frozenset[Role]] = {
    Action.VIEW_COMPANY: ALL,
    Action.VIEW_TEAM: COMPANY_ROLES,
    Action.VIEW_INVESTORS: ALL,
    Action.UPLOAD_FILES: COMPANY_ROLES,
    Action.EDIT_UPDATE: frozenset({Role.OWNER, Role.CEO, Role.DEPARTMENT_LEAD}),
    Action.APPROVE_UPDATE: frozenset({Role.OWNER, Role.CEO, Role.DEPARTMENT_LEAD}),
    Action.INVITE_USERS: frozenset({Role.OWNER, Role.CEO}),
    Action.INVITE_INVESTORS: frozenset({Role.OWNER, Role.CEO}),
    Action.REMOVE_INVESTOR: frozenset({Role.OWNER, Role.CEO}),
    Action.MANAGE_SETTINGS: frozenset({Role.OWNER, Role.CEO}),
    Action.VIEW_AUDIT: frozenset({Role.OWNER, Role.CEO}),
    Action.COMMENT: ALL,
    Action.DELETE_WORKSPACE: frozenset({Role.OWNER}),
}

DEFAULT_APPROVER_ROLES: tuple[Role, ...] = (Role.CEO,)


def allowed(role: Role, action: Action) -> bool:
    return role in MATRIX[action]


def can_approve(
    role: Role,
    user_id: str,
    approver_roles: list[str],
    approver_user_ids: list[str],
) -> bool:
    """Approval is a per-company permission, defaulting to the CEO (FR-2.7).

    The Owner can always approve. Others need their role or their own user
    named in the company's approval setting. Investors never approve.
    """
    if role == Role.OWNER:
        return True
    if role not in MATRIX[Action.APPROVE_UPDATE]:
        return False
    return role.value in approver_roles or user_id in approver_user_ids


def can_upload_to(role: Role, departments: list[str], department: Department) -> bool:
    if role in (Role.OWNER, Role.CEO):
        return True
    if role in (Role.DEPARTMENT_LEAD, Role.CONTRIBUTOR):
        return department.value in departments
    return False
