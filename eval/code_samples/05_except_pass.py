"""Expected: nesting_depth
Config parsing that swallows every error."""


def parse_settings(lines):
    settings = {}
    for line in lines:
        try:
            if line and not line.startswith("#"):
                if "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    if value.strip().isdigit():
                        settings[key] = int(value)
                    elif value.strip().lower() in ("true", "false"):
                        settings[key] = value.strip().lower() == "true"
                    else:
                        settings[key] = value.strip()
        except ValueError:
            pass
        except AttributeError:
            pass
    return settings
