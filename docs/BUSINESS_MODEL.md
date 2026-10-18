# Kizuna Forge — Business Model

> **Convention.** Statements marked **[Assumption]** are hypotheses to test in a pilot. They are not market research. No market-size figures or revenue projections are claimed here.

## 1. Target customer

- **Primary:** Japanese manufacturing SMEs (roughly 20–300 employees) in precision machining, metalworking, casting, moulding and machine maintenance. Their competitiveness rests on a few veterans' craft skills, and they have no training department.
- **Buyer:** the president or director of manufacturing (the "Keiko Morita" persona). They carry the continuity risk and approve spending.
- **Champion and administrator:** the quality or training manager ("Kenji Watanabe"), who runs captures and signs off competency.
- **End users:** veteran experts (contributors and approvers), and younger and international engineers (learners).
- **Channel partners [Assumption]:** regional industrial support organisations, chambers of commerce, machine-tool dealers and system integrators who already advise SMEs, plus programmes that support international talent.

## 2. The business problem the buyer pays to solve

1. **Continuity:** "If this person leaves, can we still make, inspect or repair this?"
2. **Time to competence:** successors learn by shadowing, which takes years and depends on the veteran's availability.
3. **Quality escapes and rework** when undocumented judgement (thermal soak, gauge zeroing) is done wrong.
4. **Onboarding international workers** who need clear, bilingual and traceable instructions.
5. **Proof for customers and auditors** that critical processes are documented and that operators are trained and signed off.

## 3. Why an SME would pay (value hypotheses to measure in the pilot)

| Value | Pilot metric (measured in-product) |
|---|---|
| Critical skills move from "in one head" to "documented + validated successor" | Risk score per skill before and after (Risk radar); number of validated successors |
| Faster, more consistent onboarding | Attempts to pass, score trajectory, time from enrolment to sign-off (attempt history, CSV export) |
| Less expert time per trainee **[Assumption]** | Mentoring sessions per validated competency |
| Fewer errors on documented steps **[Assumption]** | Customer-supplied rework and NCR data, compared before and after (outside the product) |
| Knowledge asset owned by the company | Exportable versioned SOPs and training records |

## 4. Pricing structure [Assumption: to validate with 3–5 pilot customers]

| Tier | Intended for | Price basis | Includes |
|---|---|---|---|
| **Pilot** (fixed term, ~3 months) | One plant, 1–3 experts, 3–5 critical procedures | Fixed fee | Guided onboarding, capture coaching, on-premises or cloud setup, outcome review |
| **Standard** | SMEs after the pilot | Annual subscription by **expert seats** (people whose knowledge is captured) plus a learner allowance | All modules, offline extractor, exports, EN/JA |
| **Plus** | Multi-site or international workforce | Higher per-seat price plus LLM usage at cost-plus | Claude extraction and assistant, more languages, SSO |
| **Private deployment** | Firms that treat craft knowledge as a trade secret | Annual licence plus support | Runs inside the customer network (the single-process design makes this cheap to operate) |
| **Services** | Any tier | Per engagement | On-site capture sessions (interviewing and filming veterans), procedure review workshops, translation review |

Pricing by **expert seat** follows the value: the product is worth most where a scarce expert's knowledge is captured, and learners should not be a cost barrier.

## 5. Implementation costs and operational constraints

- **Software delivery cost is low.** Kizuna Forge runs as one Python process with SQLite and has no paid dependencies. The offline extractor has no per-use cost. LLM usage is optional and metered.
- **The real cost is people's time.** A veteran must spend time being recorded and reviewing extracted procedures. The product reduces this with demonstration markers, bulk confirmation of evidence-verified steps, and targeted open questions instead of blank documents. Capture services exist for firms that need help.
- **Constraints:** expert willingness (consent and recognition matter: the expert's name stays on "their" procedure), factory-floor recording conditions (noise and gloves), IT restrictions (offline and on-premises are supported), and language (EN/JA interface; translations reviewed by people).
- **Liability:** procedures are company documents approved by company experts. The product never certifies safety or hands-on competence, and says so in the UI.

## 6. Pilot to wider deployment

1. **Weeks 0–2: select.** With the director, use the Risk radar (seeded from interviews) to choose 3–5 critical skills with retiring or single holders.
2. **Weeks 2–6: capture and verify.** Record demonstrations, run extraction, and have experts review and publish. Target: every selected skill reaches "published".
3. **Weeks 6–12: transfer and measure.** Enrol successors and run mentoring sessions and assessments, with trainer sign-off. Target: at least one validated successor per selected skill, plus a before/after risk report.
4. **Expand:** more skills and sites; add LLM extraction if the customer accepts cloud processing; integrate HR or ERP master data; offer the template library to similar firms through partners.

## 7. Competitive differentiation

| Alternative | Gap Kizuna Forge addresses |
|---|---|
| Paper or Excel work instructions, video folders | No tacit knowledge structure, no link from instruction to evidence, no competency loop |
| Generic LMS or e-learning | Content has to be authored by someone else; no capture from experts; no evidence or approval chain |
| Manual-authoring tools for frontline work | Focus on formatting instructions, not on extracting veteran judgement or measuring successors |
| Generic AI chatbots | Fluent but unverifiable answers; no approval workflow; risky in a factory |

**Kizuna Forge's combination:** evidence-linked extraction, mandatory expert approval, assessment with critical gates and trainer sign-off, and explainable risk, all in one closed loop that runs offline or on-premises.

## 8. Major adoption risks and mitigations

| Risk | Mitigation |
|---|---|
| Experts are reluctant ("my knowledge is my value") | Consent workflow, expert remains named owner and approver, recognition in the knowledge graph, mentorship credit |
| Capture effort is too high | Markers on video, sample-driven onboarding, capture services, open questions instead of blank pages |
| Extraction quality on messy speech | Rule-based extractor keeps everything reviewable; optional LLM provider; evidence verifier flags anything unsupported |
| Trust in AI on the shop floor | Nothing is published without expert approval; evidence badges; "AI-inferred" is always visible |
| Security of trade secrets | On-premises deployment, tenant isolation, audit log, no cloud processing unless enabled |
| SME budget limits | Expert-seat pricing, low running cost, fixed-price pilot with measurable outcomes |
