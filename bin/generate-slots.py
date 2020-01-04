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

            slots_dir = profile_dir / "slots" / "rhasspy"
            slots_dir.mkdir(parents=True, exist_ok=True)

            # Day names
            with open(slots_dir / "days", "w") as days_file:
                for day_num in range(7):
                    print(calendar.day_name[day_num], file=days_file)

            # Month names
            with open(slots_dir / "months", "w") as month_file:
                for month_num in range(1, 13):
                    print(calendar.month_name[month_num], file=month_file)

            print(locale_name)

# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
