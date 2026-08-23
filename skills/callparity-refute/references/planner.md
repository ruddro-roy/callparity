# Planner (normative)

Input: ticket T, claims C_A, disclosure budget D.

1. Abstain if confidence is below 0.45.
2. Candidate observables per predicate:
   - pallet_staged: which dock, see pallet on jack, who waved you off.
   - driver_arrived: did you arrive, which gate.
   - seal_recorded: what seal number did you read (only if A actually recorded one).
3. Score information gain minus leakage. Discard leaks.
4. Greedy set-cover until coverage or UNTESTED.
5. Render goal. Max spoken words: 90s times 2.5 wps. Must include the critical entity id (e.g. PL-9F21).

Golden FR-1842 B-questions (demo): Which dock did you pull to? Did you see PL-9F21 on a jack? Who waved you off?
