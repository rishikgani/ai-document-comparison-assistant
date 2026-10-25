from collections.abc import Mapping


def _user_claims(user) -> Mapping:
    if isinstance(user, Mapping):
        return user

    to_dict = getattr(user, "to_dict", None)
    if callable(to_dict):
        return to_dict()

    return {}


def get_account_identity(user) -> dict[str, str]:
    """Extract the minimal account identity used by the app."""

    claims = _user_claims(user)
    email = (
        claims.get("email")
        or claims.get("preferred_username")
        or claims.get("upn")
    )
    if not isinstance(email, str) or not email.strip():
        raise ValueError(
            "Your identity provider did not provide an email or username. "
            "Check that the email scope is enabled for this sign-in."
        )

    email = email.strip().lower()
    display_name = claims.get("name")
    if not isinstance(display_name, str) or not display_name.strip():
        display_name = email

    issuer = claims.get("iss")
    issuer = issuer.lower() if isinstance(issuer, str) else ""
    if "accounts.google.com" in issuer:
        provider = "Google"
    elif any(
        microsoft_issuer in issuer
        for microsoft_issuer in (
            "login.microsoftonline.com",
            "login.live.com",
            "sts.windows.net",
        )
    ):
        provider = "Microsoft"
    else:
        provider = "Unknown"

    return {
        "email": email,
        "display_name": display_name.strip(),
        "provider": provider,
    }
