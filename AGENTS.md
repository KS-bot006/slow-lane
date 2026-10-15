# Rules for the coding agent

The agent copies this section to AGENTS.md in Phase 0.

### Scope and honesty

- Build only what this document describes. Do not add features, tools, notebooks, or folders.
- Use only the real NYC 311 data from the city API. Use synthetic data in unit tests only.
- Take every number in a document from a file in results/, from data/MANIFEST.json, or from run\_params.properties. Name the file next to the number.
- Report the results as computed. If the model does not beat a baseline, say so.
- Never change an expected value, a threshold, or a test to make a check pass.
- Do not say that a step passed unless you ran its command and read the output.

### Data and leakage

- Never use closed\_date, a resolution field, status, or due\_date as a feature.
- Split by time: history window, then train window, then test window.
- Compute the history features and set N from the history window only.
- Do not tune any setting on the test window.
- Download only the 11 columns of this document. Do not store addresses, names, phone numbers, or free text.

### Safety

- Run every command from the repository root.
- Do not use sudo. The human installs the system tools.
- Do not change or delete files outside the repository. Inside it, delete only files that the build made.
- Do not change shell profiles, global settings, or the system Java.
- Use the network only for data.cityofnewyork.us, repo1.maven.org, pypi.org, files.pythonhosted.org, github.com, and astral.sh. Do not upload data or results anywhere.
- Do not write the Socrata app token to a file, a log, or Git.

### Process

- Read this document at the start of every session. Read docs/BUILD\_LOG.md to find the current phase.
- Make one task for each task of the current phase. Mark each task done only after its check passes.
- Run each exit check yourself and read its output. Do not guess the result.
- Run each Scala job on the slice first. Run it on the full file only after the slice run passes.
- After each phase, add an entry to docs/BUILD\_LOG.md.
- Run scripts/ste\_check.py before every commit that changes text.
- End each phase with a short report: what passed and what is open.

### When to stop and ask the human

Stop and ask when one of these happens:

- An exit check still fails after two fixes.
- A decision in this document cannot be kept.
- ThresholdJob exits with code 2.
- The city API returns other column names or another format than this document states.
- A command fails because the computer has too little memory or disk space.
- A step needs a tool, a version, or a permission that this document does not list.

When you stop, state what failed, the command, the last 20 lines of its output, what you tried, and what you need.

