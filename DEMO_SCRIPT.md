# CallParity v9 demo script

This cut opens on the product result. A stranger sees two CALL-E call IDs, clicks
**Import live records**, and reaches `RESTAGE_AND_RECALL` within 20 seconds.

Keep v8 public at
[YouTube](https://www.youtube.com/watch?v=mLR6RTOi64c). Do not upload v9 or edit
the submission page until Ruddro watches the new master and says ship. Do not
merge this branch.

The fixed scenario is ticket `FR-1842`. Pallet `PL-9F21` carries insulin, and
the delay costs $18,000 per hour. The warehouse record says that the pallet was
staged at dock 3 at 06:40. The driver record says that the driver arrived, found
dock 3 empty, and did not see the pallet. The driver bot ended early, but the
denial stands.

Import reads only the two stored CALL-E records with GET requests. It never
dials. Re-import returns the stored job. Do not add transcript quotes or invent
spoken words.

## Prepare the take

1. Run `docker compose up -d --build` from the CallParity repository.
2. Open `http://localhost:3000` at 100 percent browser zoom.
3. Capture one continuous 1920x1080 pass at 25 fps.
4. Select `FR-1842` before recording.
5. Keep the Live import bar and both call IDs readable.
6. Keep `USE_FIXTURES=true`. The amber fixture banner may remain.
7. Rehearse the import on the operator box. If the workbench returns 409, use
   the existing machine secret outside the recording. Never put the secret in
   the repository, the video, or an editor command.
8. Do not dial, buy a number, call a person, or set `from_number`.
9. Crop out the party contact row or cover it with an opaque overlay. The
   workbench masks those values, but the final tape must show no phone fragments.
10. Keep browser tools, notifications, email, faces, and country flags out of
    frame.

The final cut should run from 1:40 to 2:10. It must remain under 2:59.

## Follow this shot list

| Time | Picture | Voice |
| --- | --- | --- |
| 0:00 to 0:04 | Open on the running `FR-1842` workbench. Keep the Live import bar, `call_vzro922bOACJjf19ML7vQQ`, and `call_2kxhpDvknUJ444kKfJLsyA` sharp. Put the cursor over **Import live records**. Click by 0:04. | Start the hook. |
| 0:04 to 0:12 | Hold the continuous pass while the graph fills. Move the cursor to the action card as soon as it reads `RESTAGE_AND_RECALL`. | Finish the hook. Start the body. |
| 0:12 to 0:20 | Point to `pallet_staged CONTRADICTED`, then `driver_arrived CONFIRMED`. Return to the action card. Keep both call IDs in frame. | Continue the body. |
| 0:20 to 0:35 | Hold on `seal_recorded UNTESTED` and the human-owned action card. Keep the frame still for two seconds. | Finish the body. |
| 0:35 to 0:58 | Click **Preview (0 calls)** only now. Frame **Dropped by leak check** and the struck question that contains dock 3 and 06:40. | Read the leak-check line. |
| 0:58 to 1:13 | Select **FR-1900 control** and click **Run parity**. Hold when the card reads `RELEASE_TRUCK`. | Start the controls line. |
| 1:13 to 1:28 | Select **FR-1888 voicemail** and click **Run parity**. Hold when the card reads `HOLD_FOR_HUMAN`. | Finish the controls line. |
| 1:28 to 1:42 | Return to `FR-1842`. Hold on the two call IDs, the contradiction edges, and `RESTAGE_AND_RECALL`. | Pause, then start the closer. |
| 1:42 to 1:52 | Add a 42px lower third for [CALLE-AI/awesome-phone-call-agents PR 220](https://github.com/CALLE-AI/awesome-phone-call-agents/pull/220). Keep the call IDs and action card readable behind it. | Finish the closer. Hold the last frame for two seconds. |

Fail the cut if `RESTAGE_AND_RECALL` is not readable by 0:20. Do not use
**Preview (0 calls)** or **Run parity** before the Import click.

The warehouse, driver, graph, and restage cards from v8 may appear as B-roll
after 0:20. They must not replace the live Import click. Do not restart the
workbench during the cut.

## Record this voiceover

Use an uncredited mild American voice. Leave short gaps so the cursor can land
on each result.

### Hook

"Two live CALL-E calls. Same pallet. They disagree. Import the records."

### Body

"Warehouse said the pallet was on dock three. The driver said dock three was
empty. Import is GET only. No new dial. The graph marks pallet staged
contradicted. Driver arrived is confirmed. Seal is untested. One human-owned
action. Restage and recall."

### Leak check

"CallParity refuses this question. It would hand dock three and six forty to
the driver. The leak check strikes it before any call."

### Controls

"Agreement and silence take different paths. FR nineteen hundred releases the
truck. FR eighteen eighty-eight reached voicemail, so CallParity holds for a
human. Silence never counts as yes."

### Closer

"ClaimKill is on the list. The graph is the product. Two call ids. One card."

Do not voice the original diner transcript. If the controls push the cut past
2:10, remove both controls together. Replace them with no more than eight
seconds of the diner result card after the restage card. The card may show
`call_Sv3d5Dt3jj0YabV9IJZh7g`, `reached=human`, and `closing_time=11`.

## Finish the picture and sound

Use one ffmpeg filter graph. Do not use a concat demuxer.

Keep titles at 72px and body copy at 42px. Keep every title inside a 10 percent
safe margin. Encode progressive Rec.709 video as H.264 High with CRF 16 or 17.
Add `faststart`. Make `callparity-watch-me-v9.mp4` a player-safe remux of the
commercial master.

Deliver 48 kHz stereo audio at -14 LUFS. Keep the true peak at or below
-1.0 dBTP. Use no music unless the bed stays below -24 LUFS.

The current tree collects 166 tests. Regenerate that count with
`.venv/bin/pytest --collect-only -q`. If the tape includes test output, record
a fresh `.venv/bin/pytest -q` run and show its actual result.

## Check the private master

- Confirm that `callparity-commercial-v9.mp4` and
  `callparity-watch-me-v9.mp4` play without a break.
- Confirm 1920x1080 progressive video at 25 fps.
- Confirm Rec.709 color and H.264 High.
- Confirm -14 LUFS loudness, -1.0 dBTP true peak, and 48 kHz stereo audio.
- Confirm that both live call IDs, the Import click, and
  `RESTAGE_AND_RECALL` appear within 20 seconds.
- Confirm that the tape contains no phone fragment, email address, face,
  country flag, secret, or voice-vendor credit.
- Record the checks in `QC-v9.txt` using the same shape as `QC-v8.txt`.
- Keep both v9 files private until Ruddro approves the watch-me file.

`/workspace/callparity/demo/commercial/` is absent in this workspace, so the
v9 encode, `assemble_v9.sh`, `QC-v9.txt`, and both MP4 files must be produced
on the operator box that holds the v8 masters.
