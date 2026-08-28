# CallParity v9 recut script

Target duration is 1:52. The cut opens on two live CALL-E call ids and the **Import live records** click. `RESTAGE_AND_RECALL` must be readable by 0:12 and stay visible through 0:20.

## Keep the story locked

- Start on the running workbench with `FR-1842` selected.
- Show both live call ids before the click.
- Click **Import live records** before any use of **Preview (0 calls)** or **Run parity**.
- Keep `FR-1900` and `FR-1888` out of this cut.
- Use the existing leak-check and diner footage only after the live import resolves.
- Do not show a phone, an email address, a face, a country flag, a secret, or invented transcript text.
- Keep v8 public until Ruddro approves `callparity-watch-me-v9.mp4`.
- Do not upload v9, edit Devpost, or merge a pull request during this recut.

The two live records are:

- Warehouse. `call_vzro922bOACJjf19ML7vQQ`
- Driver. `call_2kxhpDvknUJ444kKfJLsyA`

The driver call ended early. Its structured record still denies that the pallet was present.

## Capture the workbench

1. Run `docker compose up -d --build`.
2. Open `http://localhost:3000` in a 1920 by 1080 viewport at 100 percent browser zoom.
3. Load a clean `FR-1842` state. Keep the Live import bar, both call ids, and the button in the opening frame.
4. Capture one uninterrupted pass. Click **Import live records** once. Do not click **Preview (0 calls)** or **Run parity** first.
5. If import returns 409, use the existing CALL-E read credentials on the capture machine. Keep the credentials in the shell. Do not write them to a file.
6. Reject any take that does not show `RESTAGE_AND_RECALL` by 0:12.
7. Cover the masked party phone fields with solid blocks for every workbench frame. A partial mask still reads as a phone.

Import reads the two stored call records. It does not dial.
The amber fixture banner may stay in frame. The Import control still uses the live-record path.

## Shot list

| Time | Picture | Sound |
| --- | --- | --- |
| 0:00 to 0:04 | Cold open on a tight workbench crop. Keep `FR-1842`, both call ids, and **Import live records** readable. Move the cursor beneath the warehouse id, then the driver id. | Start VO 1. No title card. |
| 0:04 to 0:08 | Click **Import live records** once. Keep the cursor still after the click. | Finish VO 1. Keep the real click. |
| 0:08 to 0:12 | Hold the same pass as the graph fills. Punch in on `RESTAGE_AND_RECALL` as soon as it appears. | Leave a short pause. Use one quiet interface hit when the card resolves. |
| 0:12 to 0:20 | Keep the action card in frame. Move attention to `pallet_staged CONTRADICTED`, then `driver_arrived CONFIRMED`. | VO 2. |
| 0:20 to 0:38 | Use the warehouse and driver record cards as B-roll. Keep both call ids readable once more. Do not show transcript quotes. | VO 3. |
| 0:38 to 0:52 | Return to the Live import bar. Add two plain lines of body text. Use `GET only` and `No new dial`. | VO 4. |
| 0:52 to 1:08 | Fill the frame with the claim graph. Land on the untested seal edge after the two resolved edges. | Finish VO 4. |
| 1:08 to 1:24 | Insert the existing leak-check B-roll. Show the struck question that contains dock three and 6:40. Keep it readable long enough to scan once. | VO 5. |
| 1:24 to 1:34 | Return to the workbench action card. Keep the `human-owned` label and `RESTAGE_AND_RECALL` in the same crop. | VO 6. |
| 1:34 to 1:44 | Use a short diner proof sting. Show only `call_Sv3d5Dt3jj0YabV9IJZh7g`, the human result, and the closing time of 11. Do not recreate the call dialogue. | VO 7. |
| 1:44 to 1:52 | Close on the two `FR-1842` call ids, the restage card, and the official ClaimKill list artifact. Keep the workbench visible behind the lockup. | VO 8. End on the card without a logo animation. |

The closing lockup must show this link:

`https://github.com/CALLE-AI/awesome-phone-call-agents/pull/220`

## Voice-over master

Use Adam with a mild American read. Keep the delivery matter-of-fact. Leave room for the import click and the card reveal.

**VO 1**

Two live CALL-E calls. Same pallet. They disagree. Import the records.

**VO 2**

The graph marks pallet staged contradicted. Driver arrived is confirmed.

**VO 3**

This insulin delay costs eighteen thousand dollars an hour. The warehouse record says PL-9F21 was staged at dock three. The driver record says dock three was empty.

**VO 4**

Import reads both records with GET. It places no new call. The seal stays untested.

**VO 5**

The refute plan removes the question that would have handed the driver dock three and six forty. The driver gets a clean test instead of the warehouse's answer.

**VO 6**

One human-owned action. Restage the pallet and recall the driver.

**VO 7**

Same port already reached a person at a diner. They said they close at 11. That call is proof. It is not the product.

**VO 8**

ClaimKill is on the list. The graph is the product. Two call ids. One card.

## Picture and sound

- Deliver 1920 by 1080, 25 fps, progressive, and Rec.709.
- Keep every title at 72 px and every body line at 42 px.
- Keep text inside the 10 percent title-safe area.
- Use H.264 High at CRF 16 or 17 with `+faststart`.
- Deliver 48 kHz stereo at minus 14 LUFS integrated and no higher than minus 1.0 dBTP.
- Use no music bed. The click and the card resolve carry the opening.
- Keep the voice provider uncredited on tape and in public filenames.
- Build the cut in one ffmpeg filter graph. Do not use the concat demuxer.
- Do not restart the workbench inside the cut.

## Quality gate

- The duration is under 2:59. The target is 1:52.
- Both live call ids are readable before 0:08.
- **Import live records** is the first click.
- `RESTAGE_AND_RECALL` is readable by 0:12.
- `pallet_staged CONTRADICTED` and `driver_arrived CONFIRMED` are readable by 0:20.
- The tape contains no phone, email address, face, country flag, secret, provider credit, or invented quote.
- The tape makes no percentage win claim and promises no score or prize.
- `callparity-commercial-v9.mp4` plays from start to finish.
- The player-safe remux `callparity-watch-me-v9.mp4` plays from start to finish.
- `QC-v9.txt` records the duration, frame size, frame rate, color space, loudness, true peak, and content checks.
- Nothing becomes public before Ruddro watches the watch-me file and says ship.

## Repository fact

`./.venv/bin/pytest --collect-only -q` reports 166 tests in this tree. Keep that fact off camera. The live Import path and its result are the proof.

## Encode status

Encoding is blocked in this workspace because `/workspace/callparity/demo/commercial/` is absent. The operator box must create `assemble_v9.sh`, encode both v9 files, and write `QC-v9.txt` beside the v8 masters.
