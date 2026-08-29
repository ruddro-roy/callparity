# YouTube description for the CallParity demo video

Paste everything below the line into the YouTube description field.

---

CallParity runs a second phone call as a test of the first. It takes a
two-sided ops ticket, turns Party A's statements into falsifiable claims,
and asks Party B only observable questions. A structural leak check drops
any question that would reveal what A said. Both calls merge into a graph
that confirms or contradicts each claim, and one action card comes out:
restage and recall, release the truck, or hold for a human. Voicemail and
silence never count as confirmation.

This video opens with two real recorded CALL-E calls on ticket FR-1842, a
refrigerated insulin pallet with an $18,000-per-hour SLA. The warehouse says
pallet PL-9F21 is staged at Dock 3. The driver says Dock 3 was empty. The
import merges both records without placing a call and the card says restage
and recall. The walkthrough then shows the zero-call preview, the leak check
dropping the naive recap question, and the control tickets for agreement and
voicemail. The production segment kills the API mid-run with kill -9,
shows the orphaned job converge on reboot, meters an unauthenticated flood
into 429s, and scrapes Prometheus metrics. The repo carries 165 offline
tests.

Chapters:
0:00 Import of two real recorded calls
0:20 Product walkthrough
1:20 Production proof
2:20 Impact and adoption

Repo: https://github.com/ruddro-roy/callparity
Refutation planner merged upstream: https://github.com/CALLE-AI/awesome-phone-call-agents/pull/220

This video is an entry in the CALL-E hackathon on Devpost.

#devpost #hackathon #logistics
