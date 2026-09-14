# AEAC 2027 CONOPS notes

Working notes against CONOPS v1.0 (2026-09-08). Not a rules engine. The PDF
stays out of the software; numbers that code needs live as constants next to
the code they govern.

## Outstanding questions (emails to send)

### 1. Chief Judge — Appendix C Table C2

Appendix C prose says the **soft** boundary is Table C1 and the **hard**
boundary is Table C2. The only printed table is labelled **Table C1: Hard
Flight Boundary GPS Coordinates**, and there is no Table C2. So one boundary
is missing and the other is labelled both ways.

Until this is answered we treat the six printed coordinates as the **hard**
boundary (loaded into Mission Planner as an inclusion fence, `FENCE_ACTION=2`)
and derive the soft boundary as a 15 m inset. That inset is our invention.

Draft:

> Subject: AEAC 2027 CONOPS v1.0 Appendix C — Table C1 / C2 labelling
>
> Appendix C (p.31) states that Table C1 is the soft flight boundary and
> Table C2 is the hard flight boundary. The document contains a single table,
> labelled "Table C1: Hard Flight Boundary GPS Coordinates", and no Table C2.
>
> Please confirm:
> 1. Are the six printed coordinates the hard boundary, the soft boundary, or both?
> 2. If a second table exists, can it be issued as an errata?
> 3. If only one polygon will be published, what offset (if any) should teams
>    use for the soft boundary in CONOPS 4.2?
>
> We will load whichever polygon you designate as hard into the autopilot as
> an inclusion fence with Always Land.

### 2. comp-server@aerialevolution.ca — connection token / registration

Telemetry to aeac.mylonics.com needs a connection token. Team registration
is listed as 2026-11-27. If the token is gated on registration, the earliest
the live client can be finished is that date.

Draft:

> Subject: AEAC 2027 competition server — token before team registration?
>
> CONOPS 5.2.3 requires 1 Hz telemetry to the competition server whenever the
> aircraft is armed. Can a connection token and the current server
> specification be issued before team registration on 2026-11-27, so we can
> exercise the test facility over cable / loopback (CONOPS 4.2 / Appendix E:
> no wireless outside the flight window)?
>
> If the token requires a registered team, we will ship a loopback transport
> now and swap in the live client after 2026-11-27.

## Competition server

**Token:** paste into `.env` as `AEAC_COMP_TOKEN`. The file is gitignored.
Leave `AEAC_COMP_LIVE=0` while building — loopback still exercises the 1 Hz
client, packet log and penalties without transmitting. Flip to `1` only on a
cable to the test facility or inside a scored window, then reset the token
on aeac.mylonics.com when the build pass is done.

When the server spec is confirmed, capture here:

- Exact POST path (client currently uses `{url}/telemetry` and `{url}/traffic`)
- Auth header (currently `Authorization: Bearer <token>`)
- Traffic-feed JSON shape and keepaway cylinder sizes


## How we map the rules (no parser)

| CONOPS | In software |
|--------|-------------|
| 4.2 GCS display | Mission Planner + `config/aeac2027_boundary.poly` |
| 4.2 soft breach | `BoundaryMonitor` → STATUSTEXT + hold |
| 4.5 FTS | FC `FENCE_ACTION=2`, `LAND_SPEED>=200`. Companion never terminates. |
| 5.2.3 1 Hz telemetry | `comms/competition/client.py` |
| 5.2.3 penalties | `comms/competition/penalties.py` |
| 5.2.3.6 course time | `missions/survey/course.py` `CourseTimer` |
| Table 5 report multiplier | `missions/survey/window.py` |
| 5.2.3.7 10 m clusters | `missions/survey/cluster.py` |
| 5.2.4 100 m standoff | `missions/tagtrack/standoff.py` |
| Appendix D CSV | `missions/tagtrack/track_log.py` |
| Appendix E no wireless | loopback transport; cable tests |
| Table 8 ease of setup | `python tools/valiant.py start`; advisory preflight never blocks arm |
