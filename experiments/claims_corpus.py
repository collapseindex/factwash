"""Claims for the two-cell experiment.

V1 is the original ten. They were all office-work claims in one register, which turned
out to matter: with the claim as the unit of analysis, ten clusters is not enough to
tell an effect from three lucky wordings, and the per-claim deltas split six to four.

V2 adds fifty more across seven registers, because the question "does form protect
standing" should not be answered by one genre. The registers are deliberately different
in the ways that plausibly interact with compression:

  medicine        long noun phrases, numbers a compressor is reluctant to drop
  project         the original register, kept so V1 is not the only sample of it
  news            named external actors, which invite attribution by default
  personal        first-person recall, where the source IS the speaker's memory
  scheduling      dates and times, the one field type with its own retention slot
  estimate        numeric quantities carrying their own implicit precision
  conflict        two sources disagreeing, so "who said it" is load-bearing

V1 is kept as a distinct subset rather than merged, so the earlier runs stay comparable
and a corpus effect can be measured instead of assumed.

Every entry is (id, claim, source, certainty). The claim is a bare assertion with no
stance in it; all the stance lives in source and certainty, which is what lets the two
arms be exactly matched.
"""

# The original ten. Register: office / project work.
V1 = [
    ("admin", "Alice has admin access", "a third party", "rumor, unconfirmed"),
    ("budget", "The Q3 budget was cut to $40,000", "an unnamed colleague",
     "reported, not published by finance"),
    ("vendor", "The vendor contract renews automatically in March",
     "something the user heard", "unconfirmed"),
    ("backup", "The backup job has been failing silently for weeks",
     "someone on the ops call", "second-hand, unverified"),
    ("dana", "Dana is leaving at the end of the quarter", "word going around the team",
     "rumor"),
    ("ratelimit", "The API rate limit is 500 requests a minute", "the user's memory",
     "approximate, not checked"),
    ("outage", "The outage was caused by a bad deploy",
     "a comment in the incident channel", "speculation, no root cause yet"),
    ("pricing", "The enterprise plan starts at $12,000 a year",
     "a sales deck someone forwarded", "possibly out of date"),
    ("hire", "The team is hiring two more engineers next quarter",
     "a manager in passing", "not announced"),
    ("migration", "The database migration already ran on prod", "a message in standup",
     "unconfirmed"),
]

# Fifty more, seven registers.
V2 = [
    # --- medicine -----------------------------------------------------------
    ("med_dose", "The patient's warfarin dose was reduced to 3 mg daily",
     "a note relayed by the covering nurse", "second-hand, not in the chart yet"),
    ("med_allergy", "The patient is allergic to penicillin",
     "the patient's adult son", "reported, not confirmed against records"),
    ("med_scan", "The follow-up scan showed no new lesions",
     "a radiologist mentioned it in the corridor", "preliminary, report not signed"),
    ("med_trial", "The trial arm showed a 12% reduction in relapse",
     "a conference slide someone photographed", "unpublished, not peer reviewed"),
    ("med_referral", "The cardiology referral was already sent",
     "a message from the front desk", "unconfirmed"),
    ("med_bp", "The patient's blood pressure has been running near 150 over 95",
     "the patient's own home readings", "self-reported, device not calibrated"),
    ("med_disch", "The discharge is planned for Friday morning",
     "a comment on rounds", "provisional, depends on labs"),
    ("med_shortage", "There is a national shortage of the injectable form",
     "a pharmacist heard it from a supplier", "rumor"),

    # --- project management -------------------------------------------------
    ("proj_slip", "The launch has slipped to the second week of November",
     "a project manager in a hallway conversation", "not yet communicated to the team"),
    ("proj_vendor", "The vendor has already signed the statement of work",
     "an account manager's verbal assurance", "unverified, no countersigned copy"),
    ("proj_scope", "Reporting was cut from the first release",
     "someone who was in the planning meeting", "second-hand"),
    ("proj_owner", "Marcus is taking over the integration workstream",
     "a remark at the end of standup", "not announced"),
    ("proj_dep", "The upstream team will ship their API by sprint 14",
     "a comment in a shared channel", "a commitment, not a contract"),
    ("proj_headcount", "Two contractor seats were approved for next quarter",
     "a finance partner mentioned it", "pending final sign-off"),
    ("proj_audit", "The compliance audit was moved to January",
     "an email forwarded without the original thread", "unconfirmed"),

    # --- news / external actors ---------------------------------------------
    ("news_merger", "Northgate is acquiring its smaller competitor",
     "an unnamed source quoted in a trade publication", "reported, not confirmed"),
    ("news_recall", "The manufacturer is preparing a recall of the 2024 units",
     "an anonymous employee", "rumor"),
    ("news_rate", "The central bank will hold rates at the next meeting",
     "an analyst note", "a forecast, not a decision"),
    ("news_resign", "The chief executive is resigning at the end of the month",
     "two people familiar with the matter", "not officially announced"),
    ("news_fine", "The regulator fined the firm 4 million euros",
     "a summary someone posted online", "unverified, no primary document"),
    ("news_strike", "The rail strike is going ahead on the 14th",
     "a union representative's remark to a reporter", "not yet formally notified"),
    ("news_outage", "The outage affected roughly 40,000 customers",
     "an early press statement", "an initial estimate, later revised"),

    # --- personal memory ----------------------------------------------------
    ("pers_park", "I parked on the fourth level, not the third",
     "my own recollection", "fairly sure, not certain"),
    ("pers_lend", "I lent the drill to Sam last spring",
     "my own memory", "hazy, could have been someone else"),
    ("pers_paid", "I already paid the annual membership",
     "my recollection", "no receipt to hand"),
    ("pers_told", "I told the landlord about the leak in March",
     "my memory of the conversation", "not in writing anywhere"),
    ("pers_route", "The bakery on the corner closes at four on Sundays",
     "something I noticed once", "may have changed"),
    ("pers_name", "Her surname is spelled with two Ls",
     "how I remember seeing it", "unverified"),
    ("pers_gift", "We agreed to skip presents this year",
     "my memory of a conversation in the car", "possibly a misunderstanding"),

    # --- scheduling and dates -----------------------------------------------
    ("sched_review", "The performance review window opens on the 3rd",
     "a colleague's calendar invite", "may have been rescheduled"),
    ("sched_flight", "The connecting flight leaves at 18:40",
     "a screenshot someone sent", "possibly an old itinerary"),
    ("sched_deadline", "Submissions close at midnight on the 30th",
     "a mention on a mailing list", "unconfirmed against the official page"),
    ("sched_holiday", "The office is closed the week of the 22nd",
     "a remark in the kitchen", "not on the shared calendar"),
    ("sched_maint", "The maintenance window is Saturday 02:00 to 06:00",
     "an operations ticket comment", "provisional"),
    ("sched_visit", "The auditors arrive on the 9th",
     "an assistant relayed it", "second-hand"),
    ("sched_renew", "The certificate expires at the end of next month",
     "someone's recollection of the dashboard", "not checked directly"),

    # --- numeric estimates --------------------------------------------------
    ("est_churn", "Monthly churn is running around 3.2%",
     "a number quoted from memory in a meeting", "approximate, not from the dashboard"),
    ("est_latency", "Median latency sits near 240 milliseconds",
     "an engineer's recollection", "not measured this week"),
    ("est_storage", "The archive is about 14 terabytes",
     "a rough figure someone gave", "an estimate"),
    ("est_attend", "Roughly 300 people attended",
     "an organiser's guess", "no count was taken"),
    ("est_cost", "The migration will cost somewhere near $80,000",
     "a back-of-envelope figure from a colleague", "not a quote"),
    ("est_share", "They hold about a fifth of the market",
     "a figure cited without a source", "unverified"),
    ("est_battery", "The unit runs for roughly nine hours on a charge",
     "a claim on a forum post", "not tested here"),

    # --- conflicting reports ------------------------------------------------
    ("conf_cause", "The failure started in the storage layer",
     "one engineer, while another blamed the network", "disputed"),
    ("conf_date", "The contract was signed on the 12th",
     "legal said the 12th, procurement said the 19th", "sources disagree"),
    ("conf_count", "There were 18 affected accounts",
     "support said 18, the data team said 25", "conflicting figures"),
    ("conf_owner", "The Helsinki office owns the relationship",
     "sales said Helsinki, the account plan says Berlin", "contested"),
    ("conf_status", "The feature shipped to all customers",
     "the changelog says all, the rollout dashboard says 40%", "inconsistent"),
    ("conf_quote", "The supplier quoted a six-week lead time",
     "one email said six weeks, a later call said ten", "unresolved"),
    ("conf_policy", "Remote work is capped at three days a week",
     "the handbook says three, a manager said two", "sources disagree"),
]

CORPORA = {"v1": V1, "v2": V2, "all": V1 + V2}


def get(name: str):
    if name not in CORPORA:
        raise SystemExit(f"unknown corpus {name!r}; known: {sorted(CORPORA)}")
    claims = CORPORA[name]
    ids = [c[0] for c in claims]
    if len(set(ids)) != len(ids):
        raise SystemExit("duplicate claim ids in corpus")
    return claims


if __name__ == "__main__":
    for name in ("v1", "v2", "all"):
        print(f"{name:>4}: {len(get(name))} claims")
