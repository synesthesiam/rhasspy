#!/usr/bin/env python3
import argparse
import calendar
import json
import locale
from pathlib import Path

def main():
    parser = argparse.ArgumentParser("generate-slots")
    parser.add_argument("profiles_dir")
    args = parser.parse_args()

    for profile_dir in Path(args.profiles_dir).glob("*"):
        if not profile_dir.is_dir():
            continue

        with open(profile_dir / "profile.json", "r") as profile_file:
            profile = json.load(profile_file)
            locale_name = profile["locale"] + ".UTF-8"
            locale.setlocale(locale.LC_ALL, locale_name)
            print(locale_name)

        slots_dir = profile_dir / "slots" / "rhasspy"
        slots_dir.mkdir(parents=True, exist_ok=True)

        # Day names
        (slots_dir / "days").write_text('\n'.join(calendar.day_name))

        # Month names
        (slots_dir / "months").write_text('\n'.join(filter(None, calendar.month_name)))
            

# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
