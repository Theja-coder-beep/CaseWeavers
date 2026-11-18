
from datetime import datetime


def generate_report(
    case_name,
    evidence_documents,
    evidence_findings,
    connections,
    contradictions,
    leads
):

    report = []

    report.append("=" * 60)
    report.append("CASEWEAVER - INVESTIGATION REPORT")
    report.append("=" * 60)

    report.append("\nINVESTIGATION DETAILS")
    report.append("Investigation Name: " + case_name)

    report.append(
        "Report Generated: " +
        datetime.now().strftime("%d-%m-%Y %H:%M")
    )

    # --------------------------------
    # EVIDENCE DOCUMENTS
    # --------------------------------

    report.append("\n1. EVIDENCE DOCUMENTS")

    for document in evidence_documents:

        report.append(
            "- " + document["filename"]
        )

    # --------------------------------
    # EVIDENCE ANALYSIS
    # --------------------------------

    report.append("\n2. EVIDENCE ANALYSIS")

    for filename, findings in evidence_findings.items():

        report.append("\nSource: " + filename)

        for category, items in findings.items():

            report.append("\n" + category.upper())

            if items:

                for item in items:
                    report.append("- " + str(item))

            else:

                report.append("- No information identified.")

    # --------------------------------
    # CONNECTIONS
    # --------------------------------

    report.append("\n3. POSSIBLE EVIDENCE CONNECTIONS")

    if connections:

        for connection in connections:

            report.append(
                "- " + connection["file1"] +
                " and " + connection["file2"]
            )

            report.append(
                "  Shared words: " +
                ", ".join(connection["shared_words"])
            )

    else:

        report.append("- No possible connections identified.")

    # --------------------------------
    # POTENTIAL DISCREPANCIES
    # --------------------------------

    report.append("\n4. POTENTIAL DISCREPANCIES")

    if contradictions:

        for item in contradictions:

            report.append(
                "- " + item["file1"] +
                " and " + item["file2"]
            )

            report.append(
                "  " + item["description"]
            )

    else:

        report.append(
            "- No potential discrepancies identified."
        )

    # --------------------------------
    # SUGGESTED INVESTIGATION LEADS
    # --------------------------------

    report.append("\n5. SUGGESTED FOLLOW-UP QUESTIONS")

    if leads:

        for number, question in enumerate(leads, start=1):

            report.append(
                str(number) + ". " + question
            )

    else:

        report.append("- No follow-up questions generated.")

    # --------------------------------
    # DISCLAIMER
    # --------------------------------

    report.append("\n6. IMPORTANT NOTE")

    report.append(
        "This report contains automated text-processing findings "
        "and preliminary leads."
    )

    report.append(
        "Connections and discrepancies require human verification."
    )

    report.append(
        "This report does not establish guilt, innocence, "
        "or the truth of any statement."
    )

    report.append("\n" + "=" * 60)
    report.append("END OF REPORT")
    report.append("=" * 60)

    return "\n".join(report)
