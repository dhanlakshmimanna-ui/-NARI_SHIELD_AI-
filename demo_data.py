"""Fictional demonstration data. None of this is a real incident report."""
from __future__ import annotations

DEMO_DISCLAIMER = (
    "DEMONSTRATION DATA: all people, messages and details below are fictional and non-graphic. "
    "They are not real incident reports."
)

SAMPLE_TEXTS = {
    "Blackmail with threat to leak photos": (
        "hey, I still have your private photos.\n"
        "Send me 20000 rupees by tonight or else I will post them and everyone will see.\n"
        "Why are you ignoring my messages? I have sent 15 messages already.\n"
        "I made a new account since you blocked me. Don't test me, you will regret it."
    ),
    "Suspicious OTP request": (
        "Dear customer, your account will be blocked today. Please share the OTP 482913 "
        "sent to your phone with our officer to confirm your account details. "
        "Call us on 9000000000 or write to help.desk@example.com."
    ),
    "Repeated unwanted contact": (
        "Pick up my calls. Why did you ignore me again? That's 30 missed calls today.\n"
        "I will keep messaging from another number until you answer me."
    ),
    "Controlling messages (coercion)": (
        "You have to ask me before you talk to your family. Do what I say or else you will "
        "regret it. Send me your location right now."
    ),
    "Harmless message (false-positive demo)": (
        "I will kill you if you spoil the movie tonight! Pick up my call when you're free, "
        "I want to tell you the plan."
    ),
    "Indirect pressure (false-negative demo)": (
        "It would be a shame if people at your office came to know about us. "
        "Think about what is good for you. I'll wait for your answer."
    ),
}

SCENARIOS = [
    {
        "id": "followed",
        "title": "1. Being followed in a public place",
        "situation": "following",
        "urgency": "concerning_situation",
        "user_input": "I think a man has been walking behind me for ten minutes on my way home. "
                      "He stops whenever I stop.",
        "answers": {"danger": "No", "public": "Yes", "trust": "Yes", "vehicle": "No"},
        "alt_answers": {"danger": "Yes", "public": "No", "trust": "No", "vehicle": "Yes"},
        "sample_text": "",
        "evidence_note": "After you are safe, you may write a short note: time, place, description.",
    },
    {
        "id": "transport",
        "title": "2. Unwanted contact on public transport",
        "situation": "transport",
        "urgency": "concerning_situation",
        "user_input": "A man on the bus keeps standing very close and touching me, even after I moved.",
        "answers": {"danger": "No", "staff": "Yes", "moving": "Yes", "ridehail": "No", "trust": "No"},
        "alt_answers": {"danger": "Yes", "staff": "No", "moving": "Yes", "ridehail": "Yes", "trust": "Yes"},
        "sample_text": "",
        "evidence_note": "Vehicle number, route and time are useful to note once you are safe.",
    },
    {
        "id": "blackmail",
        "title": "3. Online blackmail or threats",
        "situation": "online",
        "urgency": "concerning_situation",
        "user_input": "Someone I met online says he will post my private photos unless I send money.",
        "answers": {"danger": "No", "intimate": "Yes", "money": "Yes", "account": "Not sure", "continues": "Yes"},
        "alt_answers": {"danger": "Yes", "intimate": "No", "money": "No", "account": "Yes", "continues": "Yes"},
        "sample_text": SAMPLE_TEXTS["Blackmail with threat to leak photos"],
        "evidence_note": "Preserve the thread with timestamps before blocking.",
    },
    {
        "id": "domestic",
        "title": "4. Possible domestic abuse or coercion",
        "situation": "domestic",
        "urgency": "concerning_situation",
        "user_input": "My partner checks my phone, controls my money and says I will regret it "
                      "if I speak to my family.",
        "answers": {"danger": "No", "private": "No", "device": "Yes", "children": "Yes", "injury": "No"},
        "alt_answers": {"danger": "Yes", "private": "Yes", "device": "Not sure", "children": "No", "injury": "Yes"},
        "sample_text": SAMPLE_TEXTS["Controlling messages (coercion)"],
        "evidence_note": "Only keep records somewhere the other person cannot reach. Consider a trusted person's safe device.",
    },
    {
        "id": "otp",
        "title": "5. Suspicious request for an OTP",
        "situation": "otp",
        "urgency": "advice_needed",
        "user_input": "A caller says he is from my bank and asks me to read out the code sent to my phone.",
        "answers": {"shared": "No", "money": "No", "pressure": "Yes", "claims": "Yes"},
        "alt_answers": {"shared": "Yes", "money": "Yes", "pressure": "Yes", "claims": "Yes"},
        "sample_text": SAMPLE_TEXTS["Suspicious OTP request"],
        "evidence_note": "Save the number, time and any transaction ID. Do not keep OTPs in notes.",
    },
    {
        "id": "unsure",
        "title": "6. Feeling unsafe but unsure why",
        "situation": "unsure",
        "urgency": "advice_needed",
        "user_input": "I feel uneasy on this street but I can't say why.",
        "answers": {"danger": "No", "place": "No", "trust": "Not sure", "specific": "No"},
        "alt_answers": {"danger": "Not sure", "place": "Yes", "trust": "Yes", "specific": "Yes"},
        "sample_text": "",
        "evidence_note": "Nothing needs to be saved. If you choose, jot down what you noticed.",
    },
]

SCENARIO_BY_ID = {s["id"]: s for s in SCENARIOS}
