"""Clear errors for missing inputs, so a wrong path doesn't end in a traceback."""
import os
import sys


def spt_runtime(spt):
    """spt is an SPT_Runtime folder with WTT-ContentBackport installed."""
    if not os.path.isfile(os.path.join(spt, "SPT_Data", "database", "templates", "quests.json")):
        sys.exit(f"SPT not found at {spt} (no SPT_Data/database/templates/quests.json).\n"
                 "Point it at the SPT_Runtime folder of an SPT 4.1 install.")
    if not os.path.isdir(os.path.join(spt, "user", "mods", "WTT-ContentBackport", "db")):
        sys.exit(f"WTT-ContentBackport isn't installed in {spt} (no user/mods/WTT-ContentBackport/db).\n"
                 "The build needs it for the 1.0 items quests use.")


def spt_database(db):
    """db is SPT_Runtime/SPT_Data/database."""
    if not os.path.isfile(os.path.join(db, "templates", "quests.json")):
        sys.exit(f"SPT database not found at {db} (no templates/quests.json).\n"
                 "Point it at SPT_Runtime/SPT_Data/database of an SPT 4.1 install.")


def data_files(data, *names):
    """The tarkov.dev downloads tools/fetch_data.py makes."""
    missing = [n for n in names if not os.path.isfile(os.path.join(data, n))]
    if missing:
        sys.exit(f"missing {', '.join(missing)} in {data}. Run tools/fetch_data.py first.")
