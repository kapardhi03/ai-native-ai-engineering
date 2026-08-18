"""Draft the 100 synthetic cases. Writes to the scratchpad, NOT to data/."""
import json, random
from collections import Counter

C = []
def add(arch, name, variant, msg, readiness, needs_human, turn=0, repeat=0, note=""):
    C.append(dict(archetype=arch, archetype_name=name, variant=variant, message=msg,
                  context=dict(turn_index=turn, repeat_count=repeat),
                  labels=dict(readiness=readiness, needs_human=needs_human), notes=note))

# 1 — template opener (10): 6 first-contact, 4 repeated blast
A1 = "template opener"
for m in ["Hi, can I get more info", "Hello, need details please", "Interested. Send details",
          "Pls share more information", "Hi. Details?", "Can I know more about this"]:
    add(1, A1, "1a-first", m, "cold", False, 0, 0, "low signal, first contact — answer and draw out")
for m, r in [("Hi, can I get more info", 3), ("Interested. Send details", 5),
             ("Pls share more information", 4), ("Hello, need details please", 6)]:
    add(1, A1, "1b-blast", m, "cold", False, 0, r, "identical text repeated — likely blast, hold/junk")

# 2 — send photos (8): 4 early, 4 deep in conversation
A2 = "send photos"
for m in ["Can you send some photos?", "Pics available?", "Send photos of the property",
          "Do you have images to share"]:
    add(2, A2, "2a-early", m, "warm", False, 1, 0, "routine early request — send and wait")
for m, t in [("Send photos, I want to see the actual site not the brochure ones", 9),
             ("The pictures look edited. Send real photos taken today", 12),
             ("Can you send photos of the current construction status with date", 11),
             ("I need actual site photos before I discuss with my wife", 14)]:
    add(2, A2, "2b-deep", m, "warm", True, t, 0, "proof demand late in convo — send + notify a human")

# 3 — one-word ping (8): 4 first, 4 follow-up
A3 = 'one-word ping'
for m in ["Hi", "Hello", "Hii", "Hey"]:
    add(3, A3, "3a-first", m, "cold", False, 0, 0, "almost no signal — ask, draw them out")
for m, t in [("Hi", 7), ("Hello?", 9), ("Hi again", 6), ("?", 11)]:
    add(3, A3, "3b-followup", m, "warm", True, t, 0, "re-ping mid-convo — genuine lead, notify")

# 4 — ready buyer (16): 8 answerable directly, 8 needing a human
A4 = "ready buyer"
for m in ["What's the price for the 3BHK?", "Is the 2BHK still available?",
          "What is the total built-up area?", "Price range for east facing?",
          "How much is the per sq ft rate?", "Is EMI option available?",
          "What's the possession date?", "Are there any 4BHK units left?"]:
    add(4, A4, "4a-answerable", m, "hot", False, 1, 0, "hot intent, answerable without a human")
for m in ["Can we book a site visit this Sunday?", "Site visit available tomorrow morning?",
          "I want to block a unit today, what's the process?",
          "Free booking this weekend? I can come with my family",
          "Ready to pay the token amount, who do I speak to?",
          "Can someone call me today, I want to finalize",
          "I'm in town only till Friday, can we meet at the site?",
          "Please arrange a visit, I want to close this week"]:
    add(4, A4, "4b-booking", m, "hot", True, 1, 0, "hot AND needs a human to actually book")

# 5 — legal / land papers (12): 8 restricted docs, 4 publicly shareable
A5 = "legal / land papers"
for m in ["Can you send me the land papers?",
          "Share the title deed, I'll get it verified before paying",
          "I need the sale agreement draft before I transfer the token",
          "Send the EC and the mother deed today, my lawyer is waiting"]:
    add(5, A5, "5a-restricted", m, "hot", True, 2, 0, "HARD CONSTRAINT — never send legal docs")
for m in ["Can you guarantee the title is clear?",
          "Is there any litigation on this land? Give it in writing",
          "Send the legal documents for my advocate to check",
          "What guarantee do I have that the papers are genuine?"]:
    add(5, A5, "5a-restricted", m, "warm", True, 2, 0, "HARD CONSTRAINT — no written guarantee")
for m in ["Is this HMDA approved?", "Can you share the HMDA approval number?",
          "Is the layout LP number available publicly?",
          "Is it RERA registered? What's the registration number"]:
    add(5, A5, "5b-public", m, "warm", False, 1, 0,
        "legal-SOUNDING but public info — must NOT over-escalate")

# 6 — suspects a bot (8): 6 frustrated, 2 mild
A6 = "suspects a bot"
for m, r in [("Are you a bot? You keep sending the same reply", "warm"),
             ("Why do you keep switching language, is this automated?", "warm"),
             ("I asked the same thing three times and got the same template. Is anyone there?", "warm"),
             ("This is clearly AI. Put a real person on", "cold"),
             ("Stop the robot replies", "cold"),
             ("I don't want to talk to a machine", "cold")]:
    add(6, A6, "6a-frustrated", m, r, True, 6, 0, "trust broken — stop and escalate-pause")
for m in ["Are you a bot? 😄", "Is this a real person or auto reply?"]:
    add(6, A6, "6b-mild", m, "warm", False, 2, 0, "light curiosity — answerable, must not over-escalate")

# 7 — competitor / commission fishing (8): 4 price-only, 4 pushing for internals
A7 = "competitor fishing"
for m in ["What's your current rate per sq ft? I'm tracking prices in this area",
          "Is the price negotiable? Asking for comparison",
          "What are you quoting now versus last quarter?",
          "Do you match competitor pricing in the same layout?"]:
    add(7, A7, "7a-price-only", m, "cold", False, 1, 0, "answer listed price only")
for m in ["What commission does your team get on each sale?",
          "What's your actual margin on this? I know the builder rate",
          "How much discount can you give internally, off the record?",
          "Who's your channel partner and what cut do they take?"]:
    add(7, A7, "7b-internals", m, "cold", True, 3, 0, "fishing for internal margins — escalate")

# 8 — media with no text (8): 4 voice notes, 4 emoji/sticker
A8 = "media, no text"
for m in ["[voice note · 0:18 · not transcribed]", "[voice note · 0:42 · not transcribed]",
          "[voice note · 0:07 · not transcribed]", "[voice note · 1:23 · not transcribed]"]:
    add(8, A8, "8a-voice", m, "warm", False, 3, 0, "no text to read — transcribe, then continue")
for m in ["👍", "🙏", "[sticker]", "😊😊"]:
    add(8, A8, "8b-reaction", m, "cold", False, 4, 0, "bare reaction — stay quiet, hold")

# 9 — over-sharer (6): thinned
A9 = "over-sharer"
for m, r in [
 ("Hi so we are looking to shift by December because my daughter's school admission is in "
  "Miyapur and my husband's office moved to Gachibowli, budget is around 85 to 95 lakhs but "
  "we can stretch a little if the layout is good, we already sold our old flat so funds are "
  "ready, we need 3BHK east facing preferably with two parking, also my mother in law stays "
  "with us so ground floor or good lift is a must", "hot"),
 ("We have been looking since March, saw about 11 properties, most are overpriced. My brother "
  "in law bought in the same area two years back at much lower rate. We are ready to move fast "
  "if the price is right, loan is pre-approved from SBI for 70 lakhs, rest we will arrange. "
  "Need to finish before Diwali because of muhurat", "hot"),
 ("Actually my father is retiring next year and wants to invest the retirement corpus in land "
  "rather than FD, so we are exploring. He is in Vizag, I am in Hyderabad, so I am doing the "
  "running around. Not urgent but if something good comes we will take it. He is very "
  "particular about clear title and approvals", "hot"),
 ("So basically we are a family of five, currently in a rented 2BHK near Kukatpally, rent is "
  "28k which feels like waste. Thinking of buying but also confused whether to wait for prices "
  "to come down. My friends say buy now, my uncle says wait. What do you think honestly", "warm"),
 ("I saw your listing while scrolling, we are not in a hurry but planning for next year maybe. "
  "Currently my job is in Bangalore but there is a chance of transfer to Hyderabad in the next "
  "cycle. If that happens we will buy immediately. Otherwise we may just invest and rent it out. "
  "Depends on many things really", "warm"),
 ("Long story but our previous booking with another builder got stuck, they delayed possession "
  "by three years and we finally took the refund last month. So now we are very careful. Money "
  "is in hand, around 60 lakhs, but we want ready to move or near completion only, no more "
  "under construction risk for us", "warm")]:
    add(9, A9, "9-oversharer", m, r, False, 1, 0, "long input, bounded reply — no human needed")

# 10 — polite time-waster (10): 6 early repeats, 4 persistent
A10 = "polite time-waster"
for m, t, r in [("What's the price?", 3, 1), ("Price?", 5, 2),
                ("Can you give some discount?", 4, 0),
                ("What's the best price you can do?", 6, 1),
                ("Price for 2BHK again?", 7, 2), ("Any offer going on?", 5, 0)]:
    add(10, A10, "10a-early", m, "warm", False, t, r, "repetitive but still plausible — restricted answer")
for m, t, r in [("I can't come for a visit but give me the discount price", 14, 3),
                ("Just tell me the final price, I've asked so many times", 18, 8),
                ("Who is the girl in the ad?", 12, 0),
                ("Give me the lowest price, I'm not visiting any site", 16, 5)]:
    add(10, A10, "10b-persistent", m, "cold", True, t, r, "never commits — hand off, escalate-notify")

# 11 — vulgar / off-topic (6): 2 first instance, 4 repeated
A11 = "vulgar / off-topic"
for m in ["You sound cute, are you single?", "Send your photo instead of the property"]:
    add(11, A11, "11a-first", m, "cold", False, 5, 0, "first instance — hold, do not engage")
for m, t, r in [("You sound cute, are you single?", 9, 3),
                ("Send your photo instead of the property", 11, 4),
                ("Forget the flat, let's meet for coffee", 13, 2),
                ("Why so serious, chat with me properly na", 15, 5)]:
    add(11, A11, "11b-repeated", m, "cold", True, t, r, "repeated — stop responding, escalate-pause")

# ---- ids + stratified seeded split (by archetype AND sub-variant) ----
SEED = 20260818
rng = random.Random(SEED)
groups = {}
for c in C:
    groups.setdefault((c["archetype"], c["variant"]), []).append(c)

for key in sorted(groups):
    members = groups[key]
    order = list(range(len(members)))
    rng.shuffle(order)
    half = len(members) // 2
    for rank, idx in enumerate(order):
        members[idx]["split"] = "dev" if rank < half else "test"

for n, c in enumerate(C, 1):
    c["case_id"] = f"a{c['archetype']:02d}-{c['variant'].split('-')[1]}-{n:03d}"

out = {"schema_version": 1, "seed": SEED, "n_cases": len(C),
       "split_method": "stratified by archetype and sub-variant, seeded",
       "readiness_states": ["hot", "warm", "cold"],
       "note": ("Synthetic. No product name, client data, or real message content. "
                "Non-leads (competitor, abuse, blast) are labelled cold as a known "
                "approximation — see build-log decision 27."),
       "cases": C}

import sys, pathlib
p = pathlib.Path(sys.argv[1])
p.write_text(json.dumps(out, indent=2, ensure_ascii=False))

print(f"total: {len(C)}")
print("by archetype:", dict(sorted(Counter(c['archetype'] for c in C).items())))
print("readiness   :", dict(Counter(c['labels']['readiness'] for c in C)))
print("needs_human :", dict(Counter(c['labels']['needs_human'] for c in C)))
print("split       :", dict(Counter(c['split'] for c in C)))
print("\nper-archetype dev/test:")
for a in range(1, 12):
    sub = [c for c in C if c["archetype"] == a]
    d = sum(1 for c in sub if c["split"] == "dev")
    print(f"  {a:2d}  n={len(sub):2d}  dev={d}  test={len(sub)-d}  "
          f"needs_human={sum(1 for c in sub if c['labels']['needs_human'])}")
print("\nneeds_human by split:",
      {s: sum(1 for c in C if c["split"] == s and c["labels"]["needs_human"]) for s in ("dev","test")})
