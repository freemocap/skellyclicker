# Citation checks

Record architectural source references in root references.bib with stable keys, explicit URL, access date, review scope and supported claim. Cite keys as [@key] beside supported source comments or documentation. Local repository observations should identify the inspected revision; do not imply runtime verification from source inspection.

Run `backend/.venv/Scripts/python.exe -B tools/check_references.py` after citation changes. The check verifies required fields and resolves cited keys in the current native source and architecture documentation. Archived files under old are historical and are not rewritten.
