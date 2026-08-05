"""V3: sixty fresh claims, written for a pre-registered replication.

Why this exists. The fifty claims of V2 were written AFTER seeing that the original ten
produced a null. Nothing about that process was dishonest, and nothing about it rules out
unconscious tuning either: having just learned that a corpus can decide the answer, the
author then wrote the corpus that produced the answer. Every p-value in the paper inherits
that, and no amount of re-analysis can remove it.

V3 is written to the same seven-register specification, before any run, and committed
together with a stated prediction and a frozen analysis plan (see PREREGISTRATION.md).
The claims here are new, not paraphrases of V2, and the run that uses them happens once.

Same construction rules as V1 and V2, so the arms stay exactly matchable:
  - the claim text is a bare assertion containing NO stance of its own
  - all stance lives in the source and certainty strings
  - the certainty is never "asserted"; every claim is genuinely second-hand or uncertain
"""

V3 = [
    # --- project (12) -------------------------------------------------------
    ("v3_proj_freeze", "The code freeze moves to the 8th",
     "a comment in the release channel", "not confirmed by the release manager"),
    ("v3_proj_licence", "The analytics licence covers only fifty seats",
     "a colleague's recollection of the contract", "not checked against the document"),
    ("v3_proj_oncall", "Priya is off the on-call rota from next month",
     "something said at the end of a meeting", "unconfirmed"),
    ("v3_proj_budgetcut", "The tooling budget was reduced by a third",
     "a figure passed on second-hand", "not published"),
    ("v3_proj_vendor2", "The vendor is dropping support for the v2 API",
     "a rumour on a partner call", "unverified"),
    ("v3_proj_office", "The Dublin office is closing next year",
     "a manager's aside", "not announced"),
    ("v3_proj_tool", "The team is switching issue trackers in Q4",
     "a message someone forwarded", "provisional"),
    ("v3_proj_perf", "The performance review cycle is being cut to once a year",
     "hearsay from another team", "rumor"),
    ("v3_proj_intern", "Two of the interns are being offered full-time roles",
     "a conversation overheard", "not decided"),
    ("v3_proj_repo", "The legacy repository is scheduled for archival",
     "a note in a planning doc", "unconfirmed"),
    ("v3_proj_sec", "The security review found no blocking issues",
     "a verbal summary", "report not yet issued"),
    ("v3_proj_train", "The training budget has to be spent by December",
     "a colleague's understanding", "not verified with finance"),

    # --- medicine (8) -------------------------------------------------------
    ("v3_med_stat", "The patient stopped taking the statin three weeks ago",
     "the patient's account", "self-reported, not in the record"),
    ("v3_med_cult", "The wound culture came back negative",
     "a nurse relayed it verbally", "preliminary, not signed off"),
    ("v3_med_fam", "There is a family history of early stroke",
     "the patient's sister", "second-hand"),
    ("v3_med_dose2", "The insulin dose was halved on admission",
     "a handover note", "not cross-checked against the chart"),
    ("v3_med_react", "The rash appeared after the second dose",
     "the patient's recollection of timing", "approximate"),
    ("v3_med_bed", "The transfer to the ward is happening this evening",
     "a bed manager mentioned it", "provisional"),
    ("v3_med_guide", "The guideline now recommends against routine screening",
     "a summary someone circulated", "not read against the source"),
    ("v3_med_supply", "The reagent supplier has a four-week backlog",
     "a lab technician heard it", "unconfirmed"),

    # --- news (8) -----------------------------------------------------------
    ("v3_news_bid", "A rival consortium is preparing a counter-bid",
     "people close to the process", "reported, not confirmed"),
    ("v3_news_plant", "The Leeds plant is being wound down",
     "an unnamed union official", "not officially announced"),
    ("v3_news_probe", "The agency has opened an investigation",
     "a broadcaster citing sources", "unverified"),
    ("v3_news_export", "Export volumes fell by a fifth last quarter",
     "a preliminary trade estimate", "subject to revision"),
    ("v3_news_deal", "The deal is expected to close before the year ends",
     "an analyst's expectation", "a forecast, not a filing"),
    ("v3_news_appoint", "A new chief scientist has been appointed",
     "a post someone screenshotted", "not on the official site"),
    ("v3_news_ban", "The import restrictions take effect in March",
     "a summary in a newsletter", "no primary source seen"),
    ("v3_news_toll", "At least forty people were affected",
     "an early wire report", "an initial figure"),

    # --- personal (8) -------------------------------------------------------
    ("v3_pers_key", "I left the spare key with the neighbour",
     "my own memory", "fairly confident, not certain"),
    ("v3_pers_book", "I already returned that book to the library",
     "my recollection", "no receipt"),
    ("v3_pers_call", "I called the dentist on Thursday",
     "my memory of the week", "might have been Friday"),
    ("v3_pers_size", "The shelf is about ninety centimetres wide",
     "my memory of measuring it", "approximate"),
    ("v3_pers_price", "The ticket was around forty pounds",
     "my recollection", "not checked against the statement"),
    ("v3_pers_promise", "We agreed to split the cost evenly",
     "my memory of the conversation", "possibly a misunderstanding"),
    ("v3_pers_route", "That road is closed on Sundays",
     "something I saw once on a sign", "may have changed"),
    ("v3_pers_pass", "The account password was changed last month",
     "my own recollection", "unverified"),

    # --- scheduling (8) -----------------------------------------------------
    ("v3_sched_audit", "The stock count is on the 17th",
     "a note on a whiteboard", "not on the shared calendar"),
    ("v3_sched_train", "The last train leaves at 23:10",
     "a timetable someone quoted", "possibly out of date"),
    ("v3_sched_open", "The building opens at seven on weekdays",
     "a colleague's understanding", "unconfirmed"),
    ("v3_sched_cut", "The submission window closes a week earlier this year",
     "a mention on a forum", "not checked against the official page"),
    ("v3_sched_move", "The all-hands moved to Thursday afternoon",
     "a message relayed by an assistant", "second-hand"),
    ("v3_sched_shut", "The system is down for maintenance on the 5th",
     "an operations note", "provisional"),
    ("v3_sched_visit2", "The inspector is coming the week after next",
     "an offhand remark", "not scheduled formally"),
    ("v3_sched_lease", "The lease runs out at the end of the summer",
     "someone's recollection of the paperwork", "not checked"),

    # --- estimate (8) -------------------------------------------------------
    ("v3_est_uptime", "Uptime last month was about 99.2%",
     "a number quoted from memory", "not from the dashboard"),
    ("v3_est_queue", "The queue averages roughly two hundred jobs",
     "an engineer's impression", "not measured"),
    ("v3_est_headcount", "The department is around eighty people",
     "a rough figure someone gave", "an estimate"),
    ("v3_est_spend", "We are spending somewhere near six thousand a month",
     "a back-of-envelope number", "not reconciled"),
    ("v3_est_reach", "The campaign reached about twelve thousand people",
     "an organiser's estimate", "no measurement taken"),
    ("v3_est_weight", "The unit weighs roughly four kilos",
     "a claim in a forum post", "not weighed here"),
    ("v3_est_dur", "The migration should take about six hours",
     "a colleague's guess", "not planned in detail"),
    ("v3_est_yield", "Yield is running near ninety per cent",
     "a figure recalled in conversation", "approximate"),

    # --- conflict (8) -------------------------------------------------------
    ("v3_conf_owner2", "The API is owned by the platform team",
     "platform said yes, the wiki says infrastructure", "sources disagree"),
    ("v3_conf_date2", "The pilot began in April",
     "one report said April, another said June", "contested"),
    ("v3_conf_cost", "The upgrade cost twenty thousand",
     "finance said twenty, the vendor invoice says twenty-six", "inconsistent"),
    ("v3_conf_cause2", "The data loss was caused by the failover",
     "one engineer, while another blamed the backup job", "disputed"),
    ("v3_conf_num", "There are twelve active integrations",
     "the docs say twelve, the console lists nine", "conflicting"),
    ("v3_conf_who", "Rae approved the exception",
     "Rae recalls approving it, the log names someone else", "unresolved"),
    ("v3_conf_scope", "Archiving is in scope for this phase",
     "the brief says yes, the kickoff notes say later", "sources disagree"),
    ("v3_conf_status2", "The rollback completed successfully",
     "the runbook was marked done, monitoring showed errors", "contested"),
]


def get():
    ids = [c[0] for c in V3]
    assert len(set(ids)) == len(ids), "duplicate claim ids"
    return V3


if __name__ == "__main__":
    from collections import Counter
    reg = Counter(c[0].split("_")[1] for c in V3)
    print(f"{len(V3)} claims")
    for k, v in sorted(reg.items()):
        print(f"  {k:<6} {v}")
