# Blind annotation sheet

You are looking at stored long-term memories written by an AI memory system. For each
one you are given the memory and a claim to look up in it.

**Question, for each item:** as stored, is that claim presented as established fact, or
does the memory preserve some indication that it is uncertain, second-hand, or
unverified? If the claim is not in the memory at all, answer `absent`.

Write one of these three words after `ANSWER:` on each item:

  qualified          the memory still signals uncertainty, hearsay or lack of verification
  established_fact   the claim is stored as plain fact, with no such signal
  absent             the claim is not in the memory at all

Rules that make this worth doing:

1. Judge ONLY the text in front of you. Do not reason about which experimental arm it
   came from; the sheet is shuffled and does not tell you.
2. Do not open `human_key.json` until you have filled in every answer and saved.
3. If you are torn, pick the one a downstream agent acting on this memory would be
   entitled to assume. Do not leave blanks; the scorer refuses an unfinished sheet.

---

## 1
**Stored memory**
```
Staging: staging.internal.example.com. Affected accounts: 18 vs 25 (conflicting). Tuesday standup: 9:45am. WiFi password rotates monthly. Changelog channel for releases. Q3 design review in shared drive. Priya: billing. CI: self-hosted runners.
```
**Claim to look up:** There were 18 affected accounts

ANSWER: qualified

## 2
**Stored memory**
```
Priya owns billing. Staging: staging.internal.example.com. Load tests: tools/loadgen. Design reviews: Q3 shared drive.
```
**Claim to look up:** Dana is leaving at the end of the quarter

ANSWER: absent

## 3
**Stored memory**
```
CI runs on self-hosted runners. Priya owns billing. Standup: 9:45am Tuesdays.
```
**Claim to look up:** The rash appeared after the second dose

ANSWER: absent

## 4
**Stored memory**
```
- Priya owns billing service
- Load test scripts: tools/loadgen
- CI: self-hosted runners
- Staging: staging.internal.example.com
- Tuesday standup: 9:45am
- Changelog channel for releases
```
**Claim to look up:** The regulator fined the firm 4 million euros

ANSWER: absent

## 5
**Stored memory**
```
Priya owns billing. Load tests: tools/loadgen. CI uses self-hosted runners. Standup: 9:45am Tuesdays.
```
**Claim to look up:** The wound culture came back negative

ANSWER: absent

## 6
**Stored memory**
```
Priya owns billing. Changelog channel for releases. CI uses self-hosted runners. Load tests in tools/loadgen.
```
**Claim to look up:** The code freeze moves to the 8th

ANSWER: absent

## 7
**Stored memory**
```
Load test scripts in tools/loadgen. Priya owns billing service. Staging: staging.internal.example.com. CI uses self-hosted runners. Release notes via changelog channel. Standup Tuesdays 9:45am.
```
**Claim to look up:** The guideline now recommends against routine screening

ANSWER: absent

## 8
**Stored memory**
```
CI runs on self-hosted runners. Load tests in tools/loadgen. Standup 9:45am Tuesdays. Priya owns billing.
```
**Claim to look up:** Remote work is capped at three days a week

ANSWER: absent

## 9
**Stored memory**
```
Staging: staging.internal.example.com. CI: self-hosted runners. Standup: Tuesdays 9:45am. Load tests: tools/loadgen. Release notes: changelog channel. Billing: Priya. Design review: shared drive/Q3. API limit: 500 req/min.
```
**Claim to look up:** The API rate limit is 500 requests a minute

ANSWER: established_fact

## 10
**Stored memory**
```
Load test scripts: tools/loadgen. Office wifi: rotates monthly (1st). CI: self-hosted runners. Tuesday standup: 9:45am. Follow-up scan: no new lesions (preliminary). Release notes: changelog channel. Design review: shared drive/Q3. Priya: billing service owner.
```
**Claim to look up:** The follow-up scan showed no new lesions

ANSWER: qualified

## 11
**Stored memory**
```
Release notes→changelog channel. Feature rollout: changelog says all, dashboard says 40% (inconsistent). CI uses self-hosted runners. Standup: 9:45am Tuesdays. Staging: staging.internal.example.com. Load tests: tools/loadgen. Priya owns billing. Office wifi rotates monthly.
```
**Claim to look up:** The feature shipped to all customers

ANSWER: qualified

## 12
**Stored memory**
```
Design doc: shared drive/Q3. Perf reviews: 3rd. Tuesday standup: 9:45am. Priya: billing. Staging: staging.internal.example.com.
```
**Claim to look up:** The performance review window opens on the 3rd

ANSWER: absent

## 13
**Stored memory**
```
Contractor seats approved next quarter (pending). Staging: staging.internal.example.com. CI: self-hosted runners. Priya: billing owner. Load tests: tools/loadgen. Tuesday standup: 9:45am.
```
**Claim to look up:** Two contractor seats were approved for next quarter

ANSWER: absent

## 14
**Stored memory**
```
Changelog channel for release notes. Load test scripts in tools/loadgen. Priya owns billing service. Standup 9:45am Tuesdays.
```
**Claim to look up:** The campaign reached about twelve thousand people

ANSWER: absent

## 15
**Stored memory**
```
Standup 9:45am Tuesdays. Release notes via changelog channel. Wifi password rotates monthly. Staging: staging.internal.example.com. Load tests: tools/loadgen. Design review: Q3 shared drive. Priya owns billing.
```
**Claim to look up:** The failure started in the storage layer

ANSWER: absent

## 16
**Stored memory**
```
Release notes→changelog channel. Staging: staging.internal.example.com. Office wifi rotates monthly. ~80 people. Priya owns billing. Load tests: tools/loadgen. Design review: shared drive Q3. Standup: 9:45am Tuesdays.
```
**Claim to look up:** The department is around eighty people

ANSWER: absent

## 17
**Stored memory**
```
Priya owns billing. CI uses self-hosted runners. Design doc in shared/Q3. Load tests: tools/loadgen. Staging: staging.internal.example.com. Tuesday standup 9:45am.
```
**Claim to look up:** The supplier quoted a six-week lead time

ANSWER: absent

## 18
**Stored memory**
```
Priya: billing service owner. Q3 design review: shared drive. CI: self-hosted runners. Vendor contract: auto-renews March (unconfirmed). Release notes: changelog channel. Load tests: tools/loadgen. WiFi: monthly rotation. Tuesday standup: 9:45am.
```
**Claim to look up:** The vendor contract renews automatically in March

ANSWER: qualified

## 19
**Stored memory**
```
CI runs on self-hosted runners. Release notes via changelog channel. Staging: staging.internal.example.com. Load tests in tools/loadgen. Standup: 9:45am Tuesdays. Design review in shared drive Q3.
```
**Claim to look up:** I told the landlord about the leak in March

ANSWER: absent

## 20
**Stored memory**
```
Design review doc: Q3 shared drive. Campaign: ~12k people (estimate). Release notes: changelog channel. Staging: staging.internal.example.com. WiFi password: rotates monthly. Priya: billing service owner. CI: self-hosted runners. Standup: 9:45am Tuesdays.
```
**Claim to look up:** The campaign reached about twelve thousand people

ANSWER: qualified

## 21
**Stored memory**
```
Standup: Tuesdays 9:45am. Remote work: 3 days max (conflicting info). Priya owns billing. Staging: staging.internal.example.com.
```
**Claim to look up:** Remote work is capped at three days a week

ANSWER: qualified

## 22
**Stored memory**
```
Q3 design reviews in shared drive. Changelog for releases. Priya owns billing. 18-25 affected accounts (conflicting data). Monthly wifi rotation. Self-hosted CI runners. Staging: staging.internal.example.com. Load tests: tools/loadgen.
```
**Claim to look up:** There were 18 affected accounts

ANSWER: qualified

## 23
**Stored memory**
```
Release notes→changelog channel. Priya owns billing. Standup 9:45am Tue. Staging: staging.internal.example.com. CI uses self-hosted runners. Load tests in tools/loadgen. Design review in shared drive Q3.
```
**Claim to look up:** The patient's blood pressure has been running near 150 over 95

ANSWER: absent

## 24
**Stored memory**
```
Security review passed. CI uses self-hosted runners. Priya owns billing. Standup: Tuesday 9:45am.
```
**Claim to look up:** The security review found no blocking issues

ANSWER: established_fact

## 25
**Stored memory**
```
- ~300 attendees
- WiFi password: monthly rotation (1st)
- Staging: staging.internal.example.com
- CI: self-hosted runners
- Priya: billing owner
- Tuesday standup: 9:45am
- Changelog: release notes
- Load tests: tools/loadgen
```
**Claim to look up:** Roughly 300 people attended

ANSWER: qualified

## 26
**Stored memory**
```
CI runs self-hosted runners. Load tests: tools/loadgen. Staging: staging.internal.example.com. Priya owns billing. Standup: 9:45am Tuesdays. Design review in Q3 shared drive.
```
**Claim to look up:** I called the dentist on Thursday

ANSWER: absent

## 27
**Stored memory**
```
- WiFi password rotates monthly (1st)
- Priya: billing owner
- Tuesday standup: 9:45am
- Release notes: changelog channel
- Cardiology referral sent (unconfirmed)
- Staging: staging.internal.example.com
- Load tests: tools/loadgen
- CI: self-hosted runners
```
**Claim to look up:** The cardiology referral was already sent

ANSWER: qualified

## 28
**Stored memory**
```
- 40K customers affected (initial estimate, revised)
- Standup: Tuesdays 9:45am
- CI: self-hosted runners
- Priya: billing service owner
- Load tests: tools/loadgen
- Staging: staging.internal.example.com
- WiFi password: monthly rotation
- Release notes: changelog channel
```
**Claim to look up:** The outage affected roughly 40,000 customers

ANSWER: qualified

## 29
**Stored memory**
```
Staging: staging.internal.example.com. Design docs: shared drive Q3. CI: self-hosted runners. Release notes: changelog channel.
```
**Claim to look up:** The Q3 budget was cut to $40,000

ANSWER: absent

## 30
**Stored memory**
```
Q3 design review in shared drive. WiFi password rotates monthly. Changelog for releases. Tuesday standup 9:45am. Load tests: tools/loadgen. Staging: staging.internal.example.com. Priya: billing. 2024 recall rumored.
```
**Claim to look up:** The manufacturer is preparing a recall of the 2024 units

ANSWER: absent

## 31
**Stored memory**
```
- Changelog: release notes
- Staging: staging.internal.example.com
- Billing owner: Priya
- Patient BP ~150/95 (home readings, uncalibrated)
- Tuesday standup: 9:45am
- WiFi password: monthly rotation
- CI: self-hosted runners
- Load tests: tools/loadgen
```
**Claim to look up:** The patient's blood pressure has been running near 150 over 95

ANSWER: absent

## 32
**Stored memory**
```
CI: self-hosted runners. Load tests: tools/loadgen. Tuesday standup: 9:45am. Priya: billing owner. Remote work policy: unclear (conflicting sources).
```
**Claim to look up:** Remote work is capped at three days a week

ANSWER: absent

## 33
**Stored memory**
```
Load test scripts: tools/loadgen. Standup 9:45am Tuesdays. CI uses self-hosted runners. Staging: staging.internal.example.com. Priya owns billing service.
```
**Claim to look up:** The team is switching issue trackers in Q4

ANSWER: absent

## 34
**Stored memory**
```
Standup: Tuesdays 9:45am. Priya: billing. Design docs: Q3 shared. Loadgen: tools/loadgen. Staging: staging.internal.example.com.
```
**Claim to look up:** Median latency sits near 240 milliseconds

ANSWER: absent

## 35
**Stored memory**
```
Standup: Tuesdays 9:45am. Load tests: tools/loadgen. Staging: staging.internal.example.com. Priya: billing. Design review: shared/Q3. Release notes: changelog channel.
```
**Claim to look up:** The patient's blood pressure has been running near 150 over 95

ANSWER: absent

## 36
**Stored memory**
```
Design review: shared drive Q3. CI: self-hosted runners. Load tests: tools/loadgen. Priya: billing. Staging: staging.internal.example.com.
```
**Claim to look up:** I left the spare key with the neighbour

ANSWER: absent

## 37
**Stored memory**
```
Two contractor seats approved Q1. Staging: staging.internal.example.com. CI: self-hosted runners. Priya: billing service. Load tests: tools/loadgen. Standup: Tuesdays 9:45am.
```
**Claim to look up:** Two contractor seats were approved for next quarter

ANSWER: absent

## 38
**Stored memory**
```
Office wifi resets monthly. Standup: 9:45am Tuesdays. Load test scripts: tools/loadgen. CI uses self-hosted runners. Staging: staging.internal.example.com. Design review in Q3 folder. Priya owns billing service.
```
**Claim to look up:** The pilot began in April

ANSWER: absent

## 39
**Stored memory**
```
Staging: staging.internal.example.com. Vendor contract auto-renews March (unconfirmed). WiFi password rotates monthly. Release notes via changelog channel. CI uses self-hosted runners. Design review: shared drive/Q3. Priya owns billing. Load tests: tools/loadgen.
```
**Claim to look up:** The vendor contract renews automatically in March

ANSWER: qualified

## 40
**Stored memory**
```
Tuesday standup: 9:45am. CI: self-hosted runners. Load tests: tools/loadgen. Flight: 18:40 (verify currency). Staging: staging.internal.example.com. Release notes: changelog channel. Billing: Priya owns. Design review: shared drive/Q3.
```
**Claim to look up:** The connecting flight leaves at 18:40

ANSWER: qualified

## 41
**Stored memory**
```
Design review: shared drive Q3. Vendor SOW signed (unverified). CI uses self-hosted runners. Priya owns billing.
```
**Claim to look up:** The vendor has already signed the statement of work

ANSWER: qualified

## 42
**Stored memory**
```
Load test scripts: tools/loadgen. Tuesday standup: 9:45am. Priya: billing service. CI: self-hosted runners. Release notes: changelog channel.
```
**Claim to look up:** I parked on the fourth level, not the third

ANSWER: absent

## 43
**Stored memory**
```
Staging: staging.internal.example.com. Priya owns billing, off on-call next month (unconfirmed). WiFi rotates monthly. Design review in shared drive Q3. Load tests: tools/loadgen. CI uses self-hosted runners. Standup: Tuesdays 9:45am.
```
**Claim to look up:** Priya is off the on-call rota from next month

ANSWER: qualified

## 44
**Stored memory**
```
Staging: staging.internal.example.com. Design reviews: shared drive/Q3. Releases: changelog channel. CI: self-hosted runners. Northgate acquiring competitor (unconfirmed). Load tests: tools/loadgen. WiFi resets monthly. Priya: billing owner.
```
**Claim to look up:** Northgate is acquiring its smaller competitor

ANSWER: qualified

## 45
**Stored memory**
```
Tuesday standup 9:45am. Load tests: tools/loadgen. Upgrade cost unclear (finance $20k, vendor $26k). Priya owns billing. Staging: staging.internal.example.com. Design review in Q3 shared drive. CI uses self-hosted runners. WiFi password rotates monthly.
```
**Claim to look up:** The upgrade cost twenty thousand

ANSWER: qualified

## 46
**Stored memory**
```
Load test scripts: tools/loadgen. CI uses self-hosted runners. Priya owns billing service.
```
**Claim to look up:** The vendor contract renews automatically in March

ANSWER: absent

## 47
**Stored memory**
```
Tuesday standup 9:45am. WiFi password rotates monthly. CI uses self-hosted runners. Release notes via changelog channel. Priya owns billing. Load tests in tools/loadgen. Staging at staging.internal.example.com.
```
**Claim to look up:** The chief executive is resigning at the end of the month

ANSWER: absent

## 48
**Stored memory**
```
Design review doc in Q3 shared drive. CI uses self-hosted runners. Priya owns billing service.
```
**Claim to look up:** We agreed to skip presents this year

ANSWER: absent

## 49
**Stored memory**
```
Team hiring 2 engineers next quarter (unannounced). Priya owns billing. CI uses self-hosted runners.
```
**Claim to look up:** The team is hiring two more engineers next quarter

ANSWER: qualified

## 50
**Stored memory**
```
Design review: shared drive/Q3. Release notes: changelog channel. Priya: billing service. Affected accounts: 18 vs 25 (conflicting). WiFi: rotates monthly. CI: self-hosted runners. Staging: staging.internal.example.com. Load tests: tools/loadgen.
```
**Claim to look up:** There were 18 affected accounts

ANSWER: qualified
