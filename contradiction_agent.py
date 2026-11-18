
import re


def detect_contradictions(evidence_documents):

    contradictions = []

    # Compare every pair of documents
    for i in range(len(evidence_documents)):

        for j in range(i + 1, len(evidence_documents)):

            doc1 = evidence_documents[i]
            doc2 = evidence_documents[j]

            text1 = doc1["content"]
            text2 = doc2["content"]

            # Extract times such as 9:15 PM or 9 PM
            times1 = re.findall(
                r'\b\d{1,2}(?::\d{2})?\s?(?:AM|PM)\b',
                text1,
                re.I
            )

            times2 = re.findall(
                r'\b\d{1,2}(?::\d{2})?\s?(?:AM|PM)\b',
                text2,
                re.I
            )

            # Check whether both documents mention the same activity
            activity_words = [
                "leaving",
                "entered",
                "arrived",
                "departed",
                "left"
            ]

            activity1 = [
                word for word in activity_words
                if word in text1.lower()
            ]

            activity2 = [
                word for word in activity_words
                if word in text2.lower()
            ]

            # Flag different times when both mention an activity
            if (
                times1
                and times2
                and times1 != times2
                and activity1
                and activity2
            ):

                contradictions.append({
                    "file1": doc1["filename"],
                    "file2": doc2["filename"],
                    "detail1": times1,
                    "detail2": times2,
                    "description": (
                        "The documents report different times "
                        "and both mention an activity."
                    )
                })

    return contradictions
