"""Expected: nesting_depth
Trap: strict d["key"] lookups (raise KeyError) mixed with a caught KeyError. Easy to
"simplify" with .get() and silently change which inputs fail."""


def user_emails(users, domain):
    emails = []
    for user in users:
        if user["active"]:
            try:
                contact = user["contact"]
                if "email" in contact:
                    if contact["email"].endswith(domain):
                        emails.append(contact["email"].lower())
            except KeyError:
                pass
    return emails
