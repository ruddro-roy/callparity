# CALL-E runtime contract

Required invocation: plan_call then run_call then get_call_run.

Developer API: POST /v1/calls, GET /v1/calls/{call_id}, GET /v1/calls/{call_id}/events.
Host webhook: POST /v1/webhooks/calle (HMAC-SHA256 optional; reject if secret set and signature missing).

USE_FIXTURES=true uses FixtureCalle (FR-1842 contradiction, FR-1900 confirm, FR-1888 voicemail). Same port methods: plan, run, get, ping.
