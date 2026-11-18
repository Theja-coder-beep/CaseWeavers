
from agents.evidence_agent import analyze_evidence
from agents.connection_agent import find_connections
from agents.contradiction_agent import detect_contradictions
from agents.lead_agent import generate_leads
from agents.report_agent import generate_report


def run_investigation(case_name, evidence_documents):

    # STEP 1: Evidence Agent
    evidence_findings = {}

    for document in evidence_documents:

        findings = analyze_evidence(
            document["content"]
        )

        evidence_findings[document["filename"]] = findings


    # STEP 2: Connection Agent
    connections = find_connections(
        evidence_documents
    )


    # STEP 3: Contradiction Agent
    contradictions = detect_contradictions(
        evidence_documents
    )


    # STEP 4: Lead Generation Agent
    all_leads = []

    for findings in evidence_findings.values():

        leads = generate_leads(findings)

        all_leads.extend(leads)

    # Remove duplicate questions
    all_leads = list(dict.fromkeys(all_leads))


    # STEP 5: Report Agent
    report = generate_report(
        case_name,
        evidence_documents,
        evidence_findings,
        connections,
        contradictions,
        all_leads
    )


    # Return all results
    return {
        "evidence_findings": evidence_findings,
        "connections": connections,
        "contradictions": contradictions,
        "leads": all_leads,
        "report": report
    }
