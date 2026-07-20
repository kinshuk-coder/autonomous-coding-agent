def normalize_email(email: str) -> str:
    email = email.strip()
    if "@" not in email:
        return email

    local, domain = email.rsplit("@", 1)
    return f"{local.lower()}@{domain}"
