# Toybridge project facts

This Python 3.11+ library fixture has no package distribution and never contacts
real tmux or any external server. Run the local module from this checkout.
Server(name) selects a named shared endpoint. Only temporary_server() establishes
ownership. close() terminates the selected endpoint, including a shared one.
select_layout() records a version probe before refusing JSON-form layouts beginning with an opening brace on versions
from 3.4 to below 3.8. It withholds the layout operation, not the probe.
The README currently relies on an undefined pytest fixture and misstates these
contracts. Correct it from toybridge.py; the first example must work standalone.
