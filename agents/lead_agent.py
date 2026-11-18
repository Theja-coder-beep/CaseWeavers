
def generate_leads(findings):

    leads = []

    # Check whether a person's identity is known
    if findings["people"]:

        leads.append(
            "Can the identity of the unidentified person be established?"
        )

    # Check whether a location was identified
    if findings["places"]:

        leads.append(
            "Can the reported location be independently verified?"
        )

    # Check whether a time was identified
    if findings["times"]:

        leads.append(
            "Is there another source that can confirm the reported time?"
        )

    # Questions about reported events
    if findings["events"]:

        leads.append(
            "Are there any other witnesses who can confirm these events?"
        )

        leads.append(
            "Is there any independent evidence supporting the reported events?"
        )

    # Use missing information to suggest questions
    for unknown in findings["unknowns"]:

        if "identity" in unknown.lower():

            leads.append(
                "Were any identifying details of the person recorded?"
            )

        elif "time" in unknown.lower():

            leads.append(
                "Can the approximate time of the event be established?"
            )

        elif "location" in unknown.lower():

            leads.append(
                "Can the location of the reported event be established?"
            )

    # Remove duplicate questions
    leads = list(dict.fromkeys(leads))

    return leads
