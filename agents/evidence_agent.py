
import re


def analyze_evidence(text):

    findings = {
        "people": [],
        "places": [],
        "times": [],
        "events": [],
        "unknowns": []
    }

    # 1. Find time expressions
    times = re.findall(
        r'\b\d{1,2}(?::\d{2})?\s?(?:AM|PM|am|pm)\b',
        text
    )
    findings["times"] = times

    # 2. Find possible places
    location_words = [
        "laboratory", "office", "building",
        "room", "campus", "library"
    ]

    for word in location_words:
        if word.lower() in text.lower():
            findings["places"].append(word)

    # 3. Find people references
    if re.search(r'\bperson\b|\bwitness\b|\bindividual\b', text, re.I):
        findings["people"].append("Unidentified person mentioned")

    # 4. Find important events
    sentences = re.split(r'[.!?]+', text)

    for sentence in sentences:
        sentence = sentence.strip()

        if any(word in sentence.lower() for word in
               ["saw", "seeing", "carrying", "leaving", "entered", "reported"]):
            findings["events"].append(sentence)

    # 5. Identify missing information
    if "person" in text.lower() or "individual" in text.lower():
        findings["unknowns"].append(
            "The person's identity is not established."
        )

    if not times:
        findings["unknowns"].append(
            "No specific time was identified."
        )

    if not findings["places"]:
        findings["unknowns"].append(
            "No recognised location keyword was identified."
        )

    return findings
