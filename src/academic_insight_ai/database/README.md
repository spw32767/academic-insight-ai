# Database module (future)

This module now supports read-only article input from MySQL/MariaDB.

Current flow:
1. Read source articles from an existing MySQL/MariaDB database.
2. Run selected AI task and model.
3. Save results to output JSON files.

Next planned steps:
1. Persist raw and validated results into AI result logs.
2. Optionally write back selected final category.

Current version does not write back to the database yet.
