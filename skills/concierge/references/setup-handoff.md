# Setup handoff

Switch to setup behavior when any of these are true:

- the GT root does not exist or is not initialized
- the town exists but has no rigs for the work the user described
- the user wants to add repos and has not given the URLs yet
- the Obsidian vault or project folders do not exist
- RTK is missing or not initialized
- Graphify is missing in more than one target rig
- the user explicitly asks for setup or refresh

When this happens:

1. Explain briefly that you are doing setup first.
2. Initialize GT with `gt install <root>` if needed.
3. Ask whether the user wants to add rigs now if the needed repos are not in town yet.
4. Create or repair the vault structure.
5. Install or initialize RTK.
6. Install or refresh Graphify for the target rigs.
7. Return to the user's original goal and continue with intake and dispatch.

If the user invoked `/setup-tooling` separately, let that skill own the broad setup pass. Otherwise do only the minimum setup needed to keep momentum.
