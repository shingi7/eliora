# EliOra Tech Solutions

This repository contains the public Quarto marketing site and a separate private operations package. The local-first outreach tool lives in [`outreach/README.md`](outreach/README.md). It is not part of the Quarto build, is not linked from the public website, and keeps its database, cache, logs, OS-managed mailbox secret, and exports outside the repository.

The marketing site remains the source of truth for public positioning. Run the existing site checks with `python3 scripts/check_site.py` after a Quarto render. The outreach package uses Namecheap Private Email SMTP/IMAP and keeps its mailbox password only in the OS credential store.

For private operations, run `./outreachctl setup` for concise first-run configuration and `./outreachctl config show` for a safe status summary. Private postal data and credentials stay outside this repository.
