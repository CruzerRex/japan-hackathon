"""Simulated demo content for Minato Precision Works (湊精密工業) — a FICTIONAL
precision-machining SME. All people, procedures, values and records are
simulated for demonstration. Procedures are deliberately safe: inspection and
maintenance are performed with the machine stopped or isolated, and nothing
instructs anyone to bypass guards. Numeric values quoted by "experts" refer
to the part drawing / setup sheet and must be verified against real documents.
"""

ORG = {
    "id": "org_minato", "name": "Minato Precision Works", "name_ja": "湊精密工業株式会社",
    "industry": "Precision machining — spindle housings, bearing seats, machine-tool components",
    "location": "Ota City, Tokyo (simulated)", "employee_count": 86, "plan_tier": "pilot", "is_simulated": 1,
    "recording_policy": "Expert recordings require written consent stating who may view them and for what purpose. "
                        "Recordings stay on the company server and are deleted on request or after the retention period.",
    "retention_days": 3650,
}

OTHER_ORG = {
    "id": "org_hokuto", "name": "Hokuto Casting (isolation test tenant)", "name_ja": "北斗鋳造",
    "industry": "Iron casting", "location": "Sakata, Yamagata (simulated)", "employee_count": 40, "plan_tier": "pilot",
    "is_simulated": 1, "recording_policy": "", "retention_days": 1825,
}

# id, email, name, name_ja, role, title, department, languages, years, retirement, bio
USERS = [
    ("usr_morita", "morita@minato.example", "Keiko Morita", "森田 恵子", "admin", "Director of Manufacturing", "Management",
     "ja, en", 24, None, "Owns the knowledge-continuity programme and the pilot budget."),
    ("usr_tanaka", "tanaka@minato.example", "Hiroshi Tanaka", "田中 宏", "expert", "Senior Inspection Engineer", "Quality",
     "ja", 41, "2027-03-31", "41 years in precision inspection. Known on the floor as the person who can tell a warm part by touch."),
    ("usr_kobayashi", "kobayashi@minato.example", "Masao Kobayashi", "小林 正夫", "expert", "Master Machinist (kisage)",
     "Machining", "ja", 44, "2027-09-30", "Hand-scraping (kisage) specialist; rebuilt every slideway in the plant."),
    ("usr_saito", "saito@minato.example", "Emiko Saito", "斎藤 恵美子", "expert", "Maintenance Lead", "Maintenance",
     "ja, en", 26, None, "Runs preventive maintenance for the turning and grinding cells."),
    ("usr_watanabe", "watanabe@minato.example", "Kenji Watanabe", "渡辺 健二", "trainer", "Training & Quality Manager",
     "Quality", "ja, en", 18, None, "Coordinates on-the-job training and signs off competency evidence."),
    ("usr_ishikawa", "ishikawa@minato.example", "Yuta Ishikawa", "石川 雄太", "trainee", "Production Engineer (2nd year)",
     "Machining", "ja", 2, None, ""),
    ("usr_nguyen", "nguyen@minato.example", "Nguyen Van An", "グエン・ヴァン・アン", "trainee",
     "Machining Engineer (Specified Skilled Worker)", "Machining", "vi, en, ja (JLPT N3)", 3, None,
     "Joined from a Hanoi machining school; prefers English training material with Japanese terms."),
    ("usr_takahashi", "takahashi@minato.example", "Mei Takahashi", "高橋 芽衣", "trainee", "Quality Inspector (1st year)",
     "Quality", "ja, en", 1, None, ""),
    ("usr_oshiro", "oshiro@minato.example", "Ricardo Oshiro", "大城 リカルド", "trainee", "CNC Operator", "Machining",
     "pt, ja", 4, None, "Nikkei Brazilian operator moving into setup work."),
]
OTHER_USERS = [
    ("usr_hokuto_admin", "admin@hokuto.example", "Sato Jun", "佐藤 潤", "admin", "Plant Manager", "Management", "ja", 20,
     None, ""),
]

# code, name, name_ja, category, criticality, description
SKILLS = [
    ("SK-BORE", "Precision bore inspection", "精密内径測定", "Inspection", 5,
     "Measuring bearing bores for size, taper and roundness with a bore gauge."),
    ("SK-THERM", "Thermal stabilisation judgement", "温度安定化の判断", "Inspection", 4,
     "Knowing when a part and gauge are thermally stable enough to measure."),
    ("SK-SURF", "Surface finish judgement", "面粗さの官能評価", "Inspection", 4,
     "Detecting chatter marks and scratches by sight and fingernail before instrument checks."),
    ("SK-MICRO", "Micrometer zero verification", "マイクロメータ零点確認", "Metrology", 3,
     "Verifying and adjusting outside micrometer zero against a standard."),
    ("SK-KISAGE", "Slideway hand scraping (kisage)", "きさげ加工", "Machining craft", 5,
     "Hand scraping machine slideways to a bearing pattern."),
    ("SK-GRIND", "Grinding wheel dressing", "砥石ドレッシング", "Machining craft", 4,
     "Dressing surface-grinder wheels with a single-point diamond."),
    ("SK-SPDL", "Spindle run-out check", "主軸振れ測定", "Maintenance", 4,
     "Measuring spindle total indicated run-out with a test bar and indicator."),
    ("SK-LATHE-PM", "CNC lathe pre-shift inspection", "CNC旋盤 始業点検", "Maintenance", 3,
     "Daily pre-shift inspection of a 2-axis CNC turning centre."),
    ("SK-FIXT", "Fixture clamping sequence", "治具クランプ手順", "Machining craft", 3,
     "Clamping thin-wall parts without distortion."),
]

# user, skill, proficiency
HOLDERS = [
    ("usr_tanaka", "SK-BORE", 5), ("usr_tanaka", "SK-THERM", 5), ("usr_tanaka", "SK-SURF", 4), ("usr_tanaka", "SK-MICRO", 5),
    ("usr_kobayashi", "SK-KISAGE", 5), ("usr_kobayashi", "SK-GRIND", 5), ("usr_kobayashi", "SK-SPDL", 4),
    ("usr_kobayashi", "SK-FIXT", 4),
    ("usr_saito", "SK-SPDL", 5), ("usr_saito", "SK-LATHE-PM", 5), ("usr_saito", "SK-MICRO", 4), ("usr_saito", "SK-GRIND", 3),
    ("usr_saito", "SK-FIXT", 4),
    ("usr_watanabe", "SK-MICRO", 4), ("usr_watanabe", "SK-LATHE-PM", 4), ("usr_watanabe", "SK-THERM", 3),
    ("usr_watanabe", "SK-FIXT", 4),
]

ASSETS = [
    ("machine", "Horizontal boring cell HB-2", "横中ぐりセル HB-2", "Produces SH-62 spindle housings"),
    ("machine", "2-axis CNC turning centre LT-03", "2軸CNC旋盤 LT-03", ""),
    ("machine", "Surface grinder SG-1", "平面研削盤 SG-1", ""),
    ("gauge", "Dial bore gauge 50–80 mm", "シリンダゲージ 50–80mm", "0.001 mm graduation"),
    ("gauge", "Setting ring Ø62 mm", "セッティングリング Ø62", "Calibrated annually"),
    ("gauge", "Outside micrometer 50–75 mm", "外側マイクロメータ 50–75mm", ""),
    ("tool", "Granite surface plate", "定盤", ""),
]

# ------------------------------------------------------------------------------------------------
# SIGNATURE CAPTURE — Tanaka's spindle-housing bore inspection (Act 2 of the demo)
# ------------------------------------------------------------------------------------------------
SIGNATURE_TRANSCRIPT = """WEBVTT

00:00:05.000 --> 00:00:20.000
Tanaka: This is the final inspection for the SH-62 spindle housing bore. The purpose of this inspection is to prove the bearing bore is round, straight and on size before the housing goes to assembly.

00:00:21.000 --> 00:00:47.000
Tanaka: Before you start, you need the dial bore gauge, the 62 millimetre setting ring and a clean granite surface plate. Wear safety glasses, because the alcohol and compressed air can spray.

00:00:48.000 --> 00:01:23.000
Tanaka: First, leave the housing and the setting ring on the surface plate to soak for at least 60 minutes after washing. Because cast iron grows when it is warm, a warm part reads oversize and you will pass a bad bore.

00:01:24.000 --> 00:02:04.000
Tanaka: Put the back of your hand on the housing and then on the plate. If the housing feels warmer than the plate, wait another 30 minutes. My rule is simple: if you can feel a difference, the part is still moving.

00:02:05.000 --> 00:02:39.000
Tanaka: Clean the bore and the setting ring with a lint-free cloth and alcohol. A single chip under a gauge contact gives you a false reading of several microns.

00:02:40.000 --> 00:03:29.000
Tanaka: Zero the bore gauge in the 62 millimetre setting ring. Rock the gauge a little and watch the needle, you get used to it. The needle turns around at the smallest reading, and that turning point is the true zero.

00:03:30.000 --> 00:04:14.000
Tanaka: Insert the gauge into the bore at the first depth, 5 millimetres from the front face, keeping it square to the face. Read the value at the point where the needle turns around.

00:04:15.000 --> 00:04:39.000
Tanaka: You'll hear it before you see it. When the contacts seat properly the gauge goes quiet, and a scratching sound means a contact is riding on a burr.

00:04:40.000 --> 00:05:19.000
Tanaka: Measure at three depths, front, middle and back, and at two orientations, 0 and 90 degrees. That gives six readings for every bore.

00:05:20.000 --> 00:05:49.000
Tanaka: Record every reading on the inspection sheet immediately. Never rely on memory, people swap numbers all the time.

00:05:50.000 --> 00:06:34.000
Tanaka: Check that all six readings are within the drawing tolerance. The drawing for this housing calls for H6, which on a 62 millimetre bore is plus 0 to plus 19 microns. You must confirm this before you move on.

00:06:35.000 --> 00:07:19.000
Tanaka: Compare the front and back readings to check taper, and the 0 and 90 degree readings to check roundness. If the taper is more than 5 microns, stop and call the machining leader, because the boring bar may be wearing.

00:07:20.000 --> 00:07:54.000
Tanaka: The most common mistake new people make is measuring before the part has cooled. Another mistake is pushing the gauge in at an angle, which scratches the bore.

00:07:55.000 --> 00:08:29.000
Tanaka: If a reading is out of tolerance, re-clean the bore and re-zero the gauge, then measure again. If it is still out, put a red hold tag on the housing and record it as nonconforming. Never adjust a reading to make it pass.

00:08:30.000 --> 00:09:09.000
Tanaka: Inspect the bore surface under the inspection lamp. Run your fingernail lightly across the bore, and if your nail catches there is a chatter mark or scratch deeper than the finish allows. Mark the location with a paint pen for rework.

00:09:10.000 --> 00:09:40.000
Tanaka: Sign the inspection sheet and move the housing to the green released rack. Only then is it ready for assembly.
"""

SIGNATURE_CAPTURE = {
    "title": "SH-62 spindle housing — final bore inspection",
    "task_category": "Final inspection",
    "machine": "Horizontal boring cell HB-2 (SH-62 spindle housing)",
    "tools": ["Dial bore gauge 50–80 mm", "Setting ring Ø62 mm", "Lint-free cloth", "Inspection lamp", "Paint pen"],
    "materials": ["Isopropyl alcohol"],
    "skill_codes": ["SK-BORE", "SK-THERM", "SK-SURF"],
    "experience_level": "Intermediate (operator with basic metrology)",
    "transcript": SIGNATURE_TRANSCRIPT,
    "expert_notes": "Inspection sheet IS-62 is the record of truth; the drawing revision is printed on it.",
    "tips": "Hold the gauge by the insulated grip only - body heat through the handle grows the rod by a few microns in a minute.\n"
            "Re-check zero in the setting ring after every three housings.",
    "mistakes": "Zeroing the gauge in a setting ring that has not soaked on the same plate as the part.",
    "troubleshooting": "Readings drift upward while measuring -> stop, let the gauge and ring soak 10 minutes on the plate, then re-zero.\n"
                       "Needle never turns around -> the gauge is not centred; withdraw and re-insert square to the face.",
    "safety_notes": "The housing weighs 14 kg - use the lift assist to move it onto the surface plate.",
    "markers": [
        (84, "step", "Hand-feel thermal check on housing vs plate", "Back of hand: housing, then plate"),
        (160, "step", "Zero at the needle turning point", "Shown in close-up on the setting ring"),
        (255, "tip", "Gauge goes quiet when contacts seat", "Listen for scratching = burr"),
        (350, "checkpoint", "Six readings vs H6 tolerance", ""),
        (510, "step", "Fingernail test for chatter marks", "Demonstrated on rework sample R-17"),
    ],
}

# Japanese version of the same demonstration (as Tanaka would actually say it on the floor).
SIGNATURE_TRANSCRIPT_JA = """WEBVTT

00:00:05.000 --> 00:00:20.000
田中：これはSH-62スピンドルハウジングのボア最終検査です。この検査の目的は、組立に回す前に軸受ボアが真円で、まっすぐで、寸法どおりであることを証明することです。

00:00:21.000 --> 00:00:47.000
田中：始める前に、シリンダゲージ、62ミリのセッティングリング、きれいな石定盤を用意してください。アルコールやエアーが飛ぶことがあるので、保護メガネを着用してください。

00:00:48.000 --> 00:01:23.000
田中：まず、洗浄後のハウジングとセッティングリングを定盤の上で少なくとも60分温度安定させてください。なぜなら、鋳鉄は温まると膨張するので、温かい部品は大きめに測れてしまい、不良のボアを合格にしてしまうからです。

00:01:24.000 --> 00:02:04.000
田中：手の甲をハウジングに当て、次に定盤に当ててください。ハウジングが定盤より温かく感じたら、さらに30分待ってください。私のルールは単純で、違いが感じられるうちは部品はまだ動いているということです。

00:02:05.000 --> 00:02:39.000
田中：ボアとセッティングリングを、けばの出ないウエスとアルコールで清掃してください。測定子の下に切粉が一つあるだけで、数ミクロン狂います。

00:02:40.000 --> 00:03:29.000
田中：ボアゲージを62ミリのセッティングリングでゼロ合わせします。ゲージを少し揺らして針を見てください。慣れればわかります。針は最小値のところで反転し、その反転点が本当のゼロです。

00:03:30.000 --> 00:04:14.000
田中：ゲージを前端面から5ミリの最初の深さでボアに挿入し、端面に対して直角に保ってください。針が反転する点で値を読み取ってください。

00:04:15.000 --> 00:04:39.000
田中：見る前に聞こえます。測定子がきちんと座るとゲージは静かになり、ガリガリという音は測定子がバリに乗っている証拠です。

00:04:40.000 --> 00:05:19.000
田中：前・中・奥の3つの深さで、0度と90度の2方向を測定してください。これでボア1つにつき6つの読み値になります。

00:05:20.000 --> 00:05:49.000
田中：すべての読み値をすぐに検査表に記録してください。記憶に頼ってはいけません。みんなよく数字を入れ違えるからです。

00:05:50.000 --> 00:06:34.000
田中：6つの読み値がすべて図面公差内にあることを確認してください。このハウジングの図面はH6で、62ミリのボアではプラス0からプラス19ミクロンです。次に進む前に必ずこれを確認してください。

00:06:35.000 --> 00:07:19.000
田中：前と奥の読み値を比較してテーパを、0度と90度の読み値を比較して真円度を確認してください。テーパが5ミクロンを超える場合は、作業を止めて加工リーダーを呼んでください。中ぐりバーが摩耗している可能性があるからです。

00:07:20.000 --> 00:07:54.000
田中：新人がよくやる間違いは、部品が冷める前に測定することです。もう一つの間違いは、ゲージを斜めに押し込んでボアに傷をつけることです。

00:07:55.000 --> 00:08:29.000
田中：読み値が公差外なら、ボアを再清掃してゲージを再度ゼロ合わせし、もう一度測定してください。それでも外れている場合は、ハウジングに赤い保留札を付けて不適合品として記録してください。絶対に合格させるために読み値を調整しないでください。

00:08:30.000 --> 00:09:09.000
田中：検査ランプの下でボア表面を検査してください。爪を軽くボアに当てて滑らせ、爪が引っかかるなら仕上げで許される以上のびびりマークか傷があります。その位置をペイントマーカーで印を付け、手直しに回してください。

00:09:10.000 --> 00:09:40.000
田中：検査表にサインし、ハウジングを緑のリリース棚に移動してください。そこで初めて組立の準備が整います。
"""

SIGNATURE_CAPTURE_JA = {
    "title": "SH-62 スピンドルハウジング ボア最終検査",
    "task_category": "最終検査",
    "machine": "横中ぐりセル HB-2（SH-62 スピンドルハウジング）",
    "tools": ["シリンダゲージ 50–80mm", "セッティングリング Ø62", "ウエス（けばの出ないもの）", "検査ランプ", "ペイントマーカー"],
    "materials": ["イソプロピルアルコール"],
    "skill_codes": ["SK-BORE", "SK-THERM", "SK-SURF"],
    "experience_level": "中級（基本的な測定ができる作業者）",
    "transcript": SIGNATURE_TRANSCRIPT_JA,
    "expert_notes": "検査表IS-62が正式な記録。図面の改訂番号が印刷されている。",
    "tips": "ゲージは断熱グリップ部分だけを持つこと。ハンドルから体温が伝わると、1分でロッドが数ミクロン伸びる。\n"
            "ハウジング3台ごとにセッティングリングでゼロを再確認する。",
    "mistakes": "部品と同じ定盤でなじませていないセッティングリングでゼロ合わせすること。",
    "troubleshooting": "測定中に読み値が上がっていく -> 一旦止め、ゲージとリングを定盤上で10分なじませてから再度ゼロ合わせする。\n"
                       "針が反転しない -> ゲージが芯に入っていない。一度抜いて端面に直角に入れ直す。",
    "safety_notes": "ハウジングは14kgあるので、定盤への移動にはリフトアシストを使うこと。",
    "markers": [
        (84, "step", "ハウジングと定盤の手触り比較", "手の甲でハウジング→定盤の順に触る"),
        (160, "step", "針の反転点でゼロ合わせ", "セッティングリング上でクローズアップ"),
        (255, "tip", "測定子が座るとゲージが静かになる", "ガリガリ音＝バリ"),
        (350, "checkpoint", "6点の読み値をH6公差と照合", ""),
        (510, "step", "爪によるびびりマーク確認", "手直しサンプルR-17で実演"),
    ],
}

# ------------------------------------------------------------------------------------------------
# PR-004 — Kobayashi's wheel dressing (extracted at seed time, sitting in EXPERT_REVIEW)
# ------------------------------------------------------------------------------------------------
DRESSING_TRANSCRIPT = """[00:00:04] Kobayashi: We dress the wheel on surface grinder SG-1 whenever the finish goes dull or the wheel starts to load.
[00:00:15] Kobayashi: Before you start, you need the single-point diamond dresser and the dresser holder that sits on the magnetic chuck.
[00:00:30] Kobayashi: Wear safety glasses and keep the wheel guard closed the whole time; the guard stays in place for dressing.
[00:00:52] Kobayashi: Place the dresser holder on the chuck and turn the magnet on. Check the diamond is tilted about 10 to 15 degrees, trailing the wheel rotation.
[00:01:30] Kobayashi: Start the wheel and let it run for one minute before dressing. Bring the wheel down until it just touches the diamond, you'll hear a light hiss.
[00:02:10] Kobayashi: Dress with 0.02 millimetres per pass for roughing and 0.005 for finishing, crossing slowly and evenly. Rotate the diamond a quarter turn in its holder every few dressings so it stays sharp.
[00:03:00] Kobayashi: The common mistake is crossing too fast, which leaves a spiral pattern on the wheel. Don't take deep cuts either, it cracks the diamond.
[00:03:40] Kobayashi: If the hiss turns into a rough rattle, stop and check the diamond for a chipped point.
[00:04:05] Kobayashi: Finish with one spark-out pass with no down feed. Record the dressing on the machine log.
"""

DRESSING_CAPTURE = {
    "title": "SG-1 surface grinder — wheel dressing",
    "task_category": "Machine preparation", "machine": "Surface grinder SG-1",
    "tools": ["Single-point diamond dresser", "Dresser holder"], "materials": [],
    "skill_codes": ["SK-GRIND"], "experience_level": "Intermediate",
    "transcript": DRESSING_TRANSCRIPT, "expert_notes": "", "tips": "Feel the wheel guard - if it is vibrating, the wheel is out of balance; stop and report.",
    "mistakes": "", "troubleshooting": "", "safety_notes": "", "markers": [],
}

KISAGE_CAPTURE = {
    "title": "Slideway hand scraping (kisage) — bearing pattern",
    "task_category": "Machine rebuild", "machine": "Lathe carriage slideways",
    "tools": ["Flat scraper", "Prussian blue", "Master straight edge"], "materials": [],
    "skill_codes": ["SK-KISAGE"], "experience_level": "Advanced",
    "transcript": "", "expert_notes": "Session 1 planned: first-pass scraping on scrap slideway section.",
    "tips": "", "mistakes": "", "troubleshooting": "", "safety_notes": "", "markers": [],
}


def _ev(src, ts, quote):
    return {"source_type": src, "source_timestamp": ts, "evidence_quote": quote, "evidence_verified": True,
            "expert_confirmed": True}


# ------------------------------------------------------------------------------------------------
# PR-001 — CNC lathe pre-shift inspection (Saito). v1 superseded, v2 published.
# ------------------------------------------------------------------------------------------------
LATHE_TRANSCRIPT = """[00:00:06] Saito: This is the pre-shift inspection for turning centre LT-03, done at the start of every shift.
[00:00:20] Saito: With the machine in E-stop and the door open, confirm the spindle has fully stopped before you check anything inside the enclosure.
[00:00:55] Saito: Check the way-lube and coolant sight glasses. The level must be between MIN and MAX; top up only with the oil named on the machine label.
[00:01:40] Saito: Clear chips from the chuck jaws and turret with the chip hook and brush. Never pull chips by hand, and never blow compressed air toward your face.
[00:02:30] Saito: Read the chuck pressure gauge and compare it with the value on the job setup sheet. Record it on the daily checklist.
[00:03:10] Saito: Close the door, release the E-stop and run the warm-up program O9000 for 10 minutes before the first precision part. Listen to the spindle; a new whine or knock means call maintenance.
[00:04:05] Saito: Sign the daily checklist. If anything is abnormal, hang the yellow caution tag and tell the shift leader before production.
"""

LATHE_V2 = {
    "title": "LT-03 CNC turning centre — pre-shift inspection",
    "purpose": "Confirm the turning centre is safe and stable before the first part of each shift, and catch lubrication, "
               "chuck and spindle problems early.",
    "scope": "Daily, start of every shift, by the assigned operator.",
    "machine": "2-axis CNC turning centre LT-03",
    "prerequisites": ["Daily checklist form DC-LT03", "Job setup sheet for the first job"],
    "equipment": [{"name": "Chip hook and brush", "kind": "tool"}, {"name": "Safety glasses", "kind": "ppe"}],
    "skills": ["SK-LATHE-PM"],
    "safety": [{"id": "saf-001", "text": "Work inside the enclosure only with the machine in E-stop and the spindle fully stopped.",
                "step_id": "step-001", **_ev("transcript", "00:00:20", "With the machine in E-stop and the door open, confirm the spindle has fully stopped before you check anything inside the enclosure.")}],
    "steps": [
        {"step_id": "step-001", "title": "Put the machine in a safe state", "instruction": "Press E-stop, open the door and confirm the spindle has fully stopped before checking anything inside the enclosure.",
         "why": "All following checks put hands inside the enclosure.", "quality_check": "Spindle visibly stationary; E-stop latched.",
         "safety_critical": True, "critical_checkpoint": True, "confidence": 0.9, "requires_expert_review": False,
         **_ev("transcript", "00:00:20", "With the machine in E-stop and the door open, confirm the spindle has fully stopped before you check anything inside the enclosure.")},
        {"step_id": "step-002", "title": "Check lubricant and coolant levels", "instruction": "Check the way-lube and coolant sight glasses. Top up only with the oil named on the machine label.",
         "why": "Low way-lube causes slideway wear long before an alarm appears.", "quality_check": "Both levels between MIN and MAX.",
         "safety_critical": False, "critical_checkpoint": True, "confidence": 0.9, "requires_expert_review": False,
         **_ev("transcript", "00:00:55", "Check the way-lube and coolant sight glasses. The level must be between MIN and MAX; top up only with the oil named on the machine label.")},
        {"step_id": "step-003", "title": "Clear chips from chuck and turret", "instruction": "Remove chips from the chuck jaws and turret with the chip hook and brush.",
         "why": "Chips under a jaw shift the part and cause run-out.", "quality_check": "Jaw faces and serrations visibly clean.",
         "safety_critical": True, "critical_checkpoint": False, "confidence": 0.88, "requires_expert_review": False,
         **_ev("transcript", "00:01:40", "Clear chips from the chuck jaws and turret with the chip hook and brush. Never pull chips by hand, and never blow compressed air toward your face.")},
        {"step_id": "step-004", "title": "Verify chuck pressure", "instruction": "Read the chuck pressure gauge, compare it with the value on the job setup sheet and record it on the daily checklist.",
         "why": "Wrong clamping pressure distorts thin-wall parts or lets them slip.", "quality_check": "Gauge reading matches the setup sheet value.",
         "safety_critical": False, "critical_checkpoint": True, "confidence": 0.88, "requires_expert_review": False,
         **_ev("transcript", "00:02:30", "Read the chuck pressure gauge and compare it with the value on the job setup sheet. Record it on the daily checklist.")},
        {"step_id": "step-005", "title": "Run the spindle warm-up program", "instruction": "Close the door, release the E-stop and run warm-up program O9000 for 10 minutes before the first precision part. Listen to the spindle while it runs.",
         "why": "A cold spindle grows as it warms; the first parts drift out of size.", "quality_check": "Warm-up completed; no new whine or knock.",
         "safety_critical": False, "critical_checkpoint": True, "confidence": 0.86, "requires_expert_review": False,
         "tolerance": {"text": "Run warm-up program O9000 for 10 minutes before the first precision part.",
                       "evidence_quote": "run the warm-up program O9000 for 10 minutes before the first precision part"},
         **_ev("transcript", "00:03:10", "Close the door, release the E-stop and run the warm-up program O9000 for 10 minutes before the first precision part.")},
        {"step_id": "step-006", "title": "Sign off or escalate", "instruction": "Sign the daily checklist. If anything is abnormal, hang the yellow caution tag and tell the shift leader before production.",
         "why": "", "quality_check": "Checklist signed or caution tag hung.", "safety_critical": False, "critical_checkpoint": False,
         "confidence": 0.9, "requires_expert_review": False,
         **_ev("transcript", "00:04:05", "Sign the daily checklist. If anything is abnormal, hang the yellow caution tag and tell the shift leader before production.")},
    ],
    "tips": [{"id": "tip-001", "text": "Listen to the spindle during warm-up; a new whine or knock is the earliest sign of bearing trouble.", "step_id": "step-005",
              **_ev("transcript", "00:03:10", "Listen to the spindle; a new whine or knock means call maintenance.")}],
    "mistakes": [{"id": "mis-001", "text": "Pulling chips out by hand or blowing compressed air toward your face.", "consequence": "Cuts and eye injuries.",
                  "step_id": "step-003", **_ev("transcript", "00:01:40", "Never pull chips by hand, and never blow compressed air toward your face.")},
                 {"id": "mis-002", "text": "Skipping the warm-up to save 10 minutes.", "consequence": "First parts of the shift drift oversize.",
                  "step_id": "step-005", **_ev("expert_note", None, "Skipping the warm-up to save 10 minutes.")}],
    "failure_modes": [{"id": "fm-001", "symptom": "the spindle makes a new whine or knock during warm-up", "likely_cause": "Bearing or belt problem",
                       "action": "Stop and call maintenance before running production", "step_id": "step-005",
                       **_ev("transcript", "00:03:10", "Listen to the spindle; a new whine or knock means call maintenance.")},
                      {"id": "fm-002", "symptom": "a lubricant level is below MIN", "likely_cause": "Consumption or leak",
                       "action": "Top up with the oil named on the machine label and note it on the checklist", "step_id": "step-002",
                       **_ev("transcript", "00:00:55", "top up only with the oil named on the machine label")}],
    "questions": [
        {"id": "q-001", "prompt": "What must be true before you put your hands inside the LT-03 enclosure?",
         "options": ["The machine is in E-stop and the spindle has fully stopped", "The coolant pump is running", "The warm-up program has finished", "The door interlock is bypassed"],
         "answer_index": 0, "critical": True, "step_id": "step-001", "skill": "SK-LATHE-PM",
         "explanation": "Saito, 00:00:20: confirm the spindle has fully stopped with the machine in E-stop before checking inside."},
        {"id": "q-002", "prompt": "Where do you find the correct chuck pressure for today's job?",
         "options": ["On the job setup sheet", "Use the same value as yesterday", "Maximum pressure is always safest", "Ask another operator"],
         "answer_index": 0, "critical": True, "step_id": "step-004", "skill": "SK-LATHE-PM",
         "explanation": "Saito, 00:02:30: compare the gauge with the value on the job setup sheet."},
        {"id": "q-003", "prompt": "Why is the 10-minute warm-up run before the first precision part?",
         "options": ["A cold spindle grows as it warms, so early parts drift out of size", "To clean the coolant tank", "To check the door interlock", "It is only needed on Mondays"],
         "answer_index": 0, "critical": False, "step_id": "step-005", "skill": "SK-LATHE-PM",
         "explanation": "Thermal growth of the spindle during the first minutes changes part size."},
        {"id": "q-004", "prompt": "Which oil may you use to top up the way-lube?",
         "options": ["Only the oil named on the machine label", "Any hydraulic oil", "Coolant concentrate", "Whatever is in the store room"],
         "answer_index": 0, "critical": False, "step_id": "step-002", "skill": "SK-LATHE-PM",
         "explanation": "Saito, 00:00:55: top up only with the oil named on the machine label."},
    ],
    "scenarios": [
        {"id": "sc-001", "situation": "During the warm-up program you hear a new, regular knocking from the spindle. What do you do?",
         "options": [{"text": "Stop and call maintenance before running production", "correct": True, "feedback": "Correct — Saito treats a new noise as a maintenance call."},
                     {"text": "Finish the warm-up; the noise usually goes away", "correct": False, "feedback": "A new noise is an early bearing warning; continuing risks spindle damage."},
                     {"text": "Increase the spindle speed to see if it changes", "correct": False, "feedback": "Never experiment with an abnormal spindle — stop and escalate."}],
         "critical": True, "step_id": "step-005", "skill": "SK-LATHE-PM", "explanation": "Saito, 00:03:10: a new whine or knock means call maintenance."},
    ],
    "open_questions": [],
}

LATHE_V1 = {**LATHE_V2, "steps": [s for s in LATHE_V2["steps"] if s["step_id"] != "step-005"],
            "tips": [], "mistakes": LATHE_V2["mistakes"][:1], "failure_modes": LATHE_V2["failure_modes"][1:],
            "questions": [q for q in LATHE_V2["questions"] if q["id"] != "q-003"], "scenarios": []}

LATHE_JA = {
    "title": "LT-03 CNC旋盤 始業点検",
    "purpose": "各シフトの最初の加工前に、旋盤が安全かつ安定していることを確認し、潤滑・チャック・主軸の異常を早期に発見する。",
    "steps": {
        "step-001": {"title": "機械を安全な状態にする", "instruction": "非常停止ボタンを押し、扉を開け、機内を点検する前に主軸が完全に停止していることを確認する。"},
        "step-002": {"title": "潤滑油・クーラント量の確認", "instruction": "摺動面潤滑油とクーラントの油面計を確認する。補給は機械ラベル記載の油のみ使用する。"},
        "step-003": {"title": "チャックとタレットの切粉除去", "instruction": "切粉フックとブラシでチャック爪とタレットの切粉を取り除く。"},
        "step-004": {"title": "チャック圧の確認", "instruction": "チャック圧力計を読み、段取りシートの値と比較し、日常点検表に記録する。"},
        "step-005": {"title": "主軸暖機プログラムの実行", "instruction": "扉を閉め、非常停止を解除し、最初の精密加工の前に暖機プログラムO9000を10分間運転する。運転中は主軸の音を聞く。"},
        "step-006": {"title": "サインまたはエスカレーション", "instruction": "日常点検表にサインする。異常があれば黄色の注意札を掛け、生産前に班長へ報告する。"},
    },
    "safety": {"saf-001": "非常停止状態で主軸が完全に停止している時のみ機内で作業すること。"},
}

# ------------------------------------------------------------------------------------------------
# PR-002 — Spindle run-out check (Saito), published v1
# ------------------------------------------------------------------------------------------------
RUNOUT = {
    "title": "Spindle run-out check with test bar",
    "purpose": "Measure spindle total indicated run-out (TIR) during preventive maintenance and catch bearing or taper damage early.",
    "scope": "Monthly PM on turning and boring spindles, machine isolated.",
    "machine": "2-axis CNC turning centre LT-03",
    "prerequisites": ["Machine isolated per the maintenance lock-out procedure", "Machine acceptance record with the run-out limit"],
    "equipment": [{"name": "Precision test bar", "kind": "gauge"}, {"name": "Dial test indicator 0.001 mm", "kind": "gauge"},
                  {"name": "Magnetic base", "kind": "tool"}],
    "skills": ["SK-SPDL"],
    "safety": [{"id": "saf-001", "text": "The spindle is turned by hand only, with the machine isolated and locked out by maintenance.",
                "step_id": "step-001", **_ev("transcript", "00:00:15", "The spindle is turned by hand only, with the machine isolated and locked out.")}],
    "steps": [
        {"step_id": "step-001", "title": "Confirm the machine is isolated", "instruction": "Confirm maintenance has isolated and locked out the machine before touching the spindle.",
         "why": "The spindle is rotated by hand during this check.", "quality_check": "Lock-out tag present with your name.", "safety_critical": True,
         "critical_checkpoint": True, "confidence": 0.9, "requires_expert_review": False,
         **_ev("transcript", "00:00:15", "The spindle is turned by hand only, with the machine isolated and locked out.")},
        {"step_id": "step-002", "title": "Clean the spindle taper and test bar", "instruction": "Wipe the spindle taper and the test bar shank with a lint-free cloth and inspect for dents.",
         "why": "A speck of dirt in the taper shows up as run-out.", "quality_check": "No visible marks on the taper.", "safety_critical": False,
         "critical_checkpoint": False, "confidence": 0.88, "requires_expert_review": False,
         **_ev("transcript", "00:00:40", "Wipe the spindle taper and the test bar shank with a lint-free cloth and look for dents.")},
        {"step_id": "step-003", "title": "Mount the test bar", "instruction": "Seat the test bar in the taper with a firm push and twist; do not hammer it.",
         "why": "", "quality_check": "", "safety_critical": False, "critical_checkpoint": False, "confidence": 0.85, "requires_expert_review": False,
         **_ev("transcript", "00:01:10", "Seat the test bar with a firm push and twist; never hammer it in.")},
        {"step_id": "step-004", "title": "Set the indicator near the spindle nose", "instruction": "Mount the dial test indicator on the magnetic base on a non-rotating part, touching the bar close to the spindle nose with light preload.",
         "why": "", "quality_check": "", "safety_critical": False, "critical_checkpoint": False, "confidence": 0.85, "requires_expert_review": False,
         **_ev("transcript", "00:01:45", "Mount the indicator on the magnetic base on a non-rotating part, touching the bar near the spindle nose with light preload.")},
        {"step_id": "step-005", "title": "Rotate by hand and read TIR", "instruction": "Turn the spindle slowly by hand through two full turns and note the highest and lowest reading. Repeat at the far end of the bar.",
         "why": "Near and far readings separate taper damage from bearing wear.", "quality_check": "TIR at both positions within the limit in the machine acceptance record.",
         "safety_critical": False, "critical_checkpoint": True, "confidence": 0.86, "requires_expert_review": False,
         **_ev("transcript", "00:02:20", "Turn the spindle slowly by hand through two full turns and note the highest and lowest reading.")},
        {"step_id": "step-006", "title": "Record and remove the bar", "instruction": "Record both TIR values on the PM sheet, remove the test bar and return it to its case.",
         "why": "", "quality_check": "PM sheet complete.", "safety_critical": False, "critical_checkpoint": False, "confidence": 0.88,
         "requires_expert_review": False, **_ev("transcript", "00:03:30", "Record both readings on the PM sheet and put the test bar back in its case.")},
    ],
    "tips": [{"id": "tip-001", "text": "If the needle jumps once per turn at one spot, suspect a dent on the bar, not the spindle — turn the bar 90 degrees and re-check.",
              "step_id": "step-005", **_ev("transcript", "00:02:50", "If the needle jumps once per turn at one spot, suspect a dent on the bar, not the spindle.")}],
    "mistakes": [{"id": "mis-001", "text": "Hammering the test bar into the taper.", "consequence": "Damages the taper and the bar.", "step_id": "step-003",
                  **_ev("transcript", "00:01:10", "never hammer it in")}],
    "failure_modes": [{"id": "fm-001", "symptom": "TIR exceeds the acceptance limit", "likely_cause": "Dirty taper, damaged bar or bearing wear",
                       "action": "Clean the taper and bar, re-seat and re-measure; if still over the limit, report to the maintenance lead",
                       "step_id": "step-005", **_ev("transcript", "00:03:00", "If it is over the limit, clean the taper and the bar, re-seat and measure again; if it is still over, report it to me.")}],
    "questions": [
        {"id": "q-001", "prompt": "How is the spindle rotated during the run-out check?", "options": ["By hand, with the machine isolated and locked out", "At the lowest programmed speed", "In jog mode with the door open", "With the warm-up program"],
         "answer_index": 0, "critical": True, "step_id": "step-001", "skill": "SK-SPDL", "explanation": "Saito, 00:00:15: by hand only, machine isolated and locked out."},
        {"id": "q-002", "prompt": "Where does the run-out limit come from?", "options": ["The machine acceptance record", "A general rule of 0.01 mm", "The operator's experience", "The test bar label"],
         "answer_index": 0, "critical": True, "step_id": "step-005", "skill": "SK-SPDL", "explanation": "The limit is machine-specific and recorded in the acceptance record."},
        {"id": "q-003", "prompt": "Why measure at both the near and far end of the bar?", "options": ["To separate taper damage from bearing wear", "To double the number of readings", "Because the indicator needs warming", "It is optional"],
         "answer_index": 0, "critical": False, "step_id": "step-005", "skill": "SK-SPDL", "explanation": "Different patterns at the two positions point to different causes."},
    ],
    "scenarios": [
        {"id": "sc-001", "situation": "TIR at the far end is above the limit. What is your next action?",
         "options": [{"text": "Clean taper and bar, re-seat and re-measure; report if still over", "correct": True, "feedback": "Correct — rule out dirt first, then escalate."},
                     {"text": "Record it as within limit because the near reading was fine", "correct": False, "feedback": "Never record a value you did not measure as passing."},
                     {"text": "Tap the bar with a hammer to seat it", "correct": False, "feedback": "Hammering damages the taper."}],
         "critical": True, "step_id": "step-005", "skill": "SK-SPDL", "explanation": "Saito, 00:03:00."},
    ],
    "open_questions": [],
}

# ------------------------------------------------------------------------------------------------
# PR-003 — Outside micrometer zero verification (Tanaka), published v1
# ------------------------------------------------------------------------------------------------
MICRO = {
    "title": "Outside micrometer zero verification",
    "purpose": "Verify (and if needed adjust) the zero of a 50–75 mm outside micrometer before measuring production parts.",
    "scope": "Start of shift and after any drop.",
    "machine": "Inspection bench",
    "prerequisites": ["50 mm setting standard for the micrometer", "Calibration log"],
    "equipment": [{"name": "Outside micrometer 50–75 mm", "kind": "gauge"}, {"name": "50 mm setting standard", "kind": "gauge"},
                  {"name": "Lens paper", "kind": "material"}],
    "skills": ["SK-MICRO"],
    "safety": [],
    "steps": [
        {"step_id": "step-001", "title": "Let micrometer and standard soak", "instruction": "Leave the micrometer and the setting standard together on the bench for 15 minutes before checking.",
         "why": "Hand heat expands the frame and the standard differently.", "quality_check": "Both have rested together for 15 minutes.", "safety_critical": False,
         "critical_checkpoint": True, "confidence": 0.86, "requires_expert_review": False,
         **_ev("transcript", "00:00:12", "Leave the micrometer and the standard together on the bench for 15 minutes before you check it.")},
        {"step_id": "step-002", "title": "Clean the measuring faces", "instruction": "Close the faces lightly on lens paper and draw it out to clean the anvil and spindle faces.",
         "why": "", "quality_check": "", "safety_critical": False, "critical_checkpoint": False, "confidence": 0.85, "requires_expert_review": False,
         **_ev("transcript", "00:00:40", "Close the faces lightly on a piece of lens paper and pull it out to clean them.")},
        {"step_id": "step-003", "title": "Close on the standard with the ratchet", "instruction": "Hold the frame by the insulated pad, place the standard between the faces and close using the ratchet until it clicks three times.",
         "why": "The ratchet gives the same measuring force every time.", "quality_check": "", "safety_critical": False, "critical_checkpoint": False,
         "confidence": 0.86, "requires_expert_review": False,
         **_ev("transcript", "00:01:05", "Hold it by the insulated pad and close on the standard with the ratchet until it clicks three times.")},
        {"step_id": "step-004", "title": "Read and judge zero", "instruction": "Read the micrometer. The reading must match the standard's marked size exactly; any line offset means adjustment is needed.",
         "why": "", "quality_check": "Reading equals the marked size of the standard.", "safety_critical": False, "critical_checkpoint": True,
         "confidence": 0.86, "requires_expert_review": False,
         **_ev("transcript", "00:01:40", "The reading must match the size marked on the standard exactly.")},
        {"step_id": "step-005", "title": "Adjust the sleeve if needed", "instruction": "If zero is off, lock the spindle and turn the sleeve with the supplied spanner until the index line aligns, then re-check from step 3.",
         "why": "", "quality_check": "Re-check matches the standard.", "safety_critical": False, "critical_checkpoint": False, "confidence": 0.84,
         "requires_expert_review": False, **_ev("transcript", "00:02:10", "If it is off, lock the spindle and turn the sleeve with the spanner until the line matches, then check again.")},
        {"step_id": "step-006", "title": "Record in the calibration log", "instruction": "Record the check, any adjustment and your name in the calibration log.",
         "why": "", "quality_check": "Log entry complete.", "safety_critical": False, "critical_checkpoint": False, "confidence": 0.88,
         "requires_expert_review": False, **_ev("transcript", "00:02:50", "Write the check, any adjustment and your name in the calibration log.")},
    ],
    "tips": [{"id": "tip-001", "text": "Never hold the frame in your fist while measuring — it is the easiest way to lose two microns.", "step_id": "step-003",
              **_ev("transcript", "00:01:20", "Never hold the frame in your fist while measuring, that is the easiest way to lose two microns.")}],
    "mistakes": [{"id": "mis-001", "text": "Checking zero straight after carrying the micrometer in a pocket.", "consequence": "Warm frame gives a false zero.",
                  "step_id": "step-001", **_ev("expert_note", None, "Checking zero straight after carrying the micrometer in a pocket.")}],
    "failure_modes": [{"id": "fm-001", "symptom": "zero cannot be brought into line with the sleeve adjustment", "likely_cause": "Worn or damaged faces",
                       "action": "Tag the micrometer out of service and send it to calibration", "step_id": "step-005",
                       **_ev("transcript", "00:02:30", "If you cannot bring it into line, tag it out of service and send it to calibration.")}],
    "questions": [
        {"id": "q-001", "prompt": "Why do the micrometer and the standard rest together before checking?", "options": ["So both reach the same temperature", "So the oil can drain", "To let the ratchet reset", "It is not necessary"],
         "answer_index": 0, "critical": True, "step_id": "step-001", "skill": "SK-MICRO", "explanation": "Tanaka, 00:00:12: hand heat expands frame and standard differently."},
        {"id": "q-002", "prompt": "How many ratchet clicks does Tanaka use when closing on the standard?", "options": ["Three", "One", "Until it stops turning", "Five"],
         "answer_index": 0, "critical": False, "step_id": "step-003", "skill": "SK-MICRO", "explanation": "Tanaka, 00:01:05: until it clicks three times."},
        {"id": "q-003", "prompt": "The reading is one line off the standard's marked size. What does that mean?", "options": ["Zero must be adjusted before use", "It is acceptable for production", "The standard is wrong", "Close the ratchet harder"],
         "answer_index": 0, "critical": True, "step_id": "step-004", "skill": "SK-MICRO", "explanation": "Tanaka, 00:01:40: the reading must match exactly."},
    ],
    "scenarios": [
        {"id": "sc-001", "situation": "After adjusting the sleeve twice, zero still will not line up. What do you do?",
         "options": [{"text": "Tag it out of service and send it to calibration", "correct": True, "feedback": "Correct — worn faces need calibration."},
                     {"text": "Note the offset and subtract it from every reading", "correct": False, "feedback": "Undocumented corrections cause escapes."},
                     {"text": "Use it for rough parts only", "correct": False, "feedback": "A failed gauge must not be used without calibration."}],
         "critical": False, "step_id": "step-005", "skill": "SK-MICRO", "explanation": "Tanaka, 00:02:30."},
    ],
    "open_questions": [],
}

RUNOUT_JA = {
    "title": "テストバーによる主軸振れ測定",
    "purpose": "予防保全で主軸の振れ(TIR)を測定し、軸受やテーパの損傷を早期に発見する。",
    "steps": {
        "step-001": {"title": "機械の隔離を確認", "instruction": "主軸に触れる前に、保全担当が機械を隔離・ロックアウトしていることを確認する。"},
        "step-002": {"title": "テーパとテストバーの清掃", "instruction": "主軸テーパとテストバーのシャンクをリントフリークロスで拭き、打痕がないか確認する。"},
        "step-005": {"title": "手回しでTIRを読む", "instruction": "主軸を手でゆっくり2回転させ、最大値と最小値を記録する。バー先端でも繰り返す。"},
    },
    "safety": {"saf-001": "主軸は機械を隔離・ロックアウトした状態で手で回すこと。"},
}
