import sys
from pathlib import Path

# Let tests import sql_inserts directly, matching how the other pipeline scripts are run.
sys.path.insert(0, str(Path(__file__).parent))
